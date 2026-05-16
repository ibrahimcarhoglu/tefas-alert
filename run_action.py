import logging
import os
from datetime import datetime
from database import init_db
from fetcher import fetch_and_store
from anomaly import detect_anomalies
from alerts import send_anomaly_alerts, send_daily_summary

# Log ayarları
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

def run_once():
    """GitHub Actions için tek seferlik iş akışı."""
    os.makedirs("data", exist_ok=True)
    init_db()
    
    today = datetime.today().strftime("%Y-%m-%d")
    logger.info("GitHub Action iş akışı başlıyor: %s", today)

    try:
        # 1. Veri çek
        count = fetch_and_store(today)
        if count == 0:
            logger.info("Veri bulunamadı veya piyasa kapalı. Durduruluyor.")
            return

        # 2. Anomali tespiti
        anomalies = detect_anomalies(today)
        logger.info("Anomali sayısı: %d", len(anomalies))

        # 3. Telegram alertleri gönder
        if anomalies:
            send_anomaly_alerts(anomalies, today)

        # 4. Günlük özet gönder
        send_daily_summary(today)

        logger.info("İş akışı başarıyla tamamlandı.")

    except Exception as e:
        logger.exception("İş akışında hata: %s", e)

if __name__ == "__main__":
    run_once()
