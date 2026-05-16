import logging
import os
import sys
import pandas as pd
import sqlite3
import requests
import re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pytefas import Crawler

sys.path.append(os.getcwd())
from database import init_db, get_recent_data
from fetcher import fetch_and_store
from anomaly import detect_anomalies
from alerts import send_anomaly_alerts, send_daily_summary, send_periodic_summary, send_social_pulse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

def get_news_reason(code):
    """Bir fon kodu için Google'da kısa bir haber taraması yapıp nedenini bulmaya çalışır."""
    try:
        url = f"https://www.google.com/search?q={code}+fonu+neden+konu%C5%9Fuluyor+haberleri&tbs=qdr:w"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'lxml')
        
        # İlk 2-3 arama sonucunun başlığını/snippet'ını al
        results = soup.find_all('h3')
        if results:
            reason = results[0].get_text()
            # Gürültüyü temizle ve biraz kısalt
            return f"Muhtemel Neden: {reason[:80]}..."
        return "Sosyal medyada yoğun trafik tespit edildi."
    except:
        return "Yatırımcı ilgisi ve sosyal medya trafiği artışta."

def fetch_twitter_trends():
    try:
        url = "https://www.google.com/search?q=site:twitter.com+%22fon%22+OR+%22tefas%22+OR+%22%24%22&tbs=qdr:d"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'lxml')
        text = soup.get_text().upper()
        cashtags = re.findall(r'\$([A-Z]{3})', text)
        return pd.Series(cashtags).value_counts().head(10).to_dict()
    except:
        return {}

def detect_social_trends(date_str):
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    query = """
    SELECT t1.code as fund_code, t1.num_investors as today, t2.num_investors as yesterday, 
           (CAST(t1.num_investors AS FLOAT) - t2.num_investors) / NULLIF(t2.num_investors, 0) * 100 as growth_pct,
           t1.num_investors - t2.num_investors as growth_count
    FROM fund_daily t1
    JOIN fund_daily t2 ON t1.code = t2.code
    WHERE t1.date = ? AND t2.date = (SELECT MAX(date) FROM fund_daily WHERE date < ?)
    ORDER BY growth_pct DESC
    LIMIT 30
    """
    trends = []
    try:
        df = pd.read_sql_query(query, conn, params=(date_str, date_str))
        twitter_mentions = fetch_twitter_trends()
        
        for _, row in df.iterrows():
            code = row['fund_code']
            if row['growth_count'] >= 10: # Minimum 10 yeni kişi
                extra = "🔥 Twitter Gündemi!" if code in twitter_mentions else ""
                # Her trend fon için "Neden" bulmaya çalış
                reason = get_news_reason(code)
                trends.append({
                    "code": code,
                    "growth": f"+%{row['growth_pct']:.2f} (+{int(row['growth_count'])} kişi)",
                    "reason": f"{extra} {reason}"
                })
        
        # Twitter'da olup henüz listeye girmeyenler
        for t_code in twitter_mentions:
            if t_code not in [t['code'] for t in trends] and len(trends) < 10:
                reason = get_news_reason(t_code)
                trends.append({
                    "code": t_code,
                    "growth": "Twitter Radarı",
                    "reason": reason
                })
                
        conn.close()
        return trends[:10]
    except Exception as e:
        logger.error("Trend analizi hatası: %s", e)
        return []

def calculate_periodic_top20(latest_date_str, c):
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
        anomalies = detect_anomalies(found_date)
        send_anomaly_alerts(anomalies, found_date)
        
        logger.info("Sosyal medya ve haber trendleri analiz ediliyor...")
        trends = detect_social_trends(found_date)
        send_social_pulse(found_date, trends)
        
        df_today = c.fetch(start=found_date, end=found_date, kind="YAT")
        names_dict = dict(zip(df_today['fund_code'], df_today['fund_name'])) if df_today is not None else {}
        send_daily_summary(found_date, names_dict)
        
        periodic_results = calculate_periodic_top20(found_date, c)
        if periodic_results:
            send_periodic_summary(found_date, periodic_results)

if __name__ == "__main__":
    run_once()
