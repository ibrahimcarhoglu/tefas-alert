import logging
import os
import sys
from datetime import datetime

# GitHub Actions'da mevcut klasörü path'e ekle
sys.path.append(os.getcwd())

from database import init_db
from fetcher import fetch_and_store
from anomaly import detect_anomalies
from alerts import send_anomaly_alerts, send_daily_summary

# Log ayarları - Daha detaylı
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

def run_once():
    """GitHub Actions için tek seferlik iş akışı."""
    try:
        # 0. Hazırlık
        os.makedirs("data", exist_ok=True)
        init_db()
        
        # Bugünün tarihini al (veya Cuma gününü zorla eğer haftasonuysa test için)
        # GitHub Actions'da tarih UTC olduğu için bazen kaymalar olabilir
        today = datetime.today().strftime("%Y-%m-%d")
        logger.info("GitHub Action iş akışı başlıyor (Tarih: %s)", today)

        # 1. Veri çek
        # Not: Haftasonu veri gelmeyebilir, test için son işlem gününü bulmaya çalışabiliriz
        count = fetch_and_store(today)
        
        if count == 0:
            logger.warning("Veri bulunamadı. Bugün hafta sonu veya tatil olabilir.")
            # Hata olarak saymıyoruz, sadece uyarıyoruz
            return

        # 2. Anomali tespiti
        anomalies = detect_anomalies(today)
        logger.info("Tespit edilen anomali sayısı: %d", len(anomalies))

        # 3. Telegram alertleri gönder
        if anomalies:
            send_anomaly_alerts(anomalies, today)

        # 4. Günlük özet gönder
        send_daily_summary(today)

        logger.info("İş akışı başarıyla tamamlandı.")

    except Exception as e:
        logger.error("KRİTİK HATA: %s", str(e), exc_info=True)
        # GitHub Action'ın fail vermesi için hatayı fırlatıyoruz
        sys.exit(1)

if __name__ == "__main__":
    run_once()
