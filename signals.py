"""Deterministic weekly TEFAS momentum and rotation engine.

The engine deliberately separates signal generation from natural-language AI.
Every recommendation is reproducible from the stored strategy version, config,
features and as-of date.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd
import requests

from config import DB_PATH
from database import get_connection, init_db


STRATEGY_VERSION = "tefas-momentum-rotation-v3-aum-flow"

DEFAULT_CONFIG: dict[str, Any] = {
    "rebalance_trading_days": 5,
    "max_positions": 10,
    "excluded_candidate_categories": ["Para Piyasası"],
    "minimum_history": 252,
    "minimum_market_cap": 50_000_000,
    "minimum_investors": 50,
    "emerging_min_history": 64,
    "emerging_developing_history": 127,
    "emerging_max_history": 251,
    "emerging_min_market_cap": 75_000_000,
    "emerging_min_investors": 250,
    "emerging_min_flow_persistence": 0.60,
    # PPF'nin yaklaşık aylık %3,5 getirisine karşı anlamlı ek getiri marjı.
    # Yeni alım ve model risk sepetleri son bir ayda en az %5 ister.
    "minimum_monthly_return": 0.05,
    "entry_score": 72.0,
    "hold_score": 50.0,
    "exit_score": 45.0,
    "max_recent_single_day_move": 0.50,
    "transaction_cost_rate": 0.0015,
    "annual_risk_free_rate": 0.40,
    "weights": {
        "momentum": 0.30,
        "trend": 0.20,
        "risk": 0.20,
        "flow": 0.15,
        "regime": 0.10,
        "liquidity": 0.05,
    },
}


def signal_strength(score: float) -> str:
    """Fırsat puanını kullanıcıya okunabilir, eylemden bağımsız bir banda çevir."""
    if score >= 90:
        return "ÇOK GÜÇLÜ"
    if score >= 82:
        return "GÜÇLÜ"
    if score >= 72:
        return "POZİTİF"
    if score >= 50:
        return "NÖTR"
    return "ZAYIF"


def trade_signal(status: str, score: float) -> str:
    """Teknik durumu, gücü belirtilmiş ve kolay okunur işlem etiketine çevir."""
    if status == "ALIM_ADAYI":
        return "GÜÇLÜ AL" if score >= 82 else "AL"
    if status == "TUT":
        return "TUT"
    return "GÜÇLÜ SAT" if score < 35 else "SAT"


def tefas_fund_url(code: str) -> str:
    return f"https://www.tefas.gov.tr/tr/fon-detayli-analiz/{(code or '').upper()}"


def infer_founder(name: str) -> str:
    """Fon unvanındaki PORTFÖY ibaresinden kurucu şirket adını türet."""
    upper_name = (name or "").upper().strip()
    company_match = re.match(r"^(.+?\bA\.Ş\.)\s+", upper_name)
    if company_match and any(label in company_match.group(1) for label in ("EMEKLİLİK", "HAYAT")):
        return company_match.group(1).strip()
    prefix = upper_name.split(" PORTFÖY", 1)[0].strip()
    if not prefix or prefix == upper_name:
        return "BİLİNMİYOR"
    return f"{prefix} PORTFÖY YÖNETİMİ A.Ş."


def resolve_founder(official_founder: str | None, name: str) -> str:
    if official_founder and official_founder.strip().upper() != "BİLİNMİYOR":
        return official_founder
    return infer_founder(name)


def infer_tefas_status(code: str, name: str, investor_count: int | None = None) -> str:
    """Projede kullanılan isim/yatırımcı kurallarıyla işlem platformunu tahmin et."""
    code_upper = (code or "").upper()
    name_upper = (name or "").upper()
    if any(label in name_upper for label in ("EMEKLİLİK", "EYF", "E.Y.F.")):
        return "BEFAS"
    if "EMK" in name_upper.replace("TEMKİN", ""):
        return "BEFAS"
    always_open = {"BMU", "KLH", "TTA", "TLY", "ZPR", "PPS", "KSV", "KLU", "DZM", "DPB", "DIP", "AES"}
    if code_upper in always_open:
        return "AÇIK"
    if "ÖZEL" in name_upper or "MÜNFERİT" in name_upper:
        return "KAPALI"
    if "SERBEST" not in name_upper:
        return "AÇIK"
    return "AÇIK" if investor_count is not None and investor_count > 100 else "KAPALI"


def _normalize_official_tefas_status(value: str) -> str:
    normalized = value.strip()
    folded = normalized.casefold()
    if "alımına kapalı" in folded and "bozumuna açık" in folded:
        return "ALIMA KAPALI / BOZUMA AÇIK"
    if "görmüyor" in folded:
        return "İŞLEM GÖRMÜYOR"
    if "görüyor" in folded:
        return "İŞLEM GÖRÜYOR"
    return normalized.upper()


def is_tefas_buyable(status: str | None) -> bool:
    if not status:
        return False
    return _normalize_official_tefas_status(status) in {"İŞLEM GÖRÜYOR", "AÇIK"}


def unavailable_signal(status: str | None) -> str:
    if status == "ALIMA KAPALI / BOZUMA AÇIK":
        return "ALIMA KAPALI"
    return "TEFAS DIŞI"


def classify_tefas_risk(value: int | None) -> str | None:
    """Resmî 1-7 ölçeğini portföy politikamızın dört risk bandına çevir."""
    if value is None or value < 1 or value > 7:
        return None
    if value <= 2:
        return "DÜŞÜK"
    if value <= 4:
        return "ORTA"
    if value <= 6:
        return "YÜKSEK"
    return "ÇOK YÜKSEK"


def _fetch_official_tefas_profile(code: str) -> tuple[str | None, int | None]:
    url = tefas_fund_url(code)
    last_error: requests.RequestException | None = None
    for _ in range(3):
        try:
            response = requests.get(
                url,
                timeout=12,
                headers={"User-Agent": "Mozilla/5.0 (compatible; TEFASAlert/1.0)"},
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            last_error = exc
            continue
        status_match = re.search(r'tefasDurum\\?":\\?"([^"\\]+)', response.text)
        risk_match = re.search(r'riskDegeri\\?":\\?"?([1-7])', response.text)
        status = _normalize_official_tefas_status(status_match.group(1)) if status_match else None
        risk_value = int(risk_match.group(1)) if risk_match else None
        if status is not None or risk_value is not None:
            return status, risk_value
    if last_error:
        raise last_error
    return None, None


def refresh_platform_metadata(
    conn: sqlite3.Connection,
    funds: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """Resmî TEFAS profil durumlarını paralel çek; hata halinde eski önbelleği koru."""
    fetched: dict[str, tuple[str | None, int | None]] = {}
    with ThreadPoolExecutor(max_workers=min(12, max(1, len(funds)))) as executor:
        futures = {executor.submit(_fetch_official_tefas_profile, code): code for code in funds}
        for future in as_completed(futures):
            code = futures[future]
            try:
                profile = future.result()
            except (requests.RequestException, ValueError):
                profile = (None, None)
            if any(value is not None for value in profile):
                fetched[code] = profile

    if fetched:
        conn.executemany(
            """
            INSERT INTO fund_platform_metadata (
                code, founder, tefas_status, tefas_risk_value, source, checked_at
            )
            VALUES (?, ?, ?, ?, 'tefas_official_profile', datetime('now','localtime'))
            ON CONFLICT(code) DO UPDATE SET
                founder = excluded.founder,
                tefas_status = COALESCE(excluded.tefas_status, fund_platform_metadata.tefas_status),
                tefas_risk_value = COALESCE(excluded.tefas_risk_value, fund_platform_metadata.tefas_risk_value),
                source = excluded.source,
                checked_at = excluded.checked_at
            """,
            [
                (code, infer_founder(funds[code]), profile[0], profile[1])
                for code, profile in fetched.items()
            ],
        )
        conn.commit()

    placeholders = ",".join("?" for _ in funds)
    if not placeholders:
        return {}
    rows = conn.execute(
        f"""SELECT code, founder, tefas_status, tefas_risk_value, source, checked_at
            FROM fund_platform_metadata WHERE code IN ({placeholders})""",
        list(funds),
    ).fetchall()
    return {
        str(row[0]): {
            "founder": row[1],
            "tefas_status": _normalize_official_tefas_status(str(row[2])) if row[2] else None,
            "tefas_risk_value": _int(row[3]),
            "tefas_risk_band": classify_tefas_risk(_int(row[3])),
            "tefas_status_source": row[4],
            "tefas_status_checked_at": row[5],
        }
        for row in rows
    }


def classify_category(name: str) -> str:
    n = (name or "").upper()
    if "GİRİŞİM" in n or "GIRISIM" in n or "GSYF" in n:
        return "Girişim Sermayesi"
    if "GAYRİMENKUL" in n or "GYF" in n:
        return "Gayrimenkul"
    if "HİSSE" in n or "HISSE" in n or "BİST" in n or "BIST" in n or "PAY" in n:
        return "Hisse Senedi"
    if "KATILIM" in n:
        return "Katılım"
    if "SERBEST" in n:
        return "Serbest"
    if "DEĞİŞKEN" in n or "DEGISKEN" in n:
        return "Değişken"
    if "PARA PİYASASI" in n or "PARA PIYASASI" in n or "LİKİT" in n or "LIKIT" in n:
        return "Para Piyasası"
    if any(k in n for k in ("BORÇLANMA", "BORCLANMA", "TAHVİL", "TAHVIL", "BONO", "EUROBOND", "ÖST")):
        return "Borçlanma Araçları"
    if "FON SEPETİ" in n or "FON SEPETI" in n:
        return "Fon Sepeti"
    if any(k in n for k in ("ALTIN", "KIYMETLİ", "KIYMETLI", "GÜMÜŞ", "GUMUS", "PLATİN", "PLATIN", "MADEN")):
        return "Kıymetli Madenler"
    if "KARMA" in n:
        return "Karma"
    if "ENDEKS" in n:
        return "Endeks"
    return "Diğer"


def estimate_valor(name: str) -> tuple[int, int]:
    n = (name or "").upper()
    if "PARA PİYASASI" in n or "PARA PIYASASI" in n or "LİKİT" in n or "LIKIT" in n:
        return 0, 0
    if "KISA VADELİ" in n or "KISA VADELI" in n:
        return 1, 1
    if any(k in n for k in ("YABANCI", "EUROBOND", "DIŞ", "DIS")):
        return 1, 3
    return 1, 2


@dataclass
class SignalPanels:
    dates: list[str]
    price: pd.DataFrame
    market_cap: pd.DataFrame
    investors: pd.DataFrame
    net_flow: pd.DataFrame
    names: dict[str, str]
    valid_count: pd.DataFrame
    returns: pd.DataFrame
    ema20: pd.DataFrame
    ema50: pd.DataFrame
    ema100: pd.DataFrame
    ema200: pd.DataFrame
    volatility63: pd.DataFrame
    drawdown126: pd.DataFrame
    flow_z20: pd.DataFrame
    flow_rate5: pd.DataFrame
    flow_rate20: pd.DataFrame
    flow_persistence20: pd.DataFrame
    investor_growth20: pd.DataFrame
    bad_jump252: pd.DataFrame


def _safe_pivot(data: pd.DataFrame, value: str, dates: list[str], codes: list[str]) -> pd.DataFrame:
    panel = data.pivot(index="date", columns="code", values=value)
    return panel.reindex(index=dates, columns=codes).astype(float)


def _aum_normalized_flow(
    net_flow: pd.DataFrame,
    market_cap: pd.DataFrame,
    winsorize: bool = True,
) -> pd.DataFrame:
    """Fiyat etkisinden arındırılmış TL akışını önceki gün fon büyüklüğüne böl."""
    previous_aum = market_cap.shift(1).where(market_cap.shift(1) > 0)
    rate = (net_flow / previous_aum).replace([np.inf, -np.inf], np.nan)
    if winsorize:
        lower = rate.quantile(0.01, axis=1)
        upper = rate.quantile(0.99, axis=1)
        rate = rate.clip(lower=lower, upper=upper, axis=0)
    return rate


def load_panels(conn: sqlite3.Connection, end_date: str | None = None, max_dates: int = 1000) -> SignalPanels:
    if end_date is None:
        end_date = conn.execute("SELECT MAX(date) FROM fund_daily").fetchone()[0]
    if not end_date:
        raise ValueError("Sinyal üretmek için fund_daily verisi bulunamadı")

    date_rows = conn.execute(
        """
        SELECT date FROM (
            SELECT DISTINCT date FROM fund_daily WHERE date <= ? ORDER BY date DESC LIMIT ?
        ) ORDER BY date ASC
        """,
        (end_date, max_dates),
    ).fetchall()
    dates = [row[0] for row in date_rows]
    if len(dates) < DEFAULT_CONFIG["minimum_history"] + 2:
        raise ValueError("En az 254 işlem günü veri gereklidir")

    placeholders = ",".join("?" for _ in dates)
    data = pd.read_sql_query(
        f"""
        SELECT fd.date, fd.code, fd.price, fd.market_cap, fd.num_investors,
               fd.net_flow, COALESCE(fn.name, 'Bilinmeyen Fon') AS name
        FROM fund_daily fd
        LEFT JOIN fund_names fn ON fn.code = fd.code
        WHERE fd.date IN ({placeholders})
        ORDER BY fd.date, fd.code
        """,
        conn,
        params=dates,
    )
    codes = sorted(data["code"].dropna().unique().tolist())
    names = (
        data.sort_values("date")
        .drop_duplicates("code", keep="last")
        .set_index("code")["name"]
        .fillna("Bilinmeyen Fon")
        .to_dict()
    )

    price = _safe_pivot(data, "price", dates, codes).where(lambda x: x > 0)
    market_cap = _safe_pivot(data, "market_cap", dates, codes)
    investors = _safe_pivot(data, "num_investors", dates, codes)
    net_flow = _safe_pivot(data, "net_flow", dates, codes)
    returns = price.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    flow_rate = _aum_normalized_flow(net_flow, market_cap)
    flow_rate5 = flow_rate.rolling(5, min_periods=3).sum()
    flow_rate20 = flow_rate.rolling(20, min_periods=10).sum()
    flow_persistence20 = (
        (flow_rate > 0).where(flow_rate.notna()).rolling(20, min_periods=10).mean()
    )
    flow_z20 = (
        flow_rate5 - flow_rate5.shift(1).rolling(63, min_periods=30).mean()
    ) / flow_rate5.shift(1).rolling(63, min_periods=30).std().replace(0, np.nan)

    return SignalPanels(
        dates=dates,
        price=price,
        market_cap=market_cap,
        investors=investors,
        net_flow=net_flow,
        names=names,
        valid_count=price.notna().cumsum(),
        returns=returns,
        ema20=price.ewm(span=20, min_periods=12, adjust=False).mean(),
        ema50=price.ewm(span=50, min_periods=30, adjust=False).mean(),
        ema100=price.ewm(span=100, min_periods=60, adjust=False).mean(),
        ema200=price.ewm(span=200, min_periods=126, adjust=False).mean(),
        volatility63=returns.rolling(63, min_periods=40).std() * math.sqrt(252),
        drawdown126=price / price.rolling(126, min_periods=60).max() - 1,
        flow_z20=flow_z20,
        flow_rate5=flow_rate5,
        flow_rate20=flow_rate20,
        flow_persistence20=flow_persistence20,
        investor_growth20=investors / investors.shift(20) - 1,
        bad_jump252=(returns.abs() > DEFAULT_CONFIG["max_recent_single_day_move"])
        .rolling(252, min_periods=1)
        .sum(),
    )


def _global_percentile(
    frame: pd.DataFrame,
    column: str,
    universe_mask: pd.Series,
    ascending: bool = True,
) -> pd.Series:
    """PPF hariç uygun evrende, kategoriden bağımsız yüzdelik sıra üret."""
    result = pd.Series(np.nan, index=frame.index, dtype=float)
    result.loc[universe_mask] = (
        frame.loc[universe_mask, column].rank(pct=True, ascending=ascending) * 100
    )
    return result


def _value_at(panel: pd.DataFrame, idx: int) -> pd.Series:
    return panel.iloc[idx]


def score_snapshot(
    panels: SignalPanels,
    idx: int = -1,
    config: dict[str, Any] | None = None,
    include_reasons: bool = True,
) -> pd.DataFrame:
    config = config or DEFAULT_CONFIG
    if idx < 0:
        idx = len(panels.dates) + idx
    if idx < config["minimum_history"]:
        raise ValueError("Sinyal tarihi için yeterli geçmiş yok")

    current = _value_at(panels.price, idx)
    features = pd.DataFrame(index=panels.price.columns)
    features.index.name = "code"
    features["name"] = pd.Series(panels.names)
    features["category"] = features["name"].map(classify_category)
    features["price"] = current
    features["market_cap"] = _value_at(panels.market_cap, idx)
    features["num_investors"] = _value_at(panels.investors, idx)
    features["history_count"] = _value_at(panels.valid_count, idx)
    features["ema20"] = _value_at(panels.ema20, idx)
    features["ema50"] = _value_at(panels.ema50, idx)
    features["ema100"] = _value_at(panels.ema100, idx)
    features["ema200"] = _value_at(panels.ema200, idx)
    features["ema20_slope"] = features["ema20"] / _value_at(panels.ema20, idx - 10) - 1
    features["ema50_slope"] = features["ema50"] / _value_at(panels.ema50, idx - 20) - 1
    features["volatility_annual"] = _value_at(panels.volatility63, idx)
    features["drawdown_6m"] = _value_at(panels.drawdown126, idx)
    features["flow_zscore"] = _value_at(panels.flow_z20, idx)
    features["flow_5d_ratio"] = _value_at(panels.flow_rate5, idx)
    features["flow_20d_ratio"] = _value_at(panels.flow_rate20, idx)
    features["flow_persistence"] = _value_at(panels.flow_persistence20, idx)
    features["investor_growth"] = _value_at(panels.investor_growth20, idx)
    features["bad_jump_count"] = _value_at(panels.bad_jump252, idx).fillna(0)

    for label, offset in (("return_1m", 21), ("return_3m", 63), ("return_6m", 126), ("return_1y", 252)):
        features[label] = current / _value_at(panels.price, idx - offset) - 1
        features[label] = features[label].replace([np.inf, -np.inf], np.nan)

    required_returns = features[["return_1m", "return_3m", "return_6m", "return_1y"]].notna().all(axis=1)
    base_data_quality = (
        (features["history_count"] >= config["minimum_history"])
        & features["price"].notna()
        & (features["market_cap"] >= config["minimum_market_cap"])
        & (features["num_investors"] >= config["minimum_investors"])
        & (features["bad_jump_count"] == 0)
        & required_returns
    )
    global_universe = (
        base_data_quality
        & ~features["category"].isin(config.get("excluded_candidate_categories", []))
    )

    momentum_parts = []
    for label, weight in (("return_1m", 0.15), ("return_3m", 0.30), ("return_6m", 0.35), ("return_1y", 0.20)):
        rank_col = f"{label}_rank"
        features[rank_col] = _global_percentile(features, label, global_universe)
        momentum_parts.append(features[rank_col].fillna(0) * weight)
    features["momentum_score"] = sum(momentum_parts)

    above_ema50 = features["price"] > features["ema50"]
    ordered_emas = features["ema50"] > features["ema200"]
    positive_medium_trend = (features["return_3m"] > 0) & (features["return_6m"] > 0)
    features["trend_score"] = (
        above_ema50.astype(float) * 35
        + ordered_emas.astype(float) * 35
        + positive_medium_trend.astype(float) * 30
    )

    features["risk_adjusted_momentum"] = features["return_6m"] / features["volatility_annual"].replace(0, np.nan)
    risk_rank = _global_percentile(features, "risk_adjusted_momentum", global_universe)
    drawdown_rank = _global_percentile(features, "drawdown_6m", global_universe)
    features["risk_score"] = risk_rank.fillna(0) * 0.70 + drawdown_rank.fillna(0) * 0.30

    flow_20d_rank = _global_percentile(features, "flow_20d_ratio", global_universe).fillna(50)
    flow_5d_rank = _global_percentile(features, "flow_5d_ratio", global_universe).fillna(50)
    flow_persistence_rank = _global_percentile(features, "flow_persistence", global_universe).fillna(50)
    features["investor_rank"] = _global_percentile(features, "investor_growth", global_universe).fillna(50)
    features["flow_score"] = (
        flow_20d_rank * 0.40
        + flow_5d_rank * 0.25
        + flow_persistence_rank * 0.20
        + features["investor_rank"] * 0.15
    )

    global_regime_score = 100.0 if features.loc[global_universe, "return_3m"].median() > 0 else 25.0
    features["regime_score"] = np.where(global_universe, global_regime_score, 0.0)
    features["market_cap_rank"] = _global_percentile(features, "market_cap", global_universe).fillna(0)
    features["investor_count_rank"] = _global_percentile(features, "num_investors", global_universe).fillna(0)
    features["liquidity_score"] = features["market_cap_rank"] * 0.65 + features["investor_count_rank"] * 0.35

    valors = features["name"].map(estimate_valor)
    features["alis_valor"] = valors.map(lambda value: value[0])
    features["satis_valor"] = valors.map(lambda value: value[1])
    valor_penalty = ((features["alis_valor"] + features["satis_valor"] - 2).clip(lower=0) * 2.5).clip(upper=10)
    volatility_penalty = np.where(features["volatility_annual"] > 0.80, 8.0, 0.0)

    weights = config["weights"]
    features["score"] = (
        features["momentum_score"] * weights["momentum"]
        + features["trend_score"] * weights["trend"]
        + features["risk_score"] * weights["risk"]
        + features["flow_score"] * weights["flow"]
        + features["regime_score"] * weights["regime"]
        + features["liquidity_score"] * weights["liquidity"]
        - valor_penalty
        - volatility_penalty
    ).clip(0, 100)
    # Fırsat sırası özellikle momentumun devamı ve teyitli trendi öne çıkarır.
    # Bu bir getiri yüzdesi tahmini değil, 0-100 göreli potansiyel puanıdır.
    features["opportunity_score"] = (
        features["momentum_score"] * 0.55
        + features["trend_score"] * 0.30
        + features["flow_score"] * 0.10
        + features["risk_score"] * 0.05
    ).clip(0, 100)
    features["data_quality"] = base_data_quality
    features["volatility_percentile"] = (
        features["volatility_annual"].where(features["data_quality"]).rank(pct=True) * 100
    )
    features["risk_band"] = np.select(
        [
            features["volatility_percentile"] <= 33.33,
            features["volatility_percentile"] <= 66.67,
        ],
        ["DÜŞÜK", "ORTA"],
        default="YÜKSEK",
    )
    features["entry_gate"] = (
        features["data_quality"]
        & (features["score"] >= config["entry_score"])
        & (features["return_1m"] >= config["minimum_monthly_return"])
        & above_ema50
        & ordered_emas
        & positive_medium_trend
    )

    features["status"] = np.select(
        [
            features["entry_gate"],
            features["data_quality"] & (features["score"] >= config["hold_score"]) & (features["return_3m"] > 0),
        ],
        ["ALIM_ADAYI", "TUT"],
        default="CIKIS_ADAYI",
    )
    features["score"] = features["score"].round(2)
    features["opportunity_score"] = features["opportunity_score"].round(2)
    features["strength"] = features["opportunity_score"].map(signal_strength)
    features["signal"] = [
        trade_signal(str(status), float(score))
        for status, score in zip(features["status"], features["opportunity_score"])
    ]

    if include_reasons:
        features["reasons"] = [
            _build_reasons(row)
            for _, row in features.iterrows()
        ]
    else:
        features["reasons"] = [[] for _ in range(len(features))]
    return features.reset_index()


def _build_reasons(row: pd.Series) -> list[str]:
    reasons: list[str] = []
    if not bool(row.get("data_quality")):
        reasons.append("Veri kalitesi veya minimum likidite filtresini geçemedi")
    if pd.notna(row.get("return_6m")):
        reasons.append(f"6 aylık getiri %{row['return_6m'] * 100:.1f}")
    if pd.notna(row.get("return_1m")):
        reasons.append(f"1 aylık getiri %{row['return_1m'] * 100:.1f}")
    if row.get("price", 0) > row.get("ema50", float("inf")) and row.get("ema50", 0) > row.get("ema200", float("inf")):
        reasons.append("Fiyat > EMA50 > EMA200 trend yapısı pozitif")
    elif row.get("price", 0) < row.get("ema50", 0):
        reasons.append("Fiyat EMA50 altında; trend teyidi zayıf")
    if pd.notna(row.get("flow_zscore")):
        if row["flow_zscore"] >= 1:
            reasons.append(f"Para akışı güçlü (z={row['flow_zscore']:.2f})")
        elif row["flow_zscore"] <= -1:
            reasons.append(f"Para çıkışı baskısı var (z={row['flow_zscore']:.2f})")
    if pd.notna(row.get("flow_20d_ratio")):
        reasons.append(f"20 günlük büyüklük-normalize net akış %{row['flow_20d_ratio'] * 100:.2f}")
    if pd.notna(row.get("drawdown_6m")) and row["drawdown_6m"] <= -0.10:
        reasons.append(f"6 aylık zirveden düşüş %{row['drawdown_6m'] * 100:.1f}")
    return reasons[:4]


def select_rotation(features: pd.DataFrame, config: dict[str, Any] | None = None) -> pd.DataFrame:
    config = config or DEFAULT_CONFIG
    buyable = features.get("tefas_buyable", pd.Series(True, index=features.index)).fillna(False)
    monthly_return = features.get("return_1m", pd.Series(np.inf, index=features.index))
    candidates = features[
        features["data_quality"]
        & buyable
        & ~features["category"].isin(config.get("excluded_candidate_categories", []))
        & (features["score"] >= config["entry_score"])
        & (monthly_return >= config["minimum_monthly_return"])
        & (features["return_3m"] > 0)
        & (features["return_6m"] > 0)
        & (features["price"] > features["ema50"])
        & (features["ema50"] > features["ema200"])
    ].sort_values(["opportunity_score", "score"], ascending=False)

    selected = candidates.head(config["max_positions"]).copy().reset_index(drop=True)
    if selected.empty:
        return selected
    selected["rank"] = np.arange(1, len(selected) + 1)
    selected["target_weight"] = 1.0 / len(selected)
    return selected


def build_rotation_portfolio(
    features: pd.DataFrame,
    previous_codes: set[str],
    config: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, set[str]]:
    """Mevcut pozisyonları teknik koşullar bozulana kadar koru.

    Kategori yalnız analiz bilgisidir; ne mevcut pozisyonlara ne yeni girişlere
    kota uygulanır. Boşalan yerler fırsat puanı en yüksek uygun fonlarla dolar.
    """
    config = config or DEFAULT_CONFIG
    indexed = features.set_index("code", drop=False)
    retained: set[str] = set()
    technical_exits: set[str] = set()
    for code in previous_codes:
        if code not in indexed.index:
            technical_exits.add(code)
            continue
        row = indexed.loc[code]
        hold_ok = (
            bool(row["data_quality"])
            and float(row["score"]) >= config["exit_score"]
            and float(row["return_3m"]) > 0
            and float(row["price"]) > float(row["ema50"])
        )
        if hold_ok:
            retained.add(code)
        else:
            technical_exits.add(code)

    slots = max(0, config["max_positions"] - len(retained))
    buyable = features.get("tefas_buyable", pd.Series(True, index=features.index)).fillna(False)
    monthly_return = features.get("return_1m", pd.Series(np.inf, index=features.index))
    candidates = features[
        features["data_quality"]
        & buyable
        & ~features["category"].isin(config.get("excluded_candidate_categories", []))
        & (features["score"] >= config["entry_score"])
        & (monthly_return >= config["minimum_monthly_return"])
        & (features["return_3m"] > 0)
        & (features["return_6m"] > 0)
        & (features["price"] > features["ema50"])
        & (features["ema50"] > features["ema200"])
    ].sort_values(["opportunity_score", "score"], ascending=False)

    additions: list[str] = []
    if slots > 0:
        for _, row in candidates.iterrows():
            code = str(row["code"])
            if code in retained:
                continue
            additions.append(code)
            if len(additions) >= slots:
                break

    active_codes = retained | set(additions)
    if not active_codes:
        return features.head(0).copy(), technical_exits
    active = features[features["code"].isin(active_codes)].copy()
    active = active.sort_values(["opportunity_score", "score"], ascending=False).reset_index(drop=True)
    active["rank"] = np.arange(1, len(active) + 1)
    active["target_weight"] = 1.0 / len(active)
    return active, technical_exits


def build_signal_ranking(
    features: pd.DataFrame,
    limit: int = 50,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Kategori kotası olmadan, tüm uygun evreni fırsat puanına göre sırala."""
    config = config or DEFAULT_CONFIG
    ranked = (
        features[
            features["data_quality"]
            & ~features["category"].isin(config.get("excluded_candidate_categories", []))
        ]
        .assign(monthly_return_gate=lambda frame: frame["return_1m"] >= config["minimum_monthly_return"])
        .sort_values(
            ["monthly_return_gate", "opportunity_score", "momentum_score", "trend_score", "score"],
            ascending=False,
        )
        .head(limit)
        .reset_index(drop=True)
    )
    result: list[dict[str, Any]] = []
    for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
        result.append(
            {
                "rank": rank,
                "code": str(row["code"]),
                "tefas_url": tefas_fund_url(str(row["code"])),
                "name": str(row["name"]),
                "founder": infer_founder(str(row["name"])),
                "category": str(row["category"]),
                "tefas_status": infer_tefas_status(
                    str(row["code"]), str(row["name"]), _int(row["num_investors"])
                ),
                "tefas_status_estimated": True,
                "score": float(row["score"]),
                "opportunity_score": float(row["opportunity_score"]),
                "strength": str(row["strength"]),
                "technical_status": str(row["status"]),
                "signal": str(row["signal"]),
                "risk_band": str(row["risk_band"]),
                "momentum_score": _float(row["momentum_score"]),
                "trend_score": _float(row["trend_score"]),
                "risk_score": _float(row["risk_score"]),
                "flow_score": _float(row["flow_score"]),
                "return_1m": _float(row["return_1m"]),
                "monthly_return_gate": bool(row["monthly_return_gate"]),
                "return_3m": _float(row["return_3m"]),
                "return_6m": _float(row["return_6m"]),
                "return_1y": _float(row["return_1y"]),
            }
        )
    return result


def score_emerging_funds(
    features: pd.DataFrame,
    config: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """63-251 günlük fonları ana modelden bağımsız bir potansiyel radarında puanla."""
    config = config or DEFAULT_CONFIG
    history = features["history_count"]
    universe = (
        history.between(config["emerging_min_history"], config["emerging_max_history"])
        & features["price"].notna()
        & features["return_1m"].notna()
        & features["return_3m"].notna()
        & (features["market_cap"] >= config["emerging_min_market_cap"])
        & (features["num_investors"] >= config["emerging_min_investors"])
        & (features["bad_jump_count"] == 0)
        & ~features["category"].isin(config.get("excluded_candidate_categories", []))
    )
    if not bool(universe.any()):
        return features.head(0).copy()

    radar = features.loc[universe].copy()
    radar_mask = pd.Series(True, index=radar.index)
    developing = radar["history_count"] >= config["emerging_developing_history"]
    radar["radar_tier"] = np.where(developing, "GELİŞEN", "ERKEN")

    r1_rank = _global_percentile(radar, "return_1m", radar_mask)
    r3_rank = _global_percentile(radar, "return_3m", radar_mask)
    r6_rank = _global_percentile(radar, "return_6m", radar_mask)
    early_momentum = r1_rank * (0.20 / 0.55) + r3_rank * (0.35 / 0.55)
    developing_momentum = r1_rank * 0.20 + r3_rank * 0.35 + r6_rank.fillna(0) * 0.45
    radar["radar_momentum_score"] = np.where(developing, developing_momentum, early_momentum)

    early_trend = (
        (radar["price"] > radar["ema20"]).astype(float) * 35
        + (radar["ema20"] > radar["ema50"]).astype(float) * 35
        + (radar["ema20_slope"] > 0).astype(float) * 15
        + (radar["ema50_slope"] > 0).astype(float) * 15
    )
    developing_trend = (
        (radar["price"] > radar["ema20"]).astype(float) * 20
        + (radar["ema20"] > radar["ema50"]).astype(float) * 25
        + (radar["ema50"] > radar["ema100"]).astype(float) * 30
        + (radar["ema50_slope"] > 0).astype(float) * 25
    )
    radar["radar_trend_score"] = np.where(developing, developing_trend, early_trend)

    flow20_rank = _global_percentile(radar, "flow_20d_ratio", radar_mask).fillna(50)
    flow5_rank = _global_percentile(radar, "flow_5d_ratio", radar_mask).fillna(50)
    persistence_rank = _global_percentile(radar, "flow_persistence", radar_mask).fillna(50)
    investor_rank = _global_percentile(radar, "investor_growth", radar_mask).fillna(50)
    radar["radar_flow_score"] = (
        flow20_rank * 0.40 + flow5_rank * 0.25 + persistence_rank * 0.20 + investor_rank * 0.15
    )

    radar_return = radar["return_6m"].where(developing, radar["return_3m"])
    radar["radar_risk_adjusted"] = radar_return / radar["volatility_annual"].replace(0, np.nan)
    risk_rank = _global_percentile(radar, "radar_risk_adjusted", radar_mask).fillna(0)
    drawdown_rank = _global_percentile(radar, "drawdown_6m", radar_mask).fillna(0)
    liquidity_score = (
        _global_percentile(radar, "market_cap", radar_mask).fillna(0) * 0.60
        + _global_percentile(radar, "num_investors", radar_mask).fillna(0) * 0.40
    )
    radar["radar_risk_liquidity_score"] = (
        (risk_rank * 0.70 + drawdown_rank * 0.30) * 0.60 + liquidity_score * 0.40
    )
    radar["radar_confidence"] = (radar["history_count"] / config["minimum_history"] * 100).clip(0, 100)
    confidence_penalty = (1 - radar["radar_confidence"] / 100) * 10
    radar["radar_score"] = (
        radar["radar_momentum_score"] * 0.45
        + radar["radar_trend_score"] * 0.25
        + radar["radar_flow_score"] * 0.20
        + radar["radar_risk_liquidity_score"] * 0.10
        - confidence_penalty
    ).clip(0, 100)

    gates = (
        (radar["return_1m"] >= config["minimum_monthly_return"])
        & (radar["return_3m"] > 0)
        & (radar["radar_trend_score"] >= 70)
        & (radar["flow_persistence"] >= config["emerging_min_flow_persistence"])
        & (~developing | (radar["return_6m"].notna() & (radar["return_6m"] > 0)))
    )
    radar = radar.loc[gates].copy()
    radar["radar_signal"] = np.select(
        [
            radar["radar_tier"].eq("ERKEN"),
            radar["radar_score"] >= 90,
            radar["radar_score"] >= 82,
        ],
        ["ERKEN İZLE", "GÜÇLÜ POTANSİYEL", "POTANSİYEL AL"],
        default="İZLE",
    )
    radar = radar.sort_values(
        ["radar_score", "radar_momentum_score", "radar_flow_score"], ascending=False
    ).reset_index()
    radar["radar_rank"] = np.arange(1, len(radar) + 1)
    return radar


def _emerging_radar_records(radar: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for _, row in radar.iterrows():
        records.append(
            {
                "rank": int(row["radar_rank"]),
                "code": str(row["code"]),
                "tefas_url": tefas_fund_url(str(row["code"])),
                "name": str(row["name"]),
                "category": str(row["category"]),
                "tier": str(row["radar_tier"]),
                "signal": str(row["radar_signal"]),
                "score": round(float(row["radar_score"]), 2),
                "confidence": round(float(row["radar_confidence"]), 2),
                "history_days": int(row["history_count"]),
                "momentum_score": round(float(row["radar_momentum_score"]), 2),
                "trend_score": round(float(row["radar_trend_score"]), 2),
                "flow_score": round(float(row["radar_flow_score"]), 2),
                "risk_liquidity_score": round(float(row["radar_risk_liquidity_score"]), 2),
                "return_1m": _float(row["return_1m"]),
                "return_3m": _float(row["return_3m"]),
                "return_6m": _float(row["return_6m"]),
                "flow_5d_ratio": _float(row["flow_5d_ratio"]),
                "flow_20d_ratio": _float(row["flow_20d_ratio"]),
                "flow_persistence": _float(row["flow_persistence"]),
                "market_cap": _float(row["market_cap"]),
                "num_investors": _int(row["num_investors"]),
            }
        )
    return records


def build_risk_portfolios(features: pd.DataFrame, limit: int = 10) -> dict[str, list[dict[str, Any]]]:
    """Orta ve yüksek oynaklık profilleri için kategori kotasız aday listeleri."""
    ranking = build_signal_ranking(features, limit=len(features))
    return _risk_portfolios_from_ranking(ranking, limit=limit)


def _apply_portfolio_context(
    ranking: list[dict[str, Any]],
    previous_codes: set[str],
    selected_codes: set[str],
    technical_exit_codes: set[str],
) -> None:
    """Saf fırsat sırasını değiştirmeden mevcut portföy eylemini etikete yansıt."""
    for item in ranking:
        code = str(item["code"])
        if code in technical_exit_codes:
            item["portfolio_action"] = "CIKIS_ADAYI"
            item["signal"] = trade_signal("CIKIS_ADAYI", float(item["opportunity_score"]))
        elif code in previous_codes and code in selected_codes:
            item["portfolio_action"] = "TUT"
            item["signal"] = "TUT"
        elif code in selected_codes:
            item["portfolio_action"] = "ALIM_ADAYI"
        else:
            item["portfolio_action"] = None
            if not is_tefas_buyable(item.get("tefas_status")):
                item["signal"] = unavailable_signal(item.get("tefas_status"))


def _previous_rotation(conn: sqlite3.Connection, signal_date: str) -> dict[str, str]:
    previous_date = conn.execute(
        "SELECT MAX(signal_date) FROM signal_runs WHERE signal_date < ? AND strategy_version = ? AND status = 'SUCCESS'",
        (signal_date, STRATEGY_VERSION),
    ).fetchone()[0]
    if not previous_date:
        return {}
    rows = conn.execute(
        """
        SELECT code, action FROM rotation_recommendations
        WHERE signal_date = ? AND strategy_version = ? AND target_weight > 0
        """,
        (previous_date, STRATEGY_VERSION),
    ).fetchall()
    return {row[0]: row[1] for row in rows}


def is_rotation_due(conn: sqlite3.Connection, signal_date: str, config: dict[str, Any]) -> bool:
    previous_date = conn.execute(
        "SELECT MAX(signal_date) FROM signal_runs WHERE strategy_version = ? AND status = 'SUCCESS'",
        (STRATEGY_VERSION,),
    ).fetchone()[0]
    if not previous_date:
        return True
    trading_days = conn.execute(
        "SELECT COUNT(DISTINCT date) FROM fund_daily WHERE date > ? AND date <= ?",
        (previous_date, signal_date),
    ).fetchone()[0]
    return trading_days >= config["rebalance_trading_days"]


def run_weekly_rotation(
    signal_date: str | None = None,
    force: bool = False,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = {**DEFAULT_CONFIG, **(config or {})}
    init_db()
    conn = get_connection()
    if signal_date is None:
        signal_date = conn.execute("SELECT MAX(date) FROM fund_daily").fetchone()[0]
    if not signal_date:
        conn.close()
        raise ValueError("Sinyal tarihi bulunamadı")
    if not force and not is_rotation_due(conn, signal_date, config):
        conn.close()
        latest = get_latest_rotation()
        return {"generated": False, "reason": "weekly_rebalance_not_due", **latest}

    panels = load_panels(conn, end_date=signal_date, max_dates=400)
    features = score_snapshot(panels, config=config)
    eligible = features[features["data_quality"]].copy()
    previous = _previous_rotation(conn, signal_date)
    previous_codes = set(previous)
    feature_map = features.set_index("code").to_dict("index")
    all_ranking = build_signal_ranking(features, limit=len(features), config=config)
    emerging_df = score_emerging_funds(features, config=config)
    emerging_codes = set(emerging_df.head(50)["code"].astype(str).tolist()) if not emerging_df.empty else set()
    metadata_codes = {str(item["code"]) for item in all_ranking[:50]} | previous_codes | emerging_codes
    metadata = refresh_platform_metadata(
        conn,
        {
            code: str(feature_map.get(code, {}).get("name", ""))
            for code in metadata_codes
        },
    )
    features["tefas_buyable"] = [
        is_tefas_buyable(
            metadata.get(str(row["code"]), {}).get("tefas_status")
            or infer_tefas_status(str(row["code"]), str(row["name"]), _int(row["num_investors"]))
        )
        for _, row in features.iterrows()
    ]
    selected, technical_exit_codes = build_rotation_portfolio(features, previous_codes, config)
    selected_codes = set(selected["code"].tolist())
    feature_map = features.set_index("code").to_dict("index")
    for item in all_ranking:
        item["model_risk_band"] = item.get("risk_band")
        official = metadata.get(str(item["code"]))
        if official:
            item.update(official)
            item["risk_band"] = official.get("tefas_risk_band") or item["model_risk_band"]
            item["tefas_status_estimated"] = False
    _apply_portfolio_context(all_ranking, previous_codes, selected_codes, technical_exit_codes)
    ranking = all_ranking[:50]
    risk_portfolios = _risk_portfolios_from_ranking(all_ranking, limit=10)
    emerging_radar = _emerging_radar_records(emerging_df)
    for item in emerging_radar:
        official = metadata.get(str(item["code"]), {})
        item["founder"] = official.get("founder") or infer_founder(str(item.get("name") or ""))
        item["tefas_status"] = official.get("tefas_status") or infer_tefas_status(
            str(item["code"]), str(item.get("name") or ""), _int(item.get("num_investors"))
        )
        item["tefas_status_estimated"] = not bool(official)
        item["tefas_risk_value"] = official.get("tefas_risk_value")
        item["risk_band"] = official.get("tefas_risk_band") or "BİLİNMİYOR"
        if not is_tefas_buyable(item["tefas_status"]):
            item["signal"] = unavailable_signal(item["tefas_status"])

    selected_map = selected.set_index("code").to_dict("index") if not selected.empty else {}
    recommendations: list[dict[str, Any]] = []
    for code in sorted(selected_codes | technical_exit_codes):
        row = selected_map.get(code) or feature_map.get(code) or {}
        if code in selected_codes:
            action = "TUT" if code in previous_codes else "ALIM_ADAYI"
            target_weight = float(selected_map[code]["target_weight"])
            rank = int(selected_map[code]["rank"])
        elif code in technical_exit_codes:
            action = "CIKIS_ADAYI"
            target_weight = 0.0
            rank = None
        else:
            continue
        recommendations.append(
            {
                "code": code,
                "tefas_url": tefas_fund_url(code),
                "action": action,
                "founder": resolve_founder(metadata.get(code, {}).get("founder"), str(row.get("name", ""))),
                "rank": rank,
                "score": float(row.get("score", 0)),
                "opportunity_score": float(row.get("opportunity_score", 0)),
                "strength": signal_strength(float(row.get("opportunity_score", 0))),
                "signal": trade_signal(action, float(row.get("opportunity_score", 0))),
                "model_risk_band": str(row.get("risk_band", "BİLİNMİYOR")),
                "tefas_risk_value": metadata.get(code, {}).get("tefas_risk_value"),
                "risk_band": metadata.get(code, {}).get("tefas_risk_band")
                or str(row.get("risk_band", "BİLİNMİYOR")),
                "tefas_status": metadata.get(code, {}).get("tefas_status")
                or infer_tefas_status(code, str(row.get("name", "")), _int(row.get("num_investors"))),
                "tefas_status_estimated": code not in metadata,
                "tefas_status_source": metadata.get(code, {}).get("tefas_status_source", "estimated_rules"),
                "tefas_status_checked_at": metadata.get(code, {}).get("tefas_status_checked_at"),
                "target_weight": target_weight,
                "category": str(row.get("category", "Bilinmeyen")),
                "reasons": row.get("reasons", ["Teknik tut koşulları geçersizleşti"]),
            }
        )

    previous_status_rows = conn.execute(
        """
        SELECT fs.code, fs.status FROM fund_signals fs
        JOIN (
            SELECT code, MAX(signal_date) AS d FROM fund_signals
            WHERE signal_date < ? AND strategy_version = ? GROUP BY code
        ) p
          ON p.code = fs.code AND p.d = fs.signal_date
        WHERE fs.strategy_version = ?
        """,
        (signal_date, STRATEGY_VERSION, STRATEGY_VERSION),
    ).fetchall()
    previous_status = {row[0]: row[1] for row in previous_status_rows}

    conn.execute("BEGIN")
    for table in ("fund_features_daily", "fund_signals", "rotation_recommendations", "emerging_fund_radar"):
        conn.execute(
            f"DELETE FROM {table} WHERE signal_date = ? AND strategy_version = ?",
            (signal_date, STRATEGY_VERSION),
        )
    conn.execute(
        "DELETE FROM signal_runs WHERE signal_date = ? AND strategy_version = ?",
        (signal_date, STRATEGY_VERSION),
    )

    for _, row in features.iterrows():
        details = {
            "name": row["name"],
            "history_count": int(row["history_count"]),
            "bad_jump_count": int(row["bad_jump_count"]),
            "strength": str(row["strength"]),
            "opportunity_score": float(row["opportunity_score"]),
            "risk_band": str(row["risk_band"]),
            "valor_source": "estimated_from_fund_name",
        }
        conn.execute(
            """
            INSERT INTO fund_features_daily (
                signal_date, code, strategy_version, category, score,
                momentum_score, trend_score, risk_score, flow_score, regime_score, liquidity_score,
                return_1m, return_3m, return_6m, return_1y, volatility_annual, drawdown_6m,
                flow_zscore, flow_5d_ratio, flow_20d_ratio, flow_persistence,
                investor_growth, ema50, ema200, market_cap, num_investors,
                alis_valor, satis_valor, data_quality, details_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                signal_date, row["code"], STRATEGY_VERSION, row["category"], float(row["score"]),
                _float(row["momentum_score"]), _float(row["trend_score"]), _float(row["risk_score"]),
                _float(row["flow_score"]), _float(row["regime_score"]), _float(row["liquidity_score"]),
                _float(row["return_1m"]), _float(row["return_3m"]), _float(row["return_6m"]),
                _float(row["return_1y"]), _float(row["volatility_annual"]), _float(row["drawdown_6m"]),
                _float(row["flow_zscore"]), _float(row["flow_5d_ratio"]),
                _float(row["flow_20d_ratio"]), _float(row["flow_persistence"]),
                _float(row["investor_growth"]), _float(row["ema50"]),
                _float(row["ema200"]), _float(row["market_cap"]), _int(row["num_investors"]),
                int(row["alis_valor"]), int(row["satis_valor"]), int(bool(row["data_quality"])),
                json.dumps(details, ensure_ascii=False),
            ),
        )

        code = str(row["code"])
        if code in selected_codes:
            status = "TUT" if code in previous_codes else "ALIM_ADAYI"
            rank = int(selected_map[code]["rank"])
            weight = float(selected_map[code]["target_weight"])
        elif code in previous_codes:
            status, rank, weight = "CIKIS_ADAYI", None, 0.0
        else:
            status, rank, weight = str(row["status"]), None, 0.0
        conn.execute(
            """
            INSERT INTO fund_signals (
                signal_date, code, strategy_version, status, previous_status, score, rank,
                target_weight, reasons_json, entry_window, invalidation_rule
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                signal_date, code, STRATEGY_VERSION, status, previous_status.get(code), float(row["score"]),
                rank, weight, json.dumps(row["reasons"], ensure_ascii=False),
                f"İlk uygun emir penceresi; tahmini alış valörü T+{int(row['alis_valor'])}",
                "Skor 45 altına iner, 3 aylık momentum negatife döner veya fiyat EMA50 altına inerse",
            ),
        )

    for rec in recommendations:
        conn.execute(
            """
            INSERT INTO rotation_recommendations (
                signal_date, code, strategy_version, action, rank, score,
                target_weight, category, reasons_json
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                signal_date, rec["code"], STRATEGY_VERSION, rec["action"], rec["rank"],
                rec["score"], rec["target_weight"], rec["category"],
                json.dumps(rec["reasons"], ensure_ascii=False),
            ),
        )

    for item in emerging_radar:
        conn.execute(
            """
            INSERT INTO emerging_fund_radar (
                signal_date, code, strategy_version, tier, signal, rank, score,
                confidence, history_days, momentum_score, trend_score, flow_score,
                risk_liquidity_score, reasons_json
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                signal_date, item["code"], STRATEGY_VERSION, item["tier"], item["signal"],
                item["rank"], item["score"], item["confidence"], item["history_days"],
                item["momentum_score"], item["trend_score"], item["flow_score"],
                item["risk_liquidity_score"], json.dumps([], ensure_ascii=False),
            ),
        )

    diagnostics = {
        "total_rows": len(features),
        "eligible_rows": len(eligible),
        "excluded_data_quality": int((~features["data_quality"]).sum()),
        "point_in_time_metadata": False,
        "valor_source": "estimated_from_fund_name",
    }
    conn.execute(
        """
        INSERT INTO signal_runs (
            signal_date, strategy_version, status, universe_count, selected_count,
            config_json, diagnostics_json
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            signal_date, STRATEGY_VERSION, "SUCCESS", len(eligible), len(selected),
            json.dumps(config, ensure_ascii=False), json.dumps(diagnostics, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()
    return {
        "generated": True,
        "signal_date": signal_date,
        "strategy_version": STRATEGY_VERSION,
        "universe_count": len(eligible),
        "selected_count": len(selected),
        "recommendations": recommendations,
        "ranking": ranking,
        "risk_portfolios": risk_portfolios,
        "emerging_radar": emerging_radar[:50],
        "diagnostics": diagnostics,
    }


def _float(value: Any) -> float | None:
    if value is None or pd.isna(value) or not np.isfinite(value):
        return None
    return float(value)


def _int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def get_latest_rotation() -> dict[str, Any]:
    init_db()
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM signal_runs WHERE strategy_version = ? AND status = 'SUCCESS' ORDER BY signal_date DESC LIMIT 1",
        (STRATEGY_VERSION,),
    ).fetchone()
    if not row:
        conn.close()
        return {"signal_date": None, "strategy_version": STRATEGY_VERSION, "recommendations": []}
    recs = conn.execute(
        """
        SELECT rr.*, fn.name, ff.momentum_score, ff.trend_score, ff.risk_score,
               ff.flow_score, ff.regime_score, ff.liquidity_score, ff.return_1m,
               ff.return_3m, ff.return_6m, ff.return_1y, ff.volatility_annual,
               ff.drawdown_6m, ff.flow_zscore, ff.flow_5d_ratio, ff.flow_20d_ratio,
               ff.flow_persistence, ff.investor_growth, ff.alis_valor,
               ff.satis_valor, ff.num_investors, fm.founder AS official_founder,
               fm.tefas_status AS official_tefas_status, fm.source AS tefas_status_source,
               fm.checked_at AS tefas_status_checked_at,
               fm.tefas_risk_value AS official_tefas_risk_value
        FROM rotation_recommendations rr
        LEFT JOIN fund_names fn ON fn.code = rr.code
        LEFT JOIN fund_features_daily ff
          ON ff.signal_date = rr.signal_date AND ff.code = rr.code
         AND ff.strategy_version = rr.strategy_version
        LEFT JOIN fund_platform_metadata fm ON fm.code = rr.code
        WHERE rr.signal_date = ? AND rr.strategy_version = ?
        ORDER BY CASE rr.action WHEN 'ALIM_ADAYI' THEN 1 WHEN 'TUT' THEN 2 ELSE 3 END,
                 COALESCE(rr.rank, 999), rr.score DESC
        """,
        (row["signal_date"], STRATEGY_VERSION),
    ).fetchall()
    recommendations = []
    for rec in recs:
        item = dict(rec)
        item["reasons"] = json.loads(item.pop("reasons_json") or "[]")
        opportunity_score = (
            float(item.get("momentum_score") or 0) * 0.55
            + float(item.get("trend_score") or 0) * 0.30
            + float(item.get("flow_score") or 0) * 0.10
            + float(item.get("risk_score") or 0) * 0.05
        )
        item["opportunity_score"] = round(opportunity_score, 2)
        item["tefas_url"] = tefas_fund_url(str(item["code"]))
        item["founder"] = resolve_founder(item.pop("official_founder"), str(item.get("name") or ""))
        item["strength"] = signal_strength(opportunity_score)
        item["signal"] = trade_signal(str(item["action"]), opportunity_score)
        official_status_raw = item.pop("official_tefas_status")
        official_status = _normalize_official_tefas_status(official_status_raw) if official_status_raw else None
        item["tefas_status"] = official_status or infer_tefas_status(
            str(item["code"]), str(item.get("name") or ""), _int(item.get("num_investors"))
        )
        item["tefas_status_estimated"] = official_status is None
        item["tefas_risk_value"] = _int(item.pop("official_tefas_risk_value"))
        item["risk_band"] = classify_tefas_risk(item["tefas_risk_value"]) or "BİLİNMİYOR"
        recommendations.append(item)
    result = dict(row)
    result["config"] = json.loads(result.pop("config_json") or "{}")
    result["diagnostics"] = json.loads(result.pop("diagnostics_json") or "{}")
    result["recommendations"] = recommendations
    result["ranking"] = _get_ranked_signals(conn, row["signal_date"], limit=50)
    result["risk_portfolios"] = _risk_portfolios_from_ranking(
        _get_ranked_signals(conn, row["signal_date"], limit=10000),
        limit=10,
    )
    result["emerging_radar"] = _get_emerging_fund_radar(conn, row["signal_date"], limit=50)
    conn.close()
    return result


def _get_ranked_signals(
    conn: sqlite3.Connection,
    signal_date: str,
    limit: int,
) -> list[dict[str, Any]]:
    excluded_categories = list(DEFAULT_CONFIG.get("excluded_candidate_categories", []))
    exclusion_clause = ""
    params: list[Any] = [signal_date, STRATEGY_VERSION]
    if excluded_categories:
        placeholders = ",".join("?" for _ in excluded_categories)
        exclusion_clause = f" AND ff.category NOT IN ({placeholders})"
        params.extend(excluded_categories)
    rows = conn.execute(
        f"""
        SELECT ff.code, fn.name, ff.category, ff.score, ff.momentum_score,
               ff.trend_score, ff.risk_score, ff.flow_score, ff.return_1m, ff.return_3m,
               ff.return_6m, ff.return_1y, ff.volatility_annual, ff.num_investors,
               ff.flow_5d_ratio, ff.flow_20d_ratio, ff.flow_persistence,
               fm.founder AS official_founder, fm.tefas_status AS official_tefas_status,
               fm.source AS tefas_status_source, fm.checked_at AS tefas_status_checked_at,
               fm.tefas_risk_value AS official_tefas_risk_value,
               fs.status AS technical_status, fs.target_weight AS current_target_weight
        FROM fund_features_daily ff
        LEFT JOIN fund_names fn ON fn.code = ff.code
        LEFT JOIN fund_signals fs
          ON fs.signal_date = ff.signal_date AND fs.code = ff.code
         AND fs.strategy_version = ff.strategy_version
        LEFT JOIN fund_platform_metadata fm ON fm.code = ff.code
        WHERE ff.signal_date = ? AND ff.strategy_version = ? AND ff.data_quality = 1
        {exclusion_clause}
        ORDER BY ff.score DESC
        """,
        params,
    ).fetchall()
    items = [dict(row) for row in rows]
    volatilities = pd.Series([item.get("volatility_annual") for item in items], dtype=float)
    risk_percentiles = volatilities.rank(pct=True) * 100
    for index, item in enumerate(items):
        opportunity_score = (
            float(item.get("momentum_score") or 0) * 0.55
            + float(item.get("trend_score") or 0) * 0.30
            + float(item.get("flow_score") or 0) * 0.10
            + float(item.get("risk_score") or 0) * 0.05
        )
        percentile = float(risk_percentiles.iloc[index]) if pd.notna(risk_percentiles.iloc[index]) else 100.0
        item["opportunity_score"] = round(opportunity_score, 2)
        item["tefas_url"] = tefas_fund_url(str(item["code"]))
        item["founder"] = resolve_founder(item.pop("official_founder"), str(item.get("name") or ""))
        item["strength"] = signal_strength(opportunity_score)
        item["signal"] = trade_signal(str(item.get("technical_status")), opportunity_score)
        official_status_raw = item.pop("official_tefas_status")
        official_status = _normalize_official_tefas_status(official_status_raw) if official_status_raw else None
        item["tefas_status"] = official_status or infer_tefas_status(
            str(item["code"]), str(item.get("name") or ""), _int(item.get("num_investors"))
        )
        item["tefas_status_estimated"] = official_status is None
        is_current_holding = float(item.get("current_target_weight") or 0) > 0
        if not is_current_holding and item["signal"] not in {"SAT", "GÜÇLÜ SAT"} and not is_tefas_buyable(item["tefas_status"]):
            item["signal"] = unavailable_signal(item["tefas_status"])
        item["model_risk_band"] = "DÜŞÜK" if percentile <= 33.33 else "ORTA" if percentile <= 66.67 else "YÜKSEK"
        item["tefas_risk_value"] = _int(item.pop("official_tefas_risk_value"))
        item["risk_band"] = classify_tefas_risk(item["tefas_risk_value"]) or item["model_risk_band"]
        item["monthly_return_gate"] = float(item.get("return_1m") or 0) >= DEFAULT_CONFIG["minimum_monthly_return"]
    items.sort(
        key=lambda item: (
            bool(item["monthly_return_gate"]),
            float(item["opportunity_score"]),
            float(item.get("momentum_score") or 0),
            float(item.get("trend_score") or 0),
            float(item.get("score") or 0),
        ),
        reverse=True,
    )
    ranking: list[dict[str, Any]] = []
    for rank, item in enumerate(items[:limit], start=1):
        item["rank"] = rank
        ranking.append(item)
    return ranking


def _risk_portfolios_from_ranking(
    ranking: list[dict[str, Any]],
    limit: int,
) -> dict[str, list[dict[str, Any]]]:
    investable = [
        item
        for item in ranking
        if item.get("monthly_return_gate", float(item.get("return_1m") or 0) >= DEFAULT_CONFIG["minimum_monthly_return"])
        and item.get("technical_status") != "CIKIS_ADAYI"
        and item.get("portfolio_action") != "CIKIS_ADAYI"
        and (item.get("signal") == "TUT" or is_tefas_buyable(item.get("tefas_status")))
    ]
    portfolios: dict[str, list[dict[str, Any]]] = {}
    for profile, bands in (
        ("medium_risk", {"ORTA"}),
        ("high_risk", {"YÜKSEK", "ÇOK YÜKSEK"}),
    ):
        selected = [dict(item) for item in investable if item.get("risk_band") in bands][:limit]
        weight = 1.0 / len(selected) if selected else 0.0
        for item in selected:
            item["profile_target_weight"] = weight
        portfolios[profile] = selected
    return portfolios


def get_ranked_signals(limit: int = 50) -> dict[str, Any]:
    """Son başarılı taramanın kategori kotasız global güç sıralamasını döndür."""
    init_db()
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    signal_date = conn.execute(
        "SELECT MAX(signal_date) FROM signal_runs WHERE strategy_version = ? AND status = 'SUCCESS'",
        (STRATEGY_VERSION,),
    ).fetchone()[0]
    if not signal_date:
        conn.close()
        return {"signal_date": None, "strategy_version": STRATEGY_VERSION, "ranking": []}
    ranking = _get_ranked_signals(conn, signal_date, limit)
    conn.close()
    return {
        "signal_date": signal_date,
        "strategy_version": STRATEGY_VERSION,
        "ranking": ranking,
    }


def _get_emerging_fund_radar(
    conn: sqlite3.Connection,
    signal_date: str,
    limit: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT er.*, fn.name, ff.category, ff.return_1m, ff.return_3m, ff.return_6m,
               ff.flow_5d_ratio, ff.flow_20d_ratio, ff.flow_persistence,
               ff.market_cap, ff.num_investors,
               fm.founder AS official_founder, fm.tefas_status AS official_tefas_status,
               fm.tefas_risk_value AS official_tefas_risk_value
        FROM emerging_fund_radar er
        LEFT JOIN fund_names fn ON fn.code = er.code
        LEFT JOIN fund_features_daily ff
          ON ff.signal_date = er.signal_date AND ff.code = er.code
         AND ff.strategy_version = er.strategy_version
        LEFT JOIN fund_platform_metadata fm ON fm.code = er.code
        WHERE er.signal_date = ? AND er.strategy_version = ?
        ORDER BY er.rank LIMIT ?
        """,
        (signal_date, STRATEGY_VERSION, limit),
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["reasons"] = json.loads(item.pop("reasons_json") or "[]")
        item["tefas_url"] = tefas_fund_url(str(item["code"]))
        item["founder"] = resolve_founder(item.pop("official_founder"), str(item.get("name") or ""))
        official_raw = item.pop("official_tefas_status")
        official_status = _normalize_official_tefas_status(official_raw) if official_raw else None
        item["tefas_status"] = official_status or infer_tefas_status(
            str(item["code"]), str(item.get("name") or ""), _int(item.get("num_investors"))
        )
        item["tefas_status_estimated"] = official_status is None
        item["tefas_risk_value"] = _int(item.pop("official_tefas_risk_value"))
        item["risk_band"] = classify_tefas_risk(item["tefas_risk_value"]) or "BİLİNMİYOR"
        items.append(item)
    return items


def get_emerging_fund_radar(limit: int = 50) -> dict[str, Any]:
    """63-251 günlük fonlar için son yeni-fon momentum radarını döndür."""
    init_db()
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    signal_date = conn.execute(
        "SELECT MAX(signal_date) FROM signal_runs WHERE strategy_version = ? AND status = 'SUCCESS'",
        (STRATEGY_VERSION,),
    ).fetchone()[0]
    if not signal_date:
        conn.close()
        return {"signal_date": None, "strategy_version": STRATEGY_VERSION, "radar": []}
    radar = _get_emerging_fund_radar(conn, signal_date, limit)
    conn.close()
    return {"signal_date": signal_date, "strategy_version": STRATEGY_VERSION, "radar": radar}


def get_risk_portfolios(limit: int = 10) -> dict[str, Any]:
    """Son taramadan orta ve yüksek riskli, trendi bozulmamış aday sepetleri."""
    init_db()
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    signal_date = conn.execute(
        "SELECT MAX(signal_date) FROM signal_runs WHERE strategy_version = ? AND status = 'SUCCESS'",
        (STRATEGY_VERSION,),
    ).fetchone()[0]
    if not signal_date:
        conn.close()
        return {"signal_date": None, "strategy_version": STRATEGY_VERSION, "portfolios": {}}
    ranking = _get_ranked_signals(conn, signal_date, limit=10000)
    portfolios = _risk_portfolios_from_ranking(ranking, limit=limit)
    conn.close()
    return {
        "signal_date": signal_date,
        "strategy_version": STRATEGY_VERSION,
        "portfolios": portfolios,
    }


def get_signals(
    status: str | None = None,
    category: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    signal_date = conn.execute(
        "SELECT MAX(signal_date) FROM signal_runs WHERE strategy_version = ? AND status = 'SUCCESS'",
        (STRATEGY_VERSION,),
    ).fetchone()[0]
    if not signal_date:
        conn.close()
        return {"signal_date": None, "signals": []}
    clauses = ["fs.signal_date = ?", "fs.strategy_version = ?"]
    params: list[Any] = [signal_date, STRATEGY_VERSION]
    if status:
        clauses.append("fs.status = ?")
        params.append(status)
    if category:
        clauses.append("ff.category = ?")
        params.append(category)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT fs.*, fn.name, ff.category, ff.momentum_score, ff.trend_score,
               ff.risk_score, ff.flow_score, ff.return_1m, ff.return_3m,
               ff.return_6m, ff.volatility_annual, ff.drawdown_6m,
               ff.alis_valor, ff.satis_valor, ff.data_quality
        FROM fund_signals fs
        LEFT JOIN fund_features_daily ff
          ON ff.signal_date = fs.signal_date AND ff.code = fs.code
         AND ff.strategy_version = fs.strategy_version
        LEFT JOIN fund_names fn ON fn.code = fs.code
        WHERE {' AND '.join(clauses)}
        ORDER BY fs.score DESC LIMIT ?
        """,
        params,
    ).fetchall()
    signals = []
    for row in rows:
        item = dict(row)
        item["reasons"] = json.loads(item.pop("reasons_json") or "[]")
        opportunity_score = (
            float(item.get("momentum_score") or 0) * 0.55
            + float(item.get("trend_score") or 0) * 0.30
            + float(item.get("flow_score") or 0) * 0.10
            + float(item.get("risk_score") or 0) * 0.05
        )
        item["opportunity_score"] = round(opportunity_score, 2)
        item["strength"] = signal_strength(opportunity_score)
        item["signal"] = trade_signal(str(item["status"]), opportunity_score)
        signals.append(item)
    conn.close()
    return {"signal_date": signal_date, "strategy_version": STRATEGY_VERSION, "signals": signals}


def get_signal_history(code: str, limit: int = 52) -> dict[str, Any]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT fs.signal_date, fs.status, fs.previous_status, fs.score, fs.rank,
               fs.target_weight, fs.reasons_json, ff.return_3m, ff.return_6m,
               ff.volatility_annual, ff.drawdown_6m, ff.momentum_score,
               ff.trend_score, ff.risk_score, ff.flow_score
        FROM fund_signals fs
        LEFT JOIN fund_features_daily ff
          ON ff.signal_date = fs.signal_date AND ff.code = fs.code
         AND ff.strategy_version = fs.strategy_version
        WHERE fs.code = ? AND fs.strategy_version = ?
        ORDER BY fs.signal_date DESC LIMIT ?
        """,
        (code.upper(), STRATEGY_VERSION, limit),
    ).fetchall()
    history = []
    for row in rows:
        item = dict(row)
        item["reasons"] = json.loads(item.pop("reasons_json") or "[]")
        opportunity_score = (
            float(item.get("momentum_score") or 0) * 0.55
            + float(item.get("trend_score") or 0) * 0.30
            + float(item.get("flow_score") or 0) * 0.10
            + float(item.get("risk_score") or 0) * 0.05
        )
        item["opportunity_score"] = round(opportunity_score, 2)
        item["strength"] = signal_strength(opportunity_score)
        item["signal"] = trade_signal(str(item["status"]), opportunity_score)
        history.append(item)
    conn.close()
    return {"code": code.upper(), "strategy_version": STRATEGY_VERSION, "history": history}


def run_backtest(
    max_dates: int = 1000,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = {**DEFAULT_CONFIG, **(config or {})}
    init_db()
    conn = get_connection()
    panels = load_panels(conn, max_dates=max_dates)
    step = config["rebalance_trading_days"]
    observations: list[dict[str, Any]] = []
    previous_weights: dict[str, float] = {}
    strategy_equity = 1.0
    benchmark_equity = 1.0

    for idx in range(config["minimum_history"], len(panels.dates) - step - 1, step):
        snapshot = score_snapshot(panels, idx=idx, config=config, include_reasons=False)
        selected, _ = build_rotation_portfolio(snapshot, set(previous_weights), config)
        entry_idx = idx + 1
        exit_idx = idx + step + 1
        entry_prices = panels.price.iloc[entry_idx]
        # Bir fon dönem içinde NAV yayımlamayı keserse onu gelecekteki veri
        # mevcudiyetine bakarak evrenden çıkarmak look-ahead yanlılığı yaratır.
        # Girişte işlem görebilen fonu dönem sonuna kadar son bilinen NAV ile değerle.
        exit_prices = panels.price.iloc[entry_idx : exit_idx + 1].ffill().iloc[-1]
        forward = exit_prices / entry_prices - 1

        selected_codes = [code for code in selected.get("code", []) if pd.notna(entry_prices.get(code))]
        new_weights = {code: 1.0 / len(selected_codes) for code in selected_codes} if selected_codes else {}
        all_codes = set(previous_weights) | set(new_weights)
        turnover = (
            1.0
            if not previous_weights and new_weights
            else 0.5 * sum(abs(new_weights.get(code, 0) - previous_weights.get(code, 0)) for code in all_codes)
        )
        gross_return = float(np.mean([forward[code] for code in selected_codes])) if selected_codes else 0.0
        net_return = gross_return - turnover * config["transaction_cost_rate"]

        eligible_codes = snapshot.loc[snapshot["data_quality"], "code"].tolist()
        benchmark_values = [forward[code] for code in eligible_codes if pd.notna(entry_prices.get(code))]
        benchmark_return = float(np.mean(benchmark_values)) if benchmark_values else 0.0
        strategy_equity *= 1 + net_return
        benchmark_equity *= 1 + benchmark_return
        observations.append(
            {
                "signal_date": panels.dates[idx],
                "entry_date": panels.dates[entry_idx],
                "exit_date": panels.dates[exit_idx],
                "return": net_return,
                "gross_return": gross_return,
                "benchmark_return": benchmark_return,
                "turnover": turnover,
                "equity": strategy_equity,
                "benchmark_equity": benchmark_equity,
                "selected": selected_codes,
            }
        )
        previous_weights = new_weights

    if not observations:
        conn.close()
        raise ValueError("Backtest için yeterli gözlem üretilemedi")
    metrics = _backtest_metrics(observations, config)
    start_date = observations[0]["entry_date"]
    end_date = observations[-1]["exit_date"]
    conn.execute(
        """
        INSERT INTO strategy_backtests (
            strategy_version, start_date, end_date, config_json, metrics_json, equity_curve_json
        ) VALUES (?,?,?,?,?,?)
        """,
        (
            STRATEGY_VERSION, start_date, end_date, json.dumps(config, ensure_ascii=False),
            json.dumps(metrics, ensure_ascii=False), json.dumps(observations, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()
    return {
        "strategy_version": STRATEGY_VERSION,
        "start_date": start_date,
        "end_date": end_date,
        "metrics": metrics,
        "equity_curve": observations,
        "limitations": [
            "Fon kategori ve unvanları tarihsel point-in-time değil, güncel fund_names tablosundan gelir.",
            "Valörler isim tabanlı tahmindir; gerçekleşme fiyatı simülasyonu sonraki işlem günü NAV kullanır.",
            "Dönem içinde NAV kesilirse fon son yayımlanan NAV ile değerlenir; giriş günü NAV yoksa işlem atlanır.",
            "Risksiz getiri sabit yıllık varsayımdır; tarihsel faiz eğrisi kullanılmaz.",
            "Sonuçlar yatırım tavsiyesi değil, model araştırmasıdır.",
        ],
    }


def _backtest_metrics(observations: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    returns = np.array([row["return"] for row in observations], dtype=float)
    benchmark = np.array([row["benchmark_return"] for row in observations], dtype=float)
    equities = np.array([row["equity"] for row in observations], dtype=float)
    periods_per_year = 252 / config["rebalance_trading_days"]
    years = len(returns) / periods_per_year
    total_return = float(equities[-1] - 1)
    cagr = float(equities[-1] ** (1 / years) - 1) if years > 0 and equities[-1] > 0 else 0.0
    annual_vol = float(np.std(returns, ddof=1) * math.sqrt(periods_per_year)) if len(returns) > 1 else 0.0
    rf_period = (1 + config["annual_risk_free_rate"]) ** (1 / periods_per_year) - 1
    excess = returns - rf_period
    sharpe = float(np.mean(excess) / np.std(returns, ddof=1) * math.sqrt(periods_per_year)) if annual_vol > 0 else 0.0
    downside_deviation = float(np.sqrt(np.mean(np.minimum(excess, 0) ** 2)))
    sortino = (
        float(np.mean(excess) / downside_deviation * math.sqrt(periods_per_year))
        if downside_deviation > 0
        else 0.0
    )
    running_peak = np.maximum.accumulate(equities)
    max_drawdown = float(np.min(equities / running_peak - 1))
    benchmark_total = float(np.prod(1 + benchmark) - 1)
    return {
        "periods": len(observations),
        "total_return": total_return,
        "cagr": cagr,
        "annual_volatility": annual_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_drawdown,
        "calmar": cagr / abs(max_drawdown) if max_drawdown < 0 else 0.0,
        "hit_rate": float(np.mean(returns > 0)),
        "average_turnover": float(np.mean([row["turnover"] for row in observations])),
        "benchmark_total_return": benchmark_total,
        "excess_total_return": total_return - benchmark_total,
    }


def get_latest_backtest(include_curve: bool = True) -> dict[str, Any]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM strategy_backtests WHERE strategy_version = ? ORDER BY id DESC LIMIT 1",
        (STRATEGY_VERSION,),
    ).fetchone()
    conn.close()
    if not row:
        return {"strategy_version": STRATEGY_VERSION, "metrics": None, "equity_curve": []}
    result = dict(row)
    result["config"] = json.loads(result.pop("config_json"))
    result["metrics"] = json.loads(result.pop("metrics_json"))
    curve = json.loads(result.pop("equity_curve_json"))
    result["equity_curve"] = curve if include_curve else []
    return result
