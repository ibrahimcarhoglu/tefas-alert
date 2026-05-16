import logging
import os
import sys
from datetime import datetime, timedelta

# GitHub Actions'da mevcut klasörü path'e ekle
sys.path.append(os.getcwd())

from database import init_db
from fetcher import fetch_and_store
from anomaly import detect_anomalies
from alerts import send_anomaly_alerts, send_daily_summary

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

def run_once():
    """GitHub Actions için tek seferlik iş akışı."""
    try:
        os.makedirs("data", exist_ok=True)
        init_db()
        
        # Bugünün verisini çekmeyi dene, yoksa geriye doğru 3 gün tara
        found = False
        target_date = datetime.today()
        
        for i in range(4): # Bugün, dün, evvelsi gün...
            date_str = (target_date - timedelta(days=i)).strftime("%Y-%m-%d")
            logger.info("%s tarihi için deneniyor...", date_str)
            
            count = fetch_and_store(date_str)
            if count > 0:
                logger.info("%s tarihi için %d kayıt bulundu ve işlendi.", date_str, count)
                
                # Anomali ve özet işlemleri
                anomalies = detect_anomalies(date_str)
                if anomalies:
                    send_anomaly_alerts(anomalies, date_str)
                
                send_daily_summary(date_str)
                found = True
                break
        
        if not found:
            logger.warning("Son 4 gün içinde işlenecek veri bulunamadı.")
        else:
            logger.info("İş akışı başarıyla tamamlandı.")

    except Exception as e:
        logger.error("KRİTİK HATA: %s", str(e), exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    run_once()
