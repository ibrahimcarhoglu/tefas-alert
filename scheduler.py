import logging
import os
import time
from datetime import datetime

import schedule

from config import FETCH_TIME
from database import init_db
from fetcher import fetch_and_store
from anomaly import detect_anomalies
from alerts import send_anomaly_alerts, send_daily_summary

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


def run_daily_job():
    """Her sabah çalışan ana iş akışı."""
    today = datetime.today().strftime("%Y-%m-%d")
    logger.info("=" * 60)
    logger.info("Günlük iş akışı başlıyor: %s", today)

    try:
        # 1. Veri çek
        count = fetch_and_store(today)
        if count == 0:
            logger.info("Veri bulunamadı (piyasa kapalı olabilir). Durduruluyor.")
            return

        # 2. Anomali tespiti
        anomalies = detect_anomalies(today)
        logger.info("Anomali sayısı: %d", len(anomalies))

        # 3. Telegram alertleri gönder
        if anomalies:
            send_anomaly_alerts(anomalies, today)

        # 4. Günlük özet gönder
        send_daily_summary(today)

        logger.info("Günlük iş akışı tamamlandı.")

    except Exception as e:
        logger.exception("Günlük iş akışında hata: %s", e)


def start_scheduler():
    """Zamanlayıcıyı başlatır."""
    init_db()

    logger.info("TEFAS Alert Scheduler başlatılıyor...")
    logger.info("Çalışma saati: %s (her gün)", FETCH_TIME)

    schedule.every().day.at(FETCH_TIME).do(run_daily_job)

    logger.info("Scheduler hazır. Bekleniyor...")

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    start_scheduler()
