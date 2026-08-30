import logging
from datetime import datetime, timedelta
import sqlite3
import json

import numpy as np
import pandas as pd
from pytefas import Crawler

from config import FUND_TYPE
from database import insert_fund_data, get_connection, save_fund_breakdown, save_fund_names

logger = logging.getLogger(__name__)


def fetch_and_store(date: str = None, include_breakdown: bool = True):
    """
    TEFAS'tan belirtilen tarih (varsayılan: bugün) için tüm fon verilerini çeker
    ve hesaplanan net_flow ile birlikte veritabanına kaydeder.
    """
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")

    logger.info("TEFAS'tan veri çekiliyor (pytefas): %s", date)

    tefas = Crawler()

    # Bugün verisi (tüm fon türleri için çekilir)
    dfs = []
    breakdown_list = []

    for kind in ["YAT", "BYF", "EYF"]:
        logger.info("TEFAS'tan %s verisi çekiliyor...", kind)
        crawler_kind = "EMK" if kind == "EYF" else kind
        try:
            df_kind = tefas.fetch(
                start=date,
                end=date,
                kind=crawler_kind
            )
            if df_kind is not None and not df_kind.empty:
                dfs.append(df_kind.dropna(axis=1, how="all"))
        except Exception as e:
            logger.warning("Tür %s için bugün verisi çekilemedi: %s", kind, e)

        # Sinyal geçmişi doldurulurken breakdown gerekli değildir; üç ek ağ
        # isteğini atlayarak taramayı belirgin biçimde hızlandırır.
        if include_breakdown:
            try:
                df_breakdown = tefas.fetch(
                    start=date,
                    end=date,
                    kind=crawler_kind,
                    columns="breakdown"
                )
                if df_breakdown is not None and not df_breakdown.empty:
                    for _, row in df_breakdown.iterrows():
                        row_dict = row.dropna().to_dict()
                        code = row_dict.get('fund_code')
                        if not code:
                            continue
                        # Filtrele: Sadece _pct ile biten ve değeri > 0 olanları al
                        alloc = {k: float(v) for k, v in row_dict.items() if k.endswith('_pct') and isinstance(v, (int, float)) and v > 0}
                        if alloc:
                            breakdown_list.append({
                                "code": code,
                                "allocation_json": json.dumps(alloc)
                            })
            except Exception as e:
                logger.warning("Tür %s için varlık dağılımı çekilemedi: %s", kind, e)

    if not dfs:
        logger.warning("TEFAS'tan hiçbir fon türü için bugün veri dönmedi. Piyasa kapalı olabilir.")
        return 0

    df_today = pd.concat(dfs, ignore_index=True)
    if {"fund_code", "fund_name"}.issubset(df_today.columns):
        names = (
            df_today[["fund_code", "fund_name"]]
            .dropna()
            .drop_duplicates("fund_code", keep="last")
        )
        save_fund_names(dict(zip(names["fund_code"], names["fund_name"])))
    if breakdown_list:
        save_fund_breakdown(date, breakdown_list)
        logger.info("%d adet varlık dağılımı (breakdown) kaydedildi.", len(breakdown_list))

    # Önceki gün verisini bul ve getir (net flow hesabı için)
    df_prev = pd.DataFrame()
    
    # 1. Öncelik: Veritabanındaki en güncel önceki tarihi bulup oradan okumak
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(date) FROM fund_daily WHERE date < ?", (date,))
        db_prev_date = cursor.fetchone()[0]
        if db_prev_date:
            logger.info("Önceki gün verisi yerel veritabanından okunuyor (tarih: %s)", db_prev_date)
            df_prev = pd.read_sql_query(
                "SELECT code, price, market_cap, num_investors, num_shares FROM fund_daily WHERE date = ?",
                conn,
                params=(db_prev_date,)
            )
        conn.close()
    except Exception as e:
        logger.warning("Yerel veritabanından önceki gün verisi okunamadı: %s", e)

    # 2. Öncelik: Eğer veritabanı boşsa veya veri yoksa, geriye doğru günleri tek tek internetten dene (maksimum 5 gün)
    if df_prev.empty:
        for offset in range(1, 6):
            check_date = (datetime.strptime(date, "%Y-%m-%d") - timedelta(days=offset)).strftime("%Y-%m-%d")
            try:
                logger.info("Önceki gün verisi internetten aranıyor (tarih: %s)...", check_date)
                prev_dfs = []
                for kind in ["YAT", "BYF", "EYF"]:
                    crawler_kind = "EMK" if kind == "EYF" else kind
                    df_prev_fetched = tefas.fetch(
                        start=check_date,
                        end=check_date,
                        kind=crawler_kind
                    )
                    if df_prev_fetched is not None and not df_prev_fetched.empty:
                        prev_dfs.append(df_prev_fetched)
                if prev_dfs:
                    df_prev = pd.concat(prev_dfs, ignore_index=True)
                    logger.info("Önceki gün verisi internetten başarıyla çekildi (tarih: %s)", check_date)
                    break
            except Exception as e:
                logger.warning("%s tarihi için veri çekilemedi: %s", check_date, e)

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

    # Her fon için DataFrame'i tekrar tekrar filtrelemek binlerce fonluk günde
    # O(n²) maliyet yaratıyordu. Kod bazlı sözlük günlük eşleştirmeyi O(n) yapar.
    prev_lookup = (
        df_prev.drop_duplicates("code", keep="last").set_index("code").to_dict("index")
        if not df_prev.empty and "code" in df_prev.columns
        else {}
    )

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

        if prev_lookup:
            prev_row = prev_lookup.get(code)
            if prev_row is not None:
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


def fetch_range_and_store(start: str, end: str) -> int:
    """Bir tarih aralığını toplu çekip günlük değişkenleri vektörel hesaplar.

    Sinyal tarayıcısının eksik tarihleri tamamlaması için optimize edilmiştir;
    varlık dağılımı çekmez ve genel web katmanına bağımlı değildir.
    """
    logger.info("TEFAS toplu veri çekimi: %s -> %s", start, end)
    crawler = Crawler()
    frames = []
    for kind in ("YAT", "BYF", "EMK"):
        try:
            frame = crawler.fetch(start=start, end=end, kind=kind)
            if frame is not None and not frame.empty:
                frames.append(frame.dropna(axis=1, how="all"))
        except Exception as exc:
            logger.warning("Tür %s için toplu veri çekilemedi: %s", kind, exc)
    if not frames:
        return 0

    data = pd.concat(frames, ignore_index=True)
    if {"fund_code", "fund_name"}.issubset(data.columns):
        names = data[["fund_code", "fund_name"]].dropna().drop_duplicates("fund_code", keep="last")
        save_fund_names(dict(zip(names["fund_code"], names["fund_name"])))

    data = data.rename(columns={
        "fund_code": "code",
        "portfolio_size": "market_cap",
        "investor_count": "num_investors",
        "shares_outstanding": "num_shares",
    })
    required = ["date", "code", "price", "market_cap", "num_investors", "num_shares"]
    missing = [column for column in required if column not in data.columns]
    if missing:
        raise ValueError(f"TEFAS toplu yanıtında gerekli kolonlar eksik: {missing}")
    data = data[required].copy()
    data["date"] = pd.to_datetime(data["date"]).dt.strftime("%Y-%m-%d")
    data = data.dropna(subset=["date", "code"]).drop_duplicates(["date", "code"], keep="last")
    for column in ("price", "market_cap", "num_investors", "num_shares"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data["_new"] = True

    conn = get_connection()
    previous = pd.read_sql_query(
        """
        SELECT fd.date, fd.code, fd.price, fd.market_cap, fd.num_investors, fd.num_shares
        FROM fund_daily fd
        JOIN (
            SELECT code, MAX(date) AS previous_date
            FROM fund_daily WHERE date < ? GROUP BY code
        ) p ON p.code = fd.code AND p.previous_date = fd.date
        """,
        conn,
        params=(start,),
    )
    conn.close()
    if not previous.empty:
        previous["_new"] = False
        combined = pd.concat([previous, data], ignore_index=True)
    else:
        combined = data.copy()
    combined = combined.sort_values(["code", "date"])

    groups = combined.groupby("code", observed=True)
    previous_price = groups["price"].shift(1)
    previous_market_cap = groups["market_cap"].shift(1)
    previous_investors = groups["num_investors"].shift(1)
    valid_previous = (previous_price > 0) & (previous_market_cap > 0)
    price_return = combined["price"] / previous_price - 1
    combined["pct_change"] = np.where(valid_previous, price_return * 100, np.nan)
    combined["net_flow"] = np.where(
        valid_previous,
        combined["market_cap"] - previous_market_cap - previous_market_cap * price_return,
        np.nan,
    )
    combined["investor_change"] = combined["num_investors"] - previous_investors

    output = combined[combined["_new"]].drop(columns="_new")
    records = output.where(pd.notna(output), None).to_dict("records")
    insert_fund_data(records)
    logger.info("Toplu TEFAS güncellemesi tamamlandı: %d kayıt", len(records))
    return len(records)
