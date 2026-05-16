import logging
import os
import sys
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from pytefas import Crawler

sys.path.append(os.getcwd())
from database import init_db, get_recent_data
from fetcher import fetch_and_store
from anomaly import detect_anomalies
from alerts import send_anomaly_alerts, send_daily_summary, send_periodic_summary, send_social_pulse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def detect_social_trends(date_str):
    """Yatırımcı sayısı artış hızından sosyal trendleri yakalar."""
    conn = sqlite3.connect("data/tefas.db")
    
    # Bugünün ve dünün verilerini karşılaştır
    query = f"""
    SELECT t1.fund_code, t1.num_investors as today, t2.num_investors as yesterday, 
           (CAST(t1.num_investors AS FLOAT) - t2.num_investors) / NULLIF(t2.num_investors, 0) * 100 as growth_pct,
           t1.num_investors - t2.num_investors as growth_count
    FROM daily_stats t1
    JOIN daily_stats t2 ON t1.fund_code = t2.fund_code
    WHERE t1.date = ? AND t2.date = (SELECT MAX(date) FROM daily_stats WHERE date < ?)
    ORDER BY growth_pct DESC
    LIMIT 10
    """
    try:
        df = pd.read_sql_query(query, conn, params=(date_str, date_str))
        conn.close()
        
        trends = []
        for _, row in df.iterrows():
            if row['growth_count'] > 50: # En az 50 yeni yatırımcı (küçük dalgalanmaları ele)
                trends.append({
                    "code": row['fund_code'],
                    "growth": f"+%{row['growth_pct']:.2f} (🚀 {int(row['growth_count'])} yeni kişi)",
                    "reason": "Yatırımcı sayısında anormal artış. Sosyal medyada ilgi odağı olabilir."
                })
        return trends
    except Exception as e:
        logger.error("Trend tespiti hatası: %s", e)
        return []

def calculate_periodic_top20(latest_date_str, c):
    # (Önceki esnek kod mantığını koruyoruz)
    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
    df_raw = c.fetch(start=latest_date_str, end=latest_date_str, kind="YAT")
    if df_raw is None or df_raw.empty: return {}
    
    cols = df_raw.columns.tolist()
    code_col = next((c for c in ['fund_code', 'code'] if c in cols), 'fund_code')
    name_col = next((c for c in ['fund_name', 'name'] if c in cols), 'fund_name')
    
    df_latest = df_raw[[code_col, 'price', name_col]].rename(columns={'price': 'p_lat', code_col: 'fund_code', name_col: 'fund_name'})
    
    periods = {"3 Gün": 3, "1 Hafta": 7, "1 Ay": 30}
    results = {}

    for label, days in periods.items():
        target = latest_date - timedelta(days=days)
        for i in range(7):
            check = (target - timedelta(days=i)).strftime("%Y-%m-%d")
            df_prev = c.fetch(start=check, end=check, kind="YAT")
            if df_prev is not None and not df_prev.empty:
                df_p = df_prev[[code_col, 'price']].rename(columns={'price': 'p_pre', code_col: 'fund_code'})
                df = pd.merge(df_latest, df_p, on='fund_code')
                df['pct_change'] = (df['p_lat'] - df['p_pre']) / df['p_pre'] * 100
                results[label] = df.sort_values(by='pct_change', ascending=False).head(15)
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
        # 1. Anomaliler
        anomalies = detect_anomalies(found_date)
        send_anomaly_alerts(anomalies, found_date)
        
        # 2. Sosyal Trendler (Yeni Bölüm)
        logger.info("Sosyal medya trendleri analiz ediliyor...")
        trends = detect_social_trends(found_date)
        if trends:
            send_social_pulse(found_date, trends)
        
        # 3. Günlük ve Periyodik Raporlar
        df_today = c.fetch(start=found_date, end=found_date, kind="YAT")
        names_dict = dict(zip(df_today['fund_code'], df_today['fund_name'])) if df_today is not None else {}
        send_daily_summary(found_date, names_dict)
        
        periodic_results = calculate_periodic_top20(found_date, c)
        if periodic_results:
            send_periodic_summary(found_date, periodic_results)

if __name__ == "__main__":
    run_once()
