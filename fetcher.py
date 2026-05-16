import logging
from datetime import datetime, timedelta

import pandas as pd
from pytefas import Crawler

from config import FUND_TYPE
from database import insert_fund_data

logger = logging.getLogger(__name__)


def fetch_and_store(date: str = None):
    """
    TEFAS'tan belirtilen tarih (varsayılan: bugün) için tüm fon verilerini çeker
    ve hesaplanan net_flow ile birlikte veritabanına kaydeder.
    """
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")

    prev_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

    logger.info("TEFAS'tan veri çekiliyor (pytefas): %s (+ önceki gün: %s)", date, prev_date)

    tefas = Crawler()

    # Bugün verisi
    try:
        df_today = tefas.fetch(
            start=date,
            end=date,
            kind=FUND_TYPE
        )
    except Exception as e:
        logger.error("Bugün verisi çekilemedi: %s", e)
        raise

    # Önceki gün verisi (net flow hesabı için)
    try:
        df_prev = tefas.fetch(
            start=prev_date,
            end=prev_date,
            kind=FUND_TYPE
        )
    except Exception as e:
        logger.warning("Önceki gün verisi çekilemedi: %s — Net flow hesaplanamayacak.", e)
        df_prev = pd.DataFrame()

    if df_today is None or df_today.empty:
        logger.warning("TEFAS'tan bugün için boş veri döndü. Piyasa kapalı olabilir.")
        return 0

    # Kolon eşleme: pytefas -> database
    # pytefas: fund_code, portfolio_size, investor_count, shares_outstanding
    # database: code, market_cap, num_investors, num_shares
    
    df_today = df_today.rename(columns={
        "fund_code": "code",
        "portfolio_size": "market_cap",
        "investor_count": "num_investors",
        "shares_outstanding": "num_shares",
    })
    
    if not df_prev.empty:
        df_prev = df_prev.rename(columns={
            "fund_code": "code",
            "portfolio_size": "market_cap",
            "investor_count": "num_investors",
            "shares_outstanding": "num_shares",
        })

    records = []

    for _, row in df_today.iterrows():
        code = row.get("code", "")
        price_today = row.get("price") or 0
        market_cap_today = row.get("market_cap") or 0
        num_investors_today = int(row.get("num_investors") or 0)
        num_shares_today = row.get("num_shares") or 0

        # Önceki gün verisi
        net_flow = None
        pct_change = None
        investor_change = None

        if not df_prev.empty:
            prev_row = df_prev[df_prev["code"] == code]
            if not prev_row.empty:
                prev_row = prev_row.iloc[0]
                price_prev = prev_row.get("price") or 0
                market_cap_prev = prev_row.get("market_cap") or 0
                num_investors_prev = int(prev_row.get("num_investors") or 0)

                # Net para akışı hesabı:
                # Getiri etkisi arındırılmış market cap değişimi
                if market_cap_prev > 0 and price_prev > 0:
                    price_return = (price_today - price_prev) / price_prev
                    # Fiyat değişimi kaynaklı market cap artışı
                    price_effect = market_cap_prev * price_return
                    # Gerçek para akışı = toplam değişim - fiyat etkisi
                    net_flow = (market_cap_today - market_cap_prev) - price_effect
                    pct_change = price_return * 100

                investor_change = num_investors_today - num_investors_prev

        records.append({
            "date": date,
            "code": code,
            "price": price_today,
            "market_cap": market_cap_today,
            "num_investors": num_investors_today,
            "num_shares": num_shares_today,
            "net_flow": net_flow,
            "pct_change": pct_change,
            "investor_change": investor_change,
        })

    insert_fund_data(records)
    logger.info("Toplam %d fon verisi işlendi ve kaydedildi.", len(records))
    return len(records)


def fetch_historical(start: str, end: str):
    """
    Geçmiş veriyi toplu çeker (ilk kurulumda geçmiş doldurma için).
    """
    import time
    
    logger.info("Geçmiş veri çekiliyor (pytefas): %s -> %s", start, end)
    
    # pytefas zaten aralık destekliyor, ama tek tek günler için net flow hesabı lazım
    # Bu yüzden fetch_and_store'u her gün için çağırmak daha mantıklı
    
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    
    current = start_dt
    total = 0
    
    while current <= end_dt:
        date_str = current.strftime("%Y-%m-%d")
        logger.info("İşleniyor: %s", date_str)
        try:
            count = fetch_and_store(date_str)
            total += count
        except Exception as e:
            logger.error("Hata (%s): %s", date_str, e)
        
        current += timedelta(days=1)
        time.sleep(0.5)  # Rate limit önlemi
        
    logger.info("Geçmiş veri yükleme tamamlandı. Toplam: %d kayıt", total)
    return total

