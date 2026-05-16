import logging
from datetime import datetime

import numpy as np

from config import Z_SCORE_THRESHOLD, DAILY_RETURN_THRESHOLD, MARKET_CAP_CHANGE_THRESHOLD
from database import get_recent_data, get_all_codes_for_date, log_alert

logger = logging.getLogger(__name__)


def _z_score(series: list[float]) -> float:
    """Son elementin Z-Score'unu hesaplar."""
    if len(series) < 5:
        return 0.0
    arr = np.array(series, dtype=float)
    # NaN'ları çıkar
    arr = arr[~np.isnan(arr)]
    if len(arr) < 5:
        return 0.0
    mean = np.mean(arr[:-1])
    std = np.std(arr[:-1])
    if std == 0:
        return 0.0
    return (arr[-1] - mean) / std


def detect_anomalies(date: str = None) -> list[dict]:
    """
    Belirtilen tarih için tüm fonlarda anomali taraması yapar.
    Döndürülen liste: [{ code, alert_type, value, z_score, severity }]
    """
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")

    funds_today = get_all_codes_for_date(date)
    if not funds_today:
        logger.warning("Anomali taraması: %s tarihi için veri bulunamadı.", date)
        return []

    anomalies = []

    for row in funds_today:
        code, price, market_cap, num_investors, net_flow, pct_change, investor_change = row

        # Geçmiş veriyi çek (rolling hesap için)
        history = get_recent_data(code, days=35)

        if len(history) < 5:
            continue

        # history: (date, net_flow, pct_change, investor_change, market_cap, num_investors)
        net_flows = [h[1] for h in history if h[1] is not None]
        pct_changes = [h[2] for h in history if h[2] is not None]
        inv_changes = [h[3] for h in history if h[3] is not None]

        # ─── 1. NET PARA AKIŞI ANOMALİSİ ─────────────────────────────
        if net_flow is not None and len(net_flows) >= 5:
            z = _z_score(net_flows)
            if abs(z) >= Z_SCORE_THRESHOLD:
                direction = "GİRİŞ 📈" if net_flow > 0 else "ÇIKIŞ 📉"
                alert = {
                    "code": code,
                    "alert_type": f"NET_FLOW_{('IN' if net_flow > 0 else 'OUT')}",
                    "value": net_flow,
                    "z_score": round(z, 2),
                    "severity": _severity(abs(z)),
                    "label": f"Anormal Para {direction}",
                    "detail": f"{_fmt_try(net_flow)} (Z={z:.2f})",
                }
                anomalies.append(alert)
                log_alert(date, code, alert["alert_type"], net_flow, z, alert["detail"])

        # ─── 2. GETİRİ ANOMALİSİ ─────────────────────────────────────
        if pct_change is not None and abs(pct_change) >= DAILY_RETURN_THRESHOLD:
            z = _z_score(pct_changes) if len(pct_changes) >= 5 else 0.0
            alert = {
                "code": code,
                "alert_type": "HIGH_RETURN" if pct_change > 0 else "HIGH_LOSS",
                "value": pct_change,
                "z_score": round(z, 2),
                "severity": "🔴 YÜKSEk" if abs(pct_change) >= 10 else "🟡 ORTA",
                "label": f"Yüksek {'Getiri' if pct_change > 0 else 'Kayıp'}",
                "detail": f"%{pct_change:.2f} (Z={z:.2f})",
            }
            anomalies.append(alert)
            log_alert(date, code, alert["alert_type"], pct_change, z, alert["detail"])

        # ─── 3. YATIRIMCI SAYISI ANOMALİSİ ──────────────────────────
        if investor_change is not None and len(inv_changes) >= 5:
            z = _z_score(inv_changes)
            if abs(z) >= Z_SCORE_THRESHOLD:
                direction = "artış 🧑‍🤝‍🧑" if investor_change > 0 else "azalış 🚶"
                alert = {
                    "code": code,
                    "alert_type": f"INVESTOR_{'IN' if investor_change > 0 else 'OUT'}",
                    "value": investor_change,
                    "z_score": round(z, 2),
                    "severity": _severity(abs(z)),
                    "label": f"Anormal Yatırımcı {direction}",
                    "detail": f"{investor_change:+,} kişi (Z={z:.2f})",
                }
                anomalies.append(alert)
                log_alert(date, code, alert["alert_type"], investor_change, z, alert["detail"])

    logger.info("%s tarihi için %d anomali tespit edildi.", date, len(anomalies))
    return anomalies


def _severity(abs_z: float) -> str:
    if abs_z >= 4.0:
        return "🔴 KRİTİK"
    elif abs_z >= 3.0:
        return "🟠 YÜKSEK"
    else:
        return "🟡 ORTA"


def _fmt_try(amount: float) -> str:
    """Para miktarını okunabilir formata çevirir."""
    if abs(amount) >= 1_000_000_000:
        return f"{amount/1_000_000_000:+.2f}B ₺"
    elif abs(amount) >= 1_000_000:
        return f"{amount/1_000_000:+.2f}M ₺"
    elif abs(amount) >= 1_000:
        return f"{amount/1_000:+.2f}K ₺"
    return f"{amount:+.2f} ₺"
