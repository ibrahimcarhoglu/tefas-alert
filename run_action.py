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

# KESİN YASAKLI KELİMELER (Gürültü Engelleme)
BLACKLIST = {
    'ARE', 'YOU', 'NOT', 'FOR', 'THE', 'AND', 'BUT', 'ALL', 'ANY', 'CAN', 'HAD', 'WAS', 'ITS', 'HIS', 'HER',
    'USD', 'EUR', 'GBP', 'TRY', 'KAP', 'IST', 'BIST', 'GUN', 'SON', 'YAT', 'BOS', 'FON', 'YEN', 'END', 'OUT',
    'GET', 'SET', 'FOR', 'WEB', 'COM', 'NET', 'ORG', 'HTTP', 'HTTPS', 'WWW', 'NEW', 'TOP', 'MAX', 'MIN'
}

def get_deep_insight(code):
    try:
        url = f"https://www.google.com/search?q={code}+fonu+neden+konu%C5%9Fuluyor+haber+detay&tbs=qdr:w"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'lxml')
        results = soup.find_all('div', {'class': 'VwiC3b'})
        if results:
            insight = results[0].get_text()
            return f"Analiz: {insight[:140]}..."
        return "Neden: Yatırımcı ilgisi ve sosyal medya trafiğinde artış."
    except:
        return "Neden: Piyasa gündeminde öne çıkan hareketlilik."

def fetch_twitter_trends(valid_codes):
    """Sadece gerçek fon kodlarını ve gürültüden arındırılmış verileri yakalar."""
    mentions = {}
    try:
        queries = [
            'site:twitter.com "TEFAS" "fonu" gündem',
            'site:twitter.com "$*" yatırım fonu',
            'site:twitter.com "en çok konuşulan fonlar" twitter'
        ]
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        
        for q in queries:
            url = f"https://www.google.com/search?q={q}&tbs=qdr:d"
            res = requests.get(url, headers=headers, timeout=8)
            soup = BeautifulSoup(res.text, 'lxml')
            text = soup.get_text().upper()
            
            # Daha sıkı yakalama: Kelime başında $ veya # olan veya izole duran 3 harfli kodlar
            codes = re.findall(r'[$#]?\b([A-Z]{3})\b', text)
            for c in codes:
                # 1. Yasaklı listede mi? 2. Gerçek fon listesinde mi?
                if c not in BLACKLIST and c in valid_codes:
                    mentions[c] = mentions.get(c, 0) + 1
        return dict(sorted(mentions.items(), key=lambda x: x[1], reverse=True)[:20])
    except:
        return {}

def detect_social_trends(date_str):
    from config import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    
    # Gerçek fon listesini çek ve gürültüleri temizle
    all_db_codes = pd.read_sql_query("SELECT DISTINCT code FROM fund_daily", conn)['code'].tolist()
    valid_codes = [c for c in all_db_codes if c not in BLACKLIST and len(c) == 3]
    
    query = """
    SELECT t1.code as fund_code, t1.num_investors as today, t2.num_investors as yesterday, 
           (CAST(t1.num_investors AS FLOAT) - t2.num_investors) / NULLIF(t2.num_investors, 0) * 100 as growth_pct,
           t1.num_investors - t2.num_investors as growth_count
    FROM fund_daily t1
    JOIN fund_daily t2 ON t1.code = t2.code
    WHERE t1.date = ? AND t2.date = (SELECT MAX(date) FROM fund_daily WHERE date < ?)
    ORDER BY growth_pct DESC
    LIMIT 40
    """
    trends = []
    try:
        df = pd.read_sql_query(query, conn, params=(date_str, date_str))
        twitter_mentions = fetch_twitter_trends(valid_codes)
        
        for _, row in df.iterrows():
            code = row['fund_code']
            # Kod geçerli mi kontrol et
            if code in valid_codes and row['growth_count'] >= 1:
                is_twitter_hot = code in twitter_mentions
                insight = get_deep_insight(code)
                trends.append({
                    "code": code,
                    "growth": f"+%{row['growth_pct']:.2f} (+{int(row['growth_count'])} yeni yatırımcı)",
                    "reason": f"{'🔥 Twitter Gündemi!' if is_twitter_hot else ''}\n{insight}"
                })
        
        # Twitter'daki gerçek kodlar yatırımcıya yansımadıysa bile ekle
        for t_code in twitter_mentions:
            if t_code not in [t['code'] for t in trends] and len(trends) < 10:
                insight = get_deep_insight(t_code)
                trends.append({
                    "code": t_code,
                    "growth": "🚀 Sosyal Medya İvmesi",
                    "reason": insight
                })
                    
        conn.close()
        return sorted(trends, key=lambda x: "🔥" in x['reason'], reverse=True)[:10]
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
