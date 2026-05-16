import logging
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from pytefas import Crawler

sys.path.append(os.getcwd())
from database import init_db
from fetcher import fetch_and_store
from anomaly import detect_anomalies
from alerts import send_anomaly_alerts, send_daily_summary, send_periodic_summary

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def get_flexible_df(df, price_suffix):
    """Sütun isimleri ne olursa olsun (code/fund_code, name/fund_name) bulur ve temizler."""
    if df is None or df.empty: return None
    cols = df.columns.tolist()
    
    # Esnek sütun eşleştirme
    code_col = next((c for c in ['fund_code', 'code', 'Kod'] if c in cols), None)
    name_col = next((c for c in ['fund_name', 'name', 'Fon Adı'] if c in cols), None)
    price_col = next((c for c in ['price', 'Birim Pay Değeri'] if c in cols), None)
    
    if not code_col or not price_col:
        logger.error("Gerekli sütunlar bulunamadı! Mevcutlar: %s", cols)
        return None
        
    res = df[[code_col, price_col]].copy()
    res.columns = ['fund_code', f'p_{price_suffix}']
    if name_col:
        res['fund_name'] = df[name_col]
    else:
        res['fund_name'] = ""
        
    return res

def calculate_periodic_top20(latest_date_str, c):
    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
    df_raw = c.fetch(start=latest_date_str, end=latest_date_str, kind="YAT")
    df_latest = get_flexible_df(df_raw, 'lat')
    
    if df_latest is None: return {}
    
    periods = {"3 Gün": 3, "1 Hafta": 7, "2 Hafta": 14, "1 Ay": 30, "7 Hafta": 49}
    results = {}

    for label, days in periods.items():
        target = latest_date - timedelta(days=days)
        logger.info("%s için hedef tarih: %s", label, target.strftime("%Y-%m-%d"))
        for i in range(7): # 7 gün geriye tara (daha garanti)
            check = (target - timedelta(days=i)).strftime("%Y-%m-%d")
            df_prev_raw = c.fetch(start=check, end=check, kind="YAT")
            df_prev = get_flexible_df(df_prev_raw, 'pre')
            
            if df_prev is not None:
                df = pd.merge(df_latest, df_prev[['fund_code', 'p_pre']], on='fund_code')
                df['pct_change'] = (df['p_lat'] - df['p_pre']) / df['p_pre'] * 100
                results[label] = df.sort_values(by='pct_change', ascending=False).head(20)
                logger.info("%s bulundu (%s)", label, check)
                break
    return results

def run_once():
    init_db()
    c = Crawler()
    today_dt = datetime.today()
    
    found_date = None
    for i in range(5):
        date_str = (today_dt - timedelta(days=i)).strftime("%Y-%m-%d")
        if fetch_and_store(date_str) > 0:
            found_date = date_str
            break
    
    if found_date:
        logger.info("İşlem tarihi: %s", found_date)
        # 1. Anomali
        anomalies = detect_anomalies(found_date)
        send_anomaly_alerts(anomalies, found_date)
        
        # 2. Günlük Özet
        df_today = c.fetch(start=found_date, end=found_date, kind="YAT")
        df_flex = get_flexible_df(df_today, 'today')
        names_dict = dict(zip(df_flex['fund_code'], df_flex['fund_name'])) if df_flex is not None else {}
        send_daily_summary(found_date, names_dict)
        
        # 3. Periyodik Analiz
        periodic_results = calculate_periodic_top20(found_date, c)
        if periodic_results:
            send_periodic_summary(found_date, periodic_results)
        else:
            logger.warning("Periyodik analiz sonuç üretemedi!")
    else:
        logger.warning("Veri bulunamadı.")

if __name__ == "__main__":
    run_once()
