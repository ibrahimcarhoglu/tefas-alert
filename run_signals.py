#!/usr/bin/env python3
"""Generate weekly TEFAS signals and optionally run a walk-forward backtest."""

import argparse
import json
import logging
from datetime import date, datetime, timedelta

from database import get_connection, init_db
from fetcher import fetch_range_and_store
from signals import run_backtest, run_weekly_rotation


logger = logging.getLogger("signal_scanner")


def scanner_status() -> dict:
    init_db()
    conn = get_connection()
    latest_data = conn.execute("SELECT MAX(date) FROM fund_daily").fetchone()[0]
    latest_signal = conn.execute(
        """
        SELECT signal_date, status, universe_count, selected_count, created_at
        FROM signal_runs ORDER BY signal_date DESC LIMIT 1
        """
    ).fetchone()
    conn.close()
    age = None
    if latest_data:
        age = (date.today() - datetime.strptime(latest_data, "%Y-%m-%d").date()).days
    return {
        "latest_data": latest_data,
        "data_age_days": age,
        "data_stale": age is None or age > 10,
        "latest_signal": (
            {
                "signal_date": latest_signal[0],
                "status": latest_signal[1],
                "universe_count": latest_signal[2],
                "selected_count": latest_signal[3],
                "created_at": latest_signal[4],
            }
            if latest_signal
            else None
        ),
    }


def refresh_missing_dates(max_backfill_days: int) -> dict:
    """TEFAS geçmişindeki eksik takvim aralığını web arayüzüne bağlı olmadan doldur."""
    status = scanner_status()
    if not status["latest_data"]:
        raise RuntimeError("Ana geçmiş verisi yok; önce fetch_history.py ile en az 252 işlem günü yükleyin")
    latest = datetime.strptime(status["latest_data"], "%Y-%m-%d").date()
    today = date.today()
    missing_calendar_days = (today - latest).days
    if missing_calendar_days <= 0:
        return {"before": str(latest), "after": str(latest), "days_checked": 0, "rows_fetched": 0}
    if missing_calendar_days > max_backfill_days:
        raise RuntimeError(
            f"{missing_calendar_days} günlük boşluk güvenlik sınırı olan {max_backfill_days} günü aşıyor; "
            "--max-backfill-days değerini bilinçli olarak yükseltin"
        )

    start = latest + timedelta(days=1)
    days_checked = sum(
        1
        for offset in range((today - start).days + 1)
        if (start + timedelta(days=offset)).weekday() < 5
    )
    rows_fetched = fetch_range_and_store(start.isoformat(), today.isoformat())

    refreshed = scanner_status()
    return {
        "before": str(latest),
        "after": refreshed["latest_data"],
        "days_checked": days_checked,
        "rows_fetched": rows_fetched,
    }


def compact_rotation(rotation: dict) -> dict:
    """CLI çıktısını operasyonel özetle sınırla; ayrıntı DB/API'de kalır."""
    keys = (
        "generated", "reason", "signal_date", "strategy_version",
        "universe_count", "selected_count", "diagnostics",
    )
    result = {key: rotation[key] for key in keys if key in rotation}
    result["recommendations"] = [
        {
            key: item.get(key)
            for key in (
                "code", "tefas_url", "founder", "action", "signal", "rank", "score", "opportunity_score",
                "strength", "risk_band", "model_risk_band", "tefas_risk_value",
                "tefas_status", "tefas_status_estimated",
                "target_weight", "category", "reasons",
            )
        }
        for item in rotation.get("recommendations", [])
    ]
    result["ranking"] = [
        {
            key: item.get(key)
            for key in (
                "rank", "code", "tefas_url", "name", "founder", "category", "score", "opportunity_score",
                "strength", "signal", "risk_band", "model_risk_band", "tefas_risk_value",
                "technical_status", "momentum_score", "trend_score",
                "risk_score", "flow_score", "return_1m", "return_3m", "return_6m", "return_1y",
                "tefas_status", "tefas_status_estimated",
            )
        }
        for item in rotation.get("ranking", [])[:10]
    ]
    result["risk_portfolios"] = {
        profile: [
            {
                key: item.get(key)
                for key in (
                    "rank", "code", "name", "founder", "category", "opportunity_score",
                    "signal", "strength", "risk_band", "model_risk_band", "tefas_risk_value", "momentum_score",
                    "trend_score", "return_1m", "return_3m", "return_6m", "return_1y",
                    "tefas_status", "tefas_status_estimated", "profile_target_weight",
                )
            }
            for item in items
        ]
        for profile, items in rotation.get("risk_portfolios", {}).items()
    }
    result["emerging_radar"] = [
        {
            key: item.get(key)
            for key in (
                "rank", "code", "tefas_url", "name", "founder", "category", "tier", "signal",
                "score", "confidence", "history_days", "momentum_score", "trend_score",
                "flow_score", "risk_liquidity_score", "return_1m", "return_3m",
                "return_6m", "flow_5d_ratio", "flow_20d_ratio", "flow_persistence",
                "market_cap", "num_investors", "risk_band", "tefas_risk_value",
                "tefas_status", "tefas_status_estimated",
            )
        }
        for item in rotation.get("emerging_radar", [])[:10]
    ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="TEFAS haftalık momentum rotasyonu")
    parser.add_argument("--date", help="Sinyal tarihi (YYYY-MM-DD); varsayılan DB son tarihi")
    parser.add_argument("--force", action="store_true", help="Haftalık süre dolmasa da yeniden üret")
    parser.add_argument("--backtest", action="store_true", help="Sinyal sonrası walk-forward backtest çalıştır")
    parser.add_argument("--max-dates", type=int, default=1000, help="Backtest işlem günü üst sınırı")
    parser.add_argument("--refresh", action="store_true", help="Eksik TEFAS günlerini tamamlayıp sonra tara")
    parser.add_argument("--max-backfill-days", type=int, default=120, help="Tek çalışmada izin verilen azami takvim boşluğu")
    parser.add_argument("--check", action="store_true", help="Veri/sinyal durumunu göster; tarama üretme")
    parser.add_argument("--allow-stale", action="store_true", help="Bayat veri üzerinde araştırma amaçlı taramaya açıkça izin ver")
    parser.add_argument("--full-output", action="store_true", help="Backtest eğrisi dahil tam JSON çıktısı ver")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    before = scanner_status()
    if args.check:
        print(json.dumps({"scanner": before}, ensure_ascii=False, indent=2))
        return

    refresh = refresh_missing_dates(args.max_backfill_days) if args.refresh else None
    current = scanner_status()
    if current["data_stale"] and not args.allow_stale:
        raise SystemExit(
            f"Tarama durduruldu: son veri {current['latest_data']} ({current['data_age_days']} gün eski). "
            "Güncel tarama için --refresh; yalnız araştırma için --allow-stale kullanın."
        )

    rotation = run_weekly_rotation(args.date, force=args.force)
    result = {
        "scanner": current,
        "refresh": refresh,
        "rotation": rotation if args.full_output else compact_rotation(rotation),
    }
    if args.backtest:
        backtest = run_backtest(max_dates=args.max_dates)
        result["backtest"] = backtest if args.full_output else {
            key: backtest[key]
            for key in ("strategy_version", "start_date", "end_date", "metrics", "limitations")
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
