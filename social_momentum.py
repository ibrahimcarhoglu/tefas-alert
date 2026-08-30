"""Daily social-momentum radar kept separate from the trading signal engine.

The radar treats X/Google results as a noisy attention feed.  A social mention
can create an early-warning label, but it never changes AL/TUT/SAT decisions.
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

from database import get_connection, save_social_momentum
from signals import STRATEGY_VERSION, tefas_fund_url


SEARCH_QUERIES = (
    "site:x.com TEFAS fon",
    "site:x.com yatırım fonu aldım",
    "site:x.com fon para girişi",
    "site:x.com fon momentum",
    "site:x.com fon balon riskli",
    "site:twitter.com TEFAS fon",
)

POSITIVE_WORDS = (
    "aldım", "ekledim", "topluyorum", "kademeli alım", "pozisyon açtım",
    "güçlü", "yükseliş", "breakout", "momentum", "net giriş", "arttı",
)
NEGATIVE_WORDS = (
    "sattım", "çıkıyorum", "azalttım", "düşüş", "riskli", "balon",
    "satmalı mıyım", "düzeltme", "net çıkış", "azaldı",
)
HYPE_WORDS = (
    "all in", "full", "yüklendim", "roket", "uçtu", "moon", "patladı",
    "kaçırmayın", "kesin yükselecek", "garanti",
)
ANALYSIS_WORDS = (
    "analiz", "rapor", "veri", "portföy", "dağılım", "fon büyüklüğü",
    "yatırımcı sayısı", "para girişi", "getiri", "risk", "tefas",
)
TRUSTED_ACCOUNTS = {
    "tefasgovtr", "fon_eko", "fontahmin", "fonetikfunds", "tefasvebefasfon",
    "fintablescom", "getmidas",
}
AMBIGUOUS_BARE_CODES = {
    "HER", "BIR", "VAR", "YOK", "ILE", "AMA", "GIB", "SON", "ALT", "UST",
    "YEN", "ISI", "KAR", "BEN", "SEN", "BIZ", "HIC", "TAM", "NET", "PAY", "FON",
}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def extract_fund_codes(text: str, valid_codes: set[str]) -> set[str]:
    """Extract explicit cashtags/hashtags and context-protected bare fund codes."""
    upper = (text or "").upper()
    explicit = set(re.findall(r"[$#]([A-Z]{3})(?![A-Z])", upper))
    result = explicit & valid_codes
    context = upper.casefold()
    if any(word in context for word in ("fon", "tefas", "portföy", "yatırım")):
        bare = set(re.findall(r"(?<![A-ZÇĞİÖŞÜ])([A-Z]{3})(?![A-ZÇĞİÖŞÜ])", upper))
        result |= (bare - AMBIGUOUS_BARE_CODES) & valid_codes
    return result


def classify_social_text(text: str) -> dict[str, bool]:
    folded = (text or "").casefold()
    return {
        "positive": _contains_any(folded, POSITIVE_WORDS),
        "negative": _contains_any(folded, NEGATIVE_WORDS),
        "hype": _contains_any(folded, HYPE_WORDS),
        "analytical": _contains_any(folded, ANALYSIS_WORDS),
    }


def _account_from_link(link: str) -> str:
    match = re.search(r"(?:x|twitter)\.com/([^/?#]+)/", link or "", re.IGNORECASE)
    return match.group(1).casefold() if match else ""


def fetch_x_observations(valid_codes: set[str]) -> tuple[dict[str, dict[str, Any]], bool]:
    """Collect deduplicated X search observations through the configured Serper feed."""
    aggregates: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "mention_count": 0, "accounts": set(), "positive_count": 0,
            "negative_count": 0, "hype_count": 0, "analytical_count": 0,
            "trusted_count": 0, "examples": [],
        }
    )
    seen: set[tuple[str, str]] = set()
    source_available = False

    def consume(results: list[dict[str, Any]]) -> None:
        for item in results:
            title = str(item.get("title") or "")
            snippet = str(item.get("snippet") or "")
            link = str(item.get("link") or "")
            text = f"{title} {snippet}".strip()
            codes = extract_fund_codes(text, valid_codes)
            if not codes:
                continue
            account = str(item.get("source_id") or "") or _account_from_link(link)
            flags = classify_social_text(text)
            identity = link or re.sub(r"\s+", " ", text.casefold())[:240]
            for code in codes:
                if (code, identity) in seen:
                    continue
                seen.add((code, identity))
                row = aggregates[code]
                row["mention_count"] += 1
                if account:
                    row["accounts"].add(account)
                for flag in ("positive", "negative", "hype", "analytical"):
                    row[f"{flag}_count"] += int(flags[flag])
                row["trusted_count"] += int(account in TRUSTED_ACCOUNTS)
                if len(row["examples"]) < 3:
                    row["examples"].append({"title": title[:120], "link": link})

    api_key = os.getenv("SERPER_API_KEY", "").strip()
    if api_key:
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
        for query in SEARCH_QUERIES:
            try:
                response = requests.post(
                    "https://google.serper.dev/search",
                    headers=headers,
                    json={"q": query, "tbs": "qdr:d3", "gl": "tr", "hl": "tr", "num": 20},
                    timeout=12,
                )
                if response.status_code in {401, 403}:
                    break
                if response.status_code != 200:
                    continue
                source_available = True
                consume(response.json().get("organic", []))
            except (requests.RequestException, ValueError):
                continue

    # Ücretsiz ve anahtarsız yedek: Google News'in X gönderisi indeksi.
    # Başlık/guid tekilleştirilir; guid burada benzersiz gönderi-kaynağı olarak kullanılır.
    if not source_available:
        for query in SEARCH_QUERIES[:-1]:
            try:
                response = requests.get(
                    "https://news.google.com/rss/search",
                    params={"q": f"{query} when:3d", "hl": "tr", "gl": "TR", "ceid": "TR:tr"},
                    headers={"User-Agent": "Mozilla/5.0 (compatible; TEFASAlert/1.0)"},
                    timeout=12,
                )
                if response.status_code != 200:
                    continue
                source_available = True
                soup = BeautifulSoup(response.text, "xml")
                rss_results = []
                for item in soup.find_all("item"):
                    title = item.title.get_text(" ", strip=True) if item.title else ""
                    link = item.link.get_text(strip=True) if item.link else ""
                    guid = item.guid.get_text(strip=True) if item.guid else link
                    rss_results.append({
                        "title": re.sub(r"\s+-\s+x\.com$", "", title, flags=re.IGNORECASE),
                        "snippet": "", "link": link, "source_id": f"rss:{guid}",
                    })
                consume(rss_results)
            except (requests.RequestException, ValueError):
                continue

    normalized: dict[str, dict[str, Any]] = {}
    for code, row in aggregates.items():
        normalized[code] = {key: value for key, value in row.items() if key != "accounts"}
        normalized[code]["unique_accounts"] = len(row["accounts"])
    return normalized, source_available


def score_social_candidate(
    observation: dict[str, Any],
    technical: dict[str, Any],
    baseline_mentions: float | None,
    investor_percentile: float,
) -> dict[str, float]:
    """Return bounded, explainable social-score components in the 0-100 range."""
    mentions = int(observation.get("mention_count") or 0)
    accounts = int(observation.get("unique_accounts") or 0)
    positive = int(observation.get("positive_count") or 0)
    negative = int(observation.get("negative_count") or 0)
    hype = int(observation.get("hype_count") or 0)
    analytical = int(observation.get("analytical_count") or 0)
    trusted = int(observation.get("trusted_count") or 0)

    if mentions <= 0:
        acceleration = diversity = sentiment = quality = 0.0
    else:
        baseline = max(float(baseline_mentions or 0), 0.0)
        acceleration = 50.0 + 25.0 * ((mentions - baseline) / max(baseline, 1.0))
        diversity = 100.0 * (accounts / mentions) * min(1.0, mentions / 3.0)
        sentiment = 50.0 + 40.0 * ((positive - negative) / mentions)
        quality = 60.0 * (analytical / mentions) + 40.0 * (trusted / mentions)

    momentum = float(technical.get("momentum_score") or 0)
    trend = float(technical.get("trend_score") or 0)
    flow = float(technical.get("flow_score") or 0)
    technical_score = momentum * 0.60 + trend * 0.40
    confirmation = technical_score * 0.45 + flow * 0.35 + investor_percentile * 0.20
    score = (
        _clamp(acceleration) * 0.30
        + _clamp(diversity) * 0.20
        + _clamp(sentiment) * 0.15
        + _clamp(confirmation) * 0.25
        + _clamp(quality) * 0.10
    )
    hype_ratio = hype / mentions if mentions else 0.0
    return {
        "score": _clamp(score), "acceleration_score": _clamp(acceleration),
        "diversity_score": _clamp(diversity), "sentiment_score": _clamp(sentiment),
        "confirmation_score": _clamp(confirmation), "quality_score": _clamp(quality),
        "technical_score": _clamp(technical_score), "flow_score": _clamp(flow),
        "hype_ratio": hype_ratio,
    }


def classify_radar_label(mentions: int, scores: dict[str, float]) -> str:
    confirmation = scores["confirmation_score"]
    if mentions >= 2 and scores["hype_ratio"] >= 0.50 and confirmation < 50:
        return "AŞIRI HYPE"
    if mentions >= 2 and scores["score"] >= 65 and confirmation >= 65:
        return "TEYİTLİ İLGİ"
    if mentions >= 2 and scores["score"] >= 50:
        return "ERKEN RADAR"
    if mentions == 0 and scores["technical_score"] >= 75 and scores["flow_score"] >= 60:
        return "SESSİZ YÜKSELİŞ"
    return "İZLE"


def _percentile_map(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda pair: pair[1])
    count = len(ordered)
    if not count:
        return {}
    return {code: (index + 1) / count * 100 for index, (code, _) in enumerate(ordered)}


def _latest_technical_rows(conn) -> tuple[str | None, dict[str, dict[str, Any]]]:
    as_of = conn.execute(
        "SELECT MAX(signal_date) FROM fund_features_daily WHERE strategy_version = ?",
        (STRATEGY_VERSION,),
    ).fetchone()[0]
    if not as_of:
        return None, {}
    rows = conn.execute(
        """
        SELECT ff.code, COALESCE(fn.name, ff.code), ff.category, ff.momentum_score,
               ff.trend_score, ff.flow_score, ff.investor_growth, ff.return_1m,
               COALESCE(pm.tefas_status, 'BİLİNMİYOR')
        FROM fund_features_daily ff
        LEFT JOIN fund_names fn ON fn.code = ff.code
        LEFT JOIN fund_platform_metadata pm ON pm.code = ff.code
        WHERE ff.signal_date = ? AND ff.strategy_version = ?
          AND ff.category <> 'Para Piyasası'
        """,
        (as_of, STRATEGY_VERSION),
    ).fetchall()
    return as_of, {
        str(row[0]): {
            "code": row[0], "name": row[1], "category": row[2],
            "momentum_score": row[3], "trend_score": row[4], "flow_score": row[5],
            "investor_growth": row[6], "return_1m": row[7], "tefas_status": row[8],
        }
        for row in rows
    }


def _mention_baselines(conn, scan_date: str) -> dict[str, float]:
    rows = conn.execute(
        """
        SELECT code, AVG(mention_count)
        FROM social_momentum_daily
        WHERE scan_date IN (
            SELECT DISTINCT scan_date FROM social_momentum_daily
            WHERE scan_date < ? ORDER BY scan_date DESC LIMIT 7
        )
        GROUP BY code
        """,
        (scan_date,),
    ).fetchall()
    return {str(code): float(value or 0) for code, value in rows}


def build_social_momentum_radar(limit: int = 10, scan_date: str | None = None) -> dict[str, Any]:
    """Build and persist a daily radar without mutating the weekly trade model."""
    scan_date = scan_date or datetime.now(ZoneInfo("Europe/Istanbul")).strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        as_of_date, technical_rows = _latest_technical_rows(conn)
        if not technical_rows:
            return {"scan_date": scan_date, "as_of_date": as_of_date, "radar": [], "source_available": False}
        observations, source_available = fetch_x_observations(set(technical_rows))
        baselines = _mention_baselines(conn, scan_date)
        investor_values = {
            code: float(row.get("investor_growth") or 0) for code, row in technical_rows.items()
        }
        investor_ranks = _percentile_map(investor_values)
        technical_top = sorted(
            technical_rows,
            key=lambda code: float(technical_rows[code].get("momentum_score") or 0) * 0.60
            + float(technical_rows[code].get("trend_score") or 0) * 0.40,
            reverse=True,
        )[:40]
        # "Sessiz" etiketi ancak X kaynağı gerçekten tarandıysa anlamlıdır.
        candidate_codes = (set(observations) | set(technical_top)) if source_available else set()
        radar: list[dict[str, Any]] = []
        for code in candidate_codes:
            technical = technical_rows[code]
            observation = observations.get(code, {})
            scores = score_social_candidate(
                observation, technical, baselines.get(code), investor_ranks.get(code, 0),
            )
            mentions = int(observation.get("mention_count") or 0)
            label = classify_radar_label(mentions, scores)
            if label == "İZLE" and mentions == 0:
                continue
            row = {
                **technical, **scores, "label": label, "mention_count": mentions,
                "unique_accounts": int(observation.get("unique_accounts") or 0),
                "positive_count": int(observation.get("positive_count") or 0),
                "negative_count": int(observation.get("negative_count") or 0),
                "hype_count": int(observation.get("hype_count") or 0),
                "examples": observation.get("examples") or [],
                "tefas_url": tefas_fund_url(code),
            }
            row["reason"] = {
                "TEYİTLİ İLGİ": "Sosyal ilgi teknik trend ve para akışıyla teyitli.",
                "ERKEN RADAR": "İlgi hızlanıyor; teknik teyit henüz tamamlanmadı.",
                "SESSİZ YÜKSELİŞ": "Teknik ve para akışı güçlü; sosyal kalabalık henüz düşük.",
                "AŞIRI HYPE": "Sosyal heyecan yüksek; teknik/akış teyidi zayıf.",
            }.get(label, "İzlenebilir sosyal hareketlilik var.")
            radar.append(row)

        label_priority = {"TEYİTLİ İLGİ": 4, "SESSİZ YÜKSELİŞ": 3, "ERKEN RADAR": 2, "AŞIRI HYPE": 1, "İZLE": 0}
        radar.sort(
            key=lambda row: (label_priority.get(row["label"], 0), row["score"], row["confirmation_score"]),
            reverse=True,
        )
        for rank, row in enumerate(radar, 1):
            row["rank"] = rank
            for key in (
                "score", "acceleration_score", "diversity_score", "sentiment_score",
                "confirmation_score", "quality_score", "technical_score", "flow_score",
            ):
                row[key] = round(float(row[key]), 1)
        save_social_momentum(scan_date, as_of_date or scan_date, radar)
        payload = {
            "scan_date": scan_date, "as_of_date": as_of_date, "strategy_version": "social-momentum-v1",
            "source_available": source_available, "radar": radar[:limit],
            "policy": "Sosyal veri ana AL/TUT/SAT skorunu değiştirmez.",
        }
        return payload
    finally:
        conn.close()
