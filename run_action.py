import logging
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from pytefas import Crawler

# GitHub Actions'da mevcut klasörü path'e ekle
sys.path.append(os.getcwd())

from database import init_db
from fetcher import fetch_and_store
from anomaly import detect_anomalies
from alerts import send_anomaly_alerts, send_daily_summary, send_periodic_summary

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def calculate_periodic_top20(latest_date_str, c):
    """3g, 1h, 2h, 1a, 7h periyotları için Top 20 hesaplar."""
    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
    df_latest = c.fetch(start=latest_date_str, end=latest_date_str, kind="YAT")
    if df_latest is None or df_latest.empty: return {}
    df_latest = df_latest[['fund_code', 'price']].rename(columns={'price': 'p_lat'})
    
    periods = {"3 Gün": 3, "1 Hafta": 7, "2 Hafta": 14, "1 Ay": 30, "7 Hafta": 49}
    results = {}

    for label, days in periods.items():
        target = latest_date - timedelta(days=days)
        for i in range(5): # Geriye dönük 5 gün dene (haftasonu/tatil için)
            check = (target - timedelta(days=i)).strftime("%Y-%m-%d")
            df_prev = c.fetch(start=check, end=check, kind="YAT")
            if df_prev is not None and not df_prev.empty:
                df_prev = df_prev[['fund_code', 'price']].rename(columns={'price': 'p_pre'})
                df = pd.merge(df_latest, df_prev, on='fund_code')
                df['pct_change'] = (df['p_lat'] - df['p_pre']) / df['p_pre'] * 100
                results[label] = df.sort_values(by='pct_change', ascending=False).head(20)
                break
    return results

def run_once():
    init_db()
    c = Crawler()
    today_dt = datetime.today()
    
    found_date = None
    for i in range(4):
        date_str = (today_dt - timedelta(days=i)).strftime("%Y-%m-%d")
        if fetch_and_store(date_str) > 0:
            found_date = date_str
            break
    
    if found_date:
        # 1. Anomali ve Günlük Özet
        anomalies = detect_anomalies(found_date)
        send_anomaly_alerts(anomalies, found_date)
        send_daily_summary(found_date)
        
        # 2. Periyodik Top 20 (Yeni İstek)
        logger.info("Periyodik analiz yapılıyor...")
        periodic_results = calculate_periodic_top20(found_date, c)
        if periodic_results:
            send_periodic_summary(found_date, periodic_results)
        
        logger.info("Tüm raporlar gönderildi.")
    else:
        logger.warning("İşlenecek veri bulunamadı.")

if __name__ == "__main__":
    run_once()
