"""Data builders for legacy Telegram notifications.

These builders do not change the main, emerging-fund or social signal models.
They only turn existing TEFAS data into clearer daily/weekly notification data.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from database import get_connection
from signals import STRATEGY_VERSION, classify_category, infer_tefas_status, tefas_fund_url


MIN_MARKET_CAP = 50_000_000
MIN_INVESTORS = 50


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


def _percentiles(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: item[1])
    count = len(ordered)
    if not count:
        return {}
    return {code: (index + 1) / count * 100 for index, (code, _) in enumerate(ordered)}


def _technical_score(row: dict[str, Any]) -> float:
    return _float(row.get("momentum_score")) * 0.60 + _float(row.get("trend_score")) * 0.40


def _platform(row: dict[str, Any]) -> str:
    return str(row.get("tefas_status") or infer_tefas_status(
        str(row.get("code") or ""), str(row.get("name") or ""), int(row.get("num_investors") or 0),
    ))


def _latest_rows(date_str: str) -> list[dict[str, Any]]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    feature_date = conn.execute(
        "SELECT MAX(signal_date) FROM fund_features_daily WHERE signal_date <= ? AND strategy_version = ?",
        (date_str, STRATEGY_VERSION),
    ).fetchone()[0]
    rows = conn.execute(
        """
        SELECT fd.code, fd.price, fd.market_cap, fd.num_investors, fd.net_flow,
               fd.pct_change, fd.investor_change, COALESCE(fn.name, fd.code) AS name,
               fm.tefas_status, fm.tefas_risk_value, fm.founder,
               ff.momentum_score, ff.trend_score, ff.flow_score, ff.risk_score,
               ff.return_1m, ff.return_3m, ff.return_6m, ff.return_1y,
               ff.alis_valor, ff.satis_valor,
               (SELECT p.market_cap FROM fund_daily p
                WHERE p.code = fd.code AND p.date < fd.date AND p.market_cap IS NOT NULL
                ORDER BY p.date DESC LIMIT 1) AS previous_market_cap
        FROM fund_daily fd
        LEFT JOIN fund_names fn ON fn.code = fd.code
        LEFT JOIN fund_platform_metadata fm ON fm.code = fd.code
        LEFT JOIN fund_features_daily ff
          ON ff.code = fd.code AND ff.signal_date = ? AND ff.strategy_version = ?
        WHERE fd.date = ?
        """,
        (feature_date, STRATEGY_VERSION, date_str),
    ).fetchall()
    conn.close()
    result = []
    for raw in rows:
        row = dict(raw)
        row["category"] = classify_category(str(row.get("name") or ""))
        row["tefas_status"] = _platform(row)
        row["tefas_url"] = tefas_fund_url(str(row["code"]))
        previous_investors = _float(row.get("num_investors")) - _float(row.get("investor_change"))
        row["investor_change_pct"] = (
            _float(row.get("investor_change")) / previous_investors * 100 if previous_investors > 0 else 0.0
        )
        denominator = _float(row.get("previous_market_cap")) or _float(row.get("market_cap"))
        row["flow_aum_pct"] = _float(row.get("net_flow")) / denominator * 100 if denominator > 0 else 0.0
        row["technical_score"] = _technical_score(row)
        result.append(row)
    return result


def _eligible(row: dict[str, Any]) -> bool:
    return (
        row.get("category") != "Para Piyasası"
        and row.get("net_flow") is not None
        and _float(row.get("market_cap")) >= MIN_MARKET_CAP
        and int(row.get("num_investors") or 0) >= MIN_INVESTORS
    )


def _flow_side(rows: list[dict[str, Any]], positive: bool, limit: int) -> list[dict[str, Any]]:
    side = [row.copy() for row in rows if (_float(row.get("net_flow")) > 0) == positive]
    if not side:
        return []
    ratio_rank = _percentiles({str(row["code"]): abs(_float(row["flow_aum_pct"])) for row in side})
    amount_rank = _percentiles({str(row["code"]): abs(_float(row["net_flow"])) for row in side})
    investor_rank = _percentiles({str(row["code"]): abs(_float(row["investor_change_pct"])) for row in side})
    for row in side:
        code = str(row["code"])
        row["flow_strength"] = (
            ratio_rank.get(code, 0) * 0.55
            + amount_rank.get(code, 0) * 0.25
            + investor_rank.get(code, 0) * 0.20
        )
        if positive:
            row["flow_label"] = (
                "TEYİTLİ GİRİŞ" if row["technical_score"] >= 70 and _float(row.get("flow_score")) >= 60
                else "YENİ İLGİ" if row["investor_change_pct"] > 0.5
                else "PARA GİRİŞİ"
            )
        else:
            row["flow_label"] = (
                "ÇIKIŞ BASKISI" if row["technical_score"] < 50 or _float(row.get("pct_change")) < 0
                else "KÂR REALİZASYONU"
            )
    side.sort(key=lambda row: (row["flow_strength"], abs(_float(row["net_flow"]))), reverse=True)
    for rank, row in enumerate(side[:limit], 1):
        row["rank"] = rank
    return side[:limit]


def build_market_pulse(date_str: str, limit: int = 5) -> dict[str, Any]:
    rows = [row for row in _latest_rows(date_str) if _eligible(row)]
    inflow = sum(_float(row["net_flow"]) for row in rows if _float(row["net_flow"]) > 0)
    outflow = sum(_float(row["net_flow"]) for row in rows if _float(row["net_flow"]) < 0)
    return {
        "date": date_str,
        "universe_count": len(rows),
        "gross_inflow": inflow,
        "gross_outflow": outflow,
        "net_flow": inflow + outflow,
        "top_inflows": _flow_side(rows, True, limit),
        "top_outflows": _flow_side(rows, False, limit),
        "policy": "Para piyasası fonları hariç; akış fon büyüklüğüne göre normalize edilmiştir.",
    }


def _return(current: float, previous: float | None) -> float | None:
    return (current / previous - 1) * 100 if previous and current > 0 else None


def build_performance_continuation(date_str: str, limit: int = 10) -> dict[str, Any]:
    rows = [row for row in _latest_rows(date_str) if _eligible(row)]
    conn = get_connection()
    dates = [
        str(row[0]) for row in conn.execute(
            "SELECT DISTINCT date FROM fund_daily WHERE date <= ? ORDER BY date DESC LIMIT 22", (date_str,)
        ).fetchall()
    ]
    price_rows = conn.execute(
        f"SELECT code, date, price FROM fund_daily WHERE date IN ({','.join('?' for _ in dates)})",
        dates,
    ).fetchall() if dates else []
    conn.close()
    prices = {(str(code), str(date)): _float(price) for code, date, price in price_rows}
    offsets = {"return_3d": 3, "return_1w": 5, "return_1m_display": 21}
    candidates: list[dict[str, Any]] = []
    for source in rows:
        row = source.copy()
        current = _float(row.get("price"))
        row["return_1d"] = _float(row.get("pct_change"))
        for label, offset in offsets.items():
            previous = prices.get((str(row["code"]), dates[offset])) if len(dates) > offset else None
            row[label] = _return(current, previous)
        if row["return_1d"] <= 0 or any(row.get(label) is None for label in offsets):
            continue
        candidates.append(row)
    if not candidates:
        return {"date": date_str, "leaders": [], "policy": "Para piyasası fonları hariç."}

    rank_weights = {
        "return_1d": 0.15, "return_3d": 0.15, "return_1w": 0.20,
        "return_1m_display": 0.20, "technical_score": 0.15, "flow_score": 0.15,
    }
    ranks = {
        field: _percentiles({str(row["code"]): _float(row.get(field)) for row in candidates})
        for field in rank_weights
    }
    for row in candidates:
        code = str(row["code"])
        row["continuation_score"] = sum(ranks[field].get(code, 0) * weight for field, weight in rank_weights.items())
        if row["return_1d"] >= 5 and _float(row.get("flow_score")) <= 50:
            label = "TEYİTSİZ SIÇRAMA"
        elif _float(row.get("net_flow")) < 0:
            label = "KÂR SATIŞI RİSKİ"
        elif row["technical_score"] >= 70 and _float(row.get("flow_score")) >= 60:
            label = "DEVAM EDEN MOMENTUM"
        else:
            label = "GÜÇLÜ PERFORMANS"
        row["performance_label"] = label
    candidates.sort(key=lambda row: (row["continuation_score"], row["return_1m_display"]), reverse=True)
    # Günün ham getiri liderlerini kaçırma; kalan sıraları devamlılık puanı doldursun.
    daily_leaders = sorted(candidates, key=lambda row: row["return_1d"], reverse=True)[: min(5, limit)]
    selected_codes = {str(row["code"]) for row in daily_leaders}
    leaders = daily_leaders + [row for row in candidates if str(row["code"]) not in selected_codes][: max(0, limit - len(daily_leaders))]
    leaders.sort(key=lambda row: row["continuation_score"], reverse=True)
    for rank, row in enumerate(leaders, 1):
        row["rank"] = rank
    return {
        "date": date_str,
        "leaders": leaders,
        "policy": "Getiri; momentum, trend ve para akışı teyidiyle birlikte sıralanır.",
    }


def enrich_rotation_changes(rotation: dict[str, Any], limit: int = 20) -> dict[str, Any]:
    date_str = str(rotation.get("signal_date") or "")
    recommendations = list(rotation.get("recommendations") or [])
    if not date_str or not recommendations:
        return {**rotation, "changes": []}
    codes = [str(item.get("code")) for item in recommendations]
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""
        SELECT fs.code, fs.previous_status, fs.status, ff.momentum_score,
               ff.trend_score, ff.flow_score, ff.return_1m, ff.return_3m,
               ff.alis_valor, ff.satis_valor, fm.tefas_risk_value, fm.tefas_status
        FROM fund_signals fs
        LEFT JOIN fund_features_daily ff
          ON ff.signal_date=fs.signal_date AND ff.code=fs.code AND ff.strategy_version=fs.strategy_version
        LEFT JOIN fund_platform_metadata fm ON fm.code=fs.code
        WHERE fs.signal_date=? AND fs.strategy_version=?
          AND fs.code IN ({','.join('?' for _ in codes)})
        """,
        [date_str, STRATEGY_VERSION, *codes],
    ).fetchall()
    conn.close()
    context = {str(row["code"]): dict(row) for row in rows}
    changes = []
    for item in recommendations:
        row = {**item, **context.get(str(item.get("code")), {})}
        previous = str(row.get("previous_status") or "YENİ")
        current = str(row.get("action") or row.get("status") or "")
        if previous == current:
            continue
        row["previous_status"] = previous
        row["current_status"] = current
        row["tefas_url"] = tefas_fund_url(str(row.get("code") or ""))
        changes.append(row)
    priority = {"ALIM_ADAYI": 3, "TUT": 2, "CIKIS_ADAYI": 1}
    changes.sort(key=lambda row: (priority.get(str(row.get("current_status")), 0), _float(row.get("score"))), reverse=True)
    return {**rotation, "changes": changes[:limit]}


def group_anomalies(anomalies: list[dict[str, Any]], date_str: str, limit: int = 10) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    for alert in anomalies:
        code = str(alert.get("code") or "")
        row = grouped.setdefault(code, {"code": code, "alerts": [], "severity_rank": 0})
        row["alerts"].append(alert)
        row["severity_rank"] = max(row["severity_rank"], int(alert.get("severity_rank") or 0))
    context = {str(row["code"]): row for row in _latest_rows(date_str)}
    rows = []
    for code, group in grouped.items():
        row = {**context.get(code, {}), **group, "tefas_url": tefas_fund_url(code)}
        row["alert_summary"] = " + ".join(str(item.get("short_label") or item.get("label") or "") for item in group["alerts"])
        row["max_zscore"] = max(abs(_float(item.get("z_score"))) for item in group["alerts"])
        rows.append(row)
    rows.sort(key=lambda row: (row["severity_rank"], row["max_zscore"]), reverse=True)
    for rank, row in enumerate(rows[:limit], 1):
        row["rank"] = rank
    return {"date": date_str, "anomalies": rows[:limit]}
