#!/usr/bin/env python3
"""
TEFAS Alert Sistemi — Ana Çalıştırıcı
Kullanım:
  python run.py                  # Scheduler'ı başlat (sonsuz döngü)
  python run.py --now            # Şu an için tek çalıştır
  python run.py --test           # Telegram bağlantısını test et
  python run.py --history 90     # Son 90 günün verisini doldur
  python run.py --dashboard      # Dashboard verilerini yenile
"""
import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta

# data klasörünü oluştur
os.makedirs("data", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/tefas_alert.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="TEFAS Alert Sistemi")
    parser.add_argument("--now", action="store_true", help="Hemen çalıştır")
    parser.add_argument("--test", action="store_true", help="Telegram bağlantısını test et")
    parser.add_argument("--history", type=int, metavar="DAYS", help="Son N günün geçmiş verisini yükle")
    parser.add_argument("--date", type=str, help="Belirli bir tarih için çalıştır (YYYY-MM-DD)")
    args = parser.parse_args()

    from database import init_db
    init_db()

    if args.test:
        logger.info("Telegram bağlantısı test ediliyor...")
        try:
            from alerts import test_telegram_connection
            username = test_telegram_connection()
            print(f"✅ Başarılı! Bot kullanıcı adı: @{username}")
        except Exception as e:
            print(f"❌ Hata: {e}")
            print("\nLütfen .env dosyasını kontrol et:")
            print("  TELEGRAM_BOT_TOKEN=...")
            print("  TELEGRAM_CHAT_ID=...")
        return

    if args.history:
        days = args.history
        end_date = datetime.today().strftime("%Y-%m-%d")
        start_date = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
        logger.info("Geçmiş veri yükleniyor: %s → %s (%d gün)", start_date, end_date, days)
        from fetcher import fetch_historical
        fetch_historical(start_date, end_date)
        return

    if args.date:
        target_date = args.date
        logger.info("Belirli tarih için çalıştırılıyor: %s", target_date)
        _run_for_date(target_date)
        return

    if args.now:
        today = datetime.today().strftime("%Y-%m-%d")
        logger.info("Şu an için çalıştırılıyor: %s", today)
        _run_for_date(today)
        return

    # Varsayılan: Scheduler başlat
    from scheduler import start_scheduler
    start_scheduler()


def _run_for_date(date: str):
    from fetcher import fetch_and_store
    from anomaly import detect_anomalies
    from alerts import send_anomaly_alerts, send_daily_summary

    count = fetch_and_store(date)
    if count == 0:
        print(f"⚠️  {date} için veri bulunamadı.")
        return

    print(f"✅ {count} fon verisi çekildi.")

    anomalies = detect_anomalies(date)
    print(f"🔍 {len(anomalies)} anomali tespit edildi.")

    if anomalies:
        for a in anomalies[:10]:
            print(f"  {a['severity']} {a['code']}: {a['label']} — {a['detail']}")
        if len(anomalies) > 10:
            print(f"  ... ve {len(anomalies) - 10} tane daha")
        asyncio.run(send_anomaly_alerts(anomalies, date))
        print("📱 Anomali alertleri Telegram'a gönderildi.")

    asyncio.run(send_daily_summary(date))
    print("📊 Günlük özet Telegram'a gönderildi.")

    # Dashboard JSON'ını güncelle
    _export_dashboard_json()


def _export_dashboard_json():
    """Dashboard için JSON veriyi data/ klasörüne yazar."""
    import json
    from database import get_dashboard_data

    data = get_dashboard_data()
    if not data:
        return

    def fmt(amount):
        if amount is None:
            return "0"
        if abs(amount) >= 1e9:
            return f"{amount/1e9:.2f}B"
        if abs(amount) >= 1e6:
            return f"{amount/1e6:.2f}M"
        if abs(amount) >= 1e3:
            return f"{amount/1e3:.2f}K"
        return f"{amount:.2f}"

    output = {
        "last_date": data["last_date"],
        "total_funds": data["total_funds"],
        "total_inflow": fmt(data["total_inflow"]),
        "total_outflow": fmt(data["total_outflow"]),
        "top_inflows": [
            {"code": r[0], "net_flow": fmt(r[1]), "pct_change": round(r[2] or 0, 2),
             "num_investors": r[3], "market_cap": fmt(r[4])}
            for r in data["top_inflows"]
        ],
        "top_outflows": [
            {"code": r[0], "net_flow": fmt(r[1]), "pct_change": round(r[2] or 0, 2),
             "num_investors": r[3], "market_cap": fmt(r[4])}
            for r in data["top_outflows"]
        ],
        "top_returns": [
            {"code": r[0], "pct_change": round(r[1] or 0, 2), "net_flow": fmt(r[2]),
             "num_investors": r[3], "market_cap": fmt(r[4])}
            for r in data["top_returns"]
        ],
        "recent_alerts": [
            {"date": r[0], "code": r[1], "type": r[2], "value": r[3], "z_score": r[4]}
            for r in data["recent_alerts"]
        ],
    }

    os.makedirs("data", exist_ok=True)
    with open("data/dashboard.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("📄 Dashboard verisi: data/dashboard.json")


if __name__ == "__main__":
    main()
