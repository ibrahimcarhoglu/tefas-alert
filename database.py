import sqlite3
import os
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    """Veritabanını ve tabloları oluşturur."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS fund_daily (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            date         TEXT NOT NULL,
            code         TEXT NOT NULL,
            price        REAL,
            market_cap   REAL,
            num_investors INTEGER,
            num_shares   REAL,
            net_flow     REAL,
            pct_change   REAL,
            investor_change INTEGER,
            created_at   TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(date, code)
        );

        CREATE TABLE IF NOT EXISTS alerts_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT NOT NULL,
            code       TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            value      REAL,
            z_score    REAL,
            message    TEXT,
            sent_at    TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_fund_daily_date ON fund_daily(date);
        CREATE INDEX IF NOT EXISTS idx_fund_daily_code ON fund_daily(code);
    """)

    conn.commit()
    conn.close()
    logger.info("Veritabanı hazır: %s", DB_PATH)


def insert_fund_data(records: list[dict]):
    """Günlük fon verilerini veritabanına ekler (UPSERT)."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executemany("""
        INSERT INTO fund_daily
            (date, code, price, market_cap, num_investors, num_shares,
             net_flow, pct_change, investor_change)
        VALUES
            (:date, :code, :price, :market_cap, :num_investors, :num_shares,
             :net_flow, :pct_change, :investor_change)
        ON CONFLICT(date, code) DO UPDATE SET
            price            = excluded.price,
            market_cap       = excluded.market_cap,
            num_investors    = excluded.num_investors,
            num_shares       = excluded.num_shares,
            net_flow         = excluded.net_flow,
            pct_change       = excluded.pct_change,
            investor_change  = excluded.investor_change
    """, records)

    conn.commit()
    conn.close()
    logger.info("%d fon kaydı veritabanına yazıldı.", len(records))


def get_recent_data(code: str, days: int = 35):
    """Belirli bir fon için son N günün verisini getirir."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, net_flow, pct_change, investor_change, market_cap, num_investors
        FROM fund_daily
        WHERE code = ?
        ORDER BY date DESC
        LIMIT ?
    """, (code, days))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_all_codes_for_date(date: str):
    """Belirli bir tarihteki tüm fon kodlarını döner."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT code, price, market_cap, num_investors, net_flow, pct_change, investor_change
        FROM fund_daily
        WHERE date = ?
        ORDER BY net_flow DESC
    """, (date,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def log_alert(date: str, code: str, alert_type: str, value: float, z_score: float, message: str):
    """Alert kaydını veritabanına yazar."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO alerts_log (date, code, alert_type, value, z_score, message)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (date, code, alert_type, value, z_score, message))
    conn.commit()
    conn.close()


def get_dashboard_data(limit: int = 50):
    """Dashboard için son verileri döner."""
    conn = get_connection()
    cursor = conn.cursor()

    # Son tarih
    cursor.execute("SELECT MAX(date) FROM fund_daily")
    last_date = cursor.fetchone()[0]

    if not last_date:
        conn.close()
        return {}

    # Top 10 para girişi
    cursor.execute("""
        SELECT code, net_flow, pct_change, num_investors, market_cap
        FROM fund_daily
        WHERE date = ?
        ORDER BY net_flow DESC
        LIMIT 10
    """, (last_date,))
    top_inflows = cursor.fetchall()

    # Top 10 para çıkışı
    cursor.execute("""
        SELECT code, net_flow, pct_change, num_investors, market_cap
        FROM fund_daily
        WHERE date = ?
        ORDER BY net_flow ASC
        LIMIT 10
    """, (last_date,))
    top_outflows = cursor.fetchall()

    # Top 10 getiri
    cursor.execute("""
        SELECT code, pct_change, net_flow, num_investors, market_cap
        FROM fund_daily
        WHERE date = ?
        ORDER BY pct_change DESC
        LIMIT 10
    """, (last_date,))
    top_returns = cursor.fetchall()

    # Son alertler
    cursor.execute("""
        SELECT date, code, alert_type, value, z_score
        FROM alerts_log
        ORDER BY sent_at DESC
        LIMIT 20
    """)
    recent_alerts = cursor.fetchall()

    # Genel istatistik
    cursor.execute("""
        SELECT COUNT(*), SUM(CASE WHEN net_flow > 0 THEN net_flow ELSE 0 END),
               SUM(CASE WHEN net_flow < 0 THEN net_flow ELSE 0 END)
        FROM fund_daily
        WHERE date = ?
    """, (last_date,))
    stats = cursor.fetchone()

    conn.close()

    return {
        "last_date": last_date,
        "top_inflows": top_inflows,
        "top_outflows": top_outflows,
        "top_returns": top_returns,
        "recent_alerts": recent_alerts,
        "total_funds": stats[0],
        "total_inflow": stats[1] or 0,
        "total_outflow": stats[2] or 0,
    }
