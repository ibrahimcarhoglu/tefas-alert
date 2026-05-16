import logging
import os
import sys
import asyncio
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

# Tarayıcı gibi görünmek için genişletilmiş header seti
HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'tr,en-US;q=0.7,en;q=0.3',
    'Referer': 'https://www.google.com/'
}

def get_deep_insight(code, name=""):
    """Google News RSS (XML) yardımıyla en temiz, güncel 'Neden' bilgisini çeker ve anlamsal fallback üretir."""
    # 1. Google News RSS Taraması (Captcha ve redirect engelini 100% aşar)
    try:
        query = f"{code} fonu"
        url = f"https://news.google.com/rss/search?q={query}&hl=tr&gl=TR&ceid=TR:tr"
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'xml')
            items = soup.find_all('item')
            if items:
                title = items[0].title.text
                # Kaynak adını temizle (örn: "- Bloomberg HT")
                clean_title = re.sub(r'\s*-\s*.*$', '', title)
                return f"Analiz: {clean_title[:120]}..."
    except Exception as e:
        logger.warning(f"Google News RSS hatası ({code}): {e}")

    # 2. Akıllı Semantik Gerekçe Çıkarımı (Eğer haber bulunamazsa isim kelimelerinden yakalar)
    name_upper = name.upper()
    if "ALTIN" in name_upper:
        return "Analiz: Altın fiyatlarındaki küresel yükseliş ve güvenli liman talebinin etkisi."
    elif "GÜMÜŞ" in name_upper:
        return "Analiz: Gümüş emtiasındaki yukarı yönlü güçlü kırılım ve yatırımcı ilgisi."
    elif "PETROL" in name_upper or "ENERJİ" in name_upper:
        return "Analiz: Petrol fiyatlarındaki hareketlilik ve enerji sektörü fonlarına artan yönelim."
    elif "TEKNOLOJİ" in name_upper or "YARI İLETKEN" in name_upper:
        return "Analiz: Küresel teknoloji devlerindeki (Nasdaq, Nvidia) ralli ve sektörel beklentiler."
    elif "EUROBOND" in name_upper or "YABANCI" in name_upper:
        return "Analiz: Döviz kurlarındaki hareketler ve yabancı varlık cinsi getiri arayışı."
    elif "HİSSE" in name_upper or "BİST" in name_upper:
        return "Analiz: BIST 100 endeksindeki hisse senedi yoğun getiri arayışı ve portföy rotasyonları."
    elif "SERBEST" in name_upper:
        return "Analiz: Nitelikli yatırımcıların yüksek getiri ve esnek portföy yönetimi stratejilerine olan ilgisi."
    
    return "Analiz: Sosyal medyadaki stratejik yatırımcı ilgisi ve artan fon hareketliliği."

def fetch_twitter_trends(valid_codes):
    """
    X (Twitter) üzerindeki finansal cashtag ($) ve hashtag (#) yoğunluğunu 
    Serper.dev API kullanarak doğrudan geçerli fon kodlarıyla eşleştirir.
    CAPTCHA ve bot engellerini tamamen aşar.
    """
    import json
    mentions = {}
    if not valid_codes:
        return mentions
        
    api_key = os.getenv("SERPER_API_KEY", "")
    if not api_key:
        print("Uyarı: SERPER_API_KEY bulunamadı (.env dosyasına ekleyin). X taraması atlanıyor.")
        return mentions

    # Tek seferde (kredi harcamasını minimize ederek) Fintwit'in kalbini vuran optimize sorgular
    queries = [
        # 1. Ana Damar: İçinde TEFAS veya Fon kelimesi geçen ve doğrudan Cashtag ($) içeren tweetler
        'site:twitter.com ("tefas" OR "yatırım fonu" OR "fonlar") "$"',
        
        # 2. Aksiyon ve Popülerlik: Yatırımcıların alım/satım veya "en iyi" muhabbeti döndürdüğü tweetler
        'site:twitter.com "fon" ("aldım" OR "portföy" OR "kazandıran" OR "gündem")'
    ]
    
    url = "https://google.serper.dev/search"
    headers = {
      'X-API-KEY': api_key,
      'Content-Type': 'application/json'
    }
    
    try:
        for q in queries:
            payload = json.dumps({
              "q": q,
              "tbs": "qdr:d",
              "gl": "tr",
              "hl": "tr"
            })
            res = requests.post(url, headers=headers, data=payload, timeout=10)
            
            if res.status_code != 200:
                print(f"Serper API hatası: {res.status_code}")
                continue
                
            data = res.json()
            organics = data.get("organic", [])
            
            # API'den dönen tüm özet (snippet) metinlerini birleştir
            text_pool = " ".join([item.get("snippet", "").upper() for item in organics if "snippet" in item])
            
            # Finansal Cashtag ($) ve Hashtag (#) bazlı fon yakalama
            # Sadece 3 harfli büyük harf kombinasyonlarını arar
            potential_codes = re.findall(r'[\$\#\b]([A-Z]{3})\b', text_pool)
            
            for c in potential_codes:
                if c in valid_codes:
                    # Cashtag ile ($) doğrudan hedef gösterildiyse ilgiyi 2 kat say
                    weight = 2 if f"${c}" in text_pool else 1
                    mentions[c] = mentions.get(c, 0) + weight
                    
        # En çok konuşulan ilk 20 fonu sırala
        return dict(sorted(mentions.items(), key=lambda x: x[1], reverse=True)[:20])
    except Exception as e:
        print(f"X Trend tarama hatası (Serper): {e}")
        return {}

def detect_social_trends(date_str, names_dict=None):
    """
    TEFAS Yatırımcı Değişimi ile X (Twitter) verilerini korele ederek 
    hibrit bir 'Trend Skor' üretir.
    """
    from config import DB_PATH
    names_dict = names_dict or {}
    
    conn = sqlite3.connect(DB_PATH)
    all_db_codes = pd.read_sql_query("SELECT DISTINCT code FROM fund_daily", conn)['code'].tolist()
    # Sadece 3 harfli fon kodlarını geçerli kabul et (Blacklist filtresi kaldırıldı)
    valid_codes = [c for c in all_db_codes if len(c) == 3]
    
    # Son gün ile bir önceki günün yatırımcı farkı
    query = """
    SELECT t1.code as fund_code, t1.num_investors as today, t2.num_investors as yesterday, 
           (CAST(t1.num_investors AS FLOAT) - t2.num_investors) / NULLIF(t2.num_investors, 0) * 100 as growth_pct,
           t1.num_investors - t2.num_investors as growth_count
    FROM fund_daily t1
    JOIN fund_daily t2 ON t1.code = t2.code
    WHERE t1.date = ? AND t2.date = (SELECT MAX(date) FROM fund_daily WHERE date < ?)
    ORDER BY growth_count DESC
    LIMIT 50
    """
    
    trends = []
    try:
        df = pd.read_sql_query(query, conn, params=(date_str, date_str))
        
        # X (Twitter) verilerini çek
        twitter_mentions = fetch_twitter_trends(valid_codes)
        
        # 1. Aşama: Hem veritabanında büyüyen hem de X'te konuşulanlar (Hibrit Skorlama)
        for _, row in df.iterrows():
            code = row['fund_code']
            if code not in valid_codes or row['growth_count'] < 1:
                continue
                
            tw_count = twitter_mentions.get(code, 0)
            is_twitter_hot = tw_count > 0
            
            # Hibrit Trend Puanı Hesaplama
            social_score = (row['growth_pct'] * 1.5) + (tw_count * 2.0)
            
            name = names_dict.get(code, "")
            insight = get_deep_insight(code, name)
            
            trends.append({
                "code": code,
                "pct": f"+%{row['growth_pct']:.2f}",
                "stat": f"+{int(row['growth_count'])} kişi (X Skoru: {tw_count})",
                "reason": f"🔥 [Fintwit Gündemi] {insight}" if is_twitter_hot else insight,
                "score": social_score
            })
        
        # 2. Aşama: TEFAS'ta henüz veri yansımamış ama X'te fırtınalar koparanlar
        for t_code, tw_count in twitter_mentions.items():
            if t_code not in [t['code'] for t in trends] and len(trends) < 15:
                name = names_dict.get(t_code, "")
                insight = get_deep_insight(t_code, name)
                trends.append({
                    "code": t_code,
                    "pct": "🚀",
                    "stat": f"X / Fintwit Yoğun İlgi (Skor: {tw_count})",
                    "reason": f"⚡ {insight}",
                    "score": tw_count * 3.0
                })
                    
        conn.close()
        
        # Trendleri ürettikleri toplam skora göre büyükten küçüğe sırala (İlk 10)
        return sorted(trends, key=lambda x: x['score'], reverse=True)[:10]
        
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
        asyncio.run(send_anomaly_alerts(anomalies, found_date))
        
        logger.info("Sosyal medya ve haber trendleri analiz ediliyor...")
        df_today = c.fetch(start=found_date, end=found_date, kind="YAT")
        names_dict = dict(zip(df_today['fund_code'], df_today['fund_name'])) if df_today is not None else {}
        
        trends = detect_social_trends(found_date, names_dict)
        asyncio.run(send_social_pulse(found_date, trends))
        
        asyncio.run(send_daily_summary(found_date, names_dict))
        
        periodic_results = calculate_periodic_top20(found_date, c)
        if periodic_results:
            asyncio.run(send_periodic_summary(found_date, periodic_results))

if __name__ == "__main__":
    run_once()
