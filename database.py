import sqlite3
import os
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn


def init_db():
    """Veritabanını ve tabloları oluşturur."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode = WAL")
    cursor.execute("PRAGMA synchronous = NORMAL")

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

        CREATE TABLE IF NOT EXISTS social_trends (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT NOT NULL,
            code       TEXT NOT NULL,
            pct        TEXT,
            stat       TEXT,
            reason     TEXT,
            score      REAL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(date, code)
        );

        CREATE TABLE IF NOT EXISTS social_momentum_daily (
            scan_date          TEXT NOT NULL,
            as_of_date         TEXT NOT NULL,
            code               TEXT NOT NULL,
            label              TEXT NOT NULL,
            rank               INTEGER,
            score              REAL NOT NULL,
            mention_count      INTEGER NOT NULL DEFAULT 0,
            unique_accounts    INTEGER NOT NULL DEFAULT 0,
            positive_count     INTEGER NOT NULL DEFAULT 0,
            negative_count     INTEGER NOT NULL DEFAULT 0,
            hype_count         INTEGER NOT NULL DEFAULT 0,
            acceleration_score REAL,
            diversity_score    REAL,
            sentiment_score    REAL,
            confirmation_score REAL,
            technical_score    REAL,
            flow_score         REAL,
            details_json       TEXT NOT NULL DEFAULT '{}',
            created_at         TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY(scan_date, code)
        );

        CREATE TABLE IF NOT EXISTS fund_names (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            management_fee REAL
        );

        CREATE TABLE IF NOT EXISTS fund_platform_metadata (
            code TEXT PRIMARY KEY,
            founder TEXT,
            tefas_status TEXT,
            tefas_risk_value INTEGER,
            source TEXT NOT NULL DEFAULT 'tefas_official_profile',
            checked_at TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS fund_breakdown (
            date       TEXT NOT NULL,
            code       TEXT NOT NULL,
            allocation_json TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY(date, code)
        );

        CREATE TABLE IF NOT EXISTS portfolio_transactions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT NOT NULL,
            code         TEXT NOT NULL,
            tx_type      TEXT NOT NULL,
            date         TEXT NOT NULL,
            units        REAL NOT NULL,
            unit_price   REAL NOT NULL,
            created_at   TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS price_alert_rules (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id   TEXT NOT NULL,
            code         TEXT NOT NULL,
            threshold    REAL NOT NULL,
            is_active    INTEGER DEFAULT 1,
            created_at   TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS signal_runs (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_date      TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            status           TEXT NOT NULL,
            universe_count   INTEGER NOT NULL DEFAULT 0,
            selected_count   INTEGER NOT NULL DEFAULT 0,
            config_json      TEXT NOT NULL,
            diagnostics_json TEXT,
            created_at       TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(signal_date, strategy_version)
        );

        CREATE TABLE IF NOT EXISTS fund_features_daily (
            signal_date       TEXT NOT NULL,
            code              TEXT NOT NULL,
            strategy_version  TEXT NOT NULL,
            category          TEXT NOT NULL,
            score             REAL NOT NULL,
            momentum_score    REAL,
            trend_score       REAL,
            risk_score        REAL,
            flow_score        REAL,
            regime_score      REAL,
            liquidity_score   REAL,
            return_1m         REAL,
            return_3m         REAL,
            return_6m         REAL,
            return_1y         REAL,
            volatility_annual REAL,
            drawdown_6m       REAL,
            flow_zscore       REAL,
            flow_5d_ratio     REAL,
            flow_20d_ratio    REAL,
            flow_persistence  REAL,
            investor_growth   REAL,
            ema50             REAL,
            ema200            REAL,
            market_cap        REAL,
            num_investors     INTEGER,
            alis_valor        INTEGER,
            satis_valor       INTEGER,
            data_quality      INTEGER NOT NULL DEFAULT 1,
            details_json      TEXT,
            created_at        TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY(signal_date, code, strategy_version)
        );

        CREATE TABLE IF NOT EXISTS fund_signals (
            signal_date       TEXT NOT NULL,
            code              TEXT NOT NULL,
            strategy_version  TEXT NOT NULL,
            status            TEXT NOT NULL,
            previous_status   TEXT,
            score             REAL NOT NULL,
            rank              INTEGER,
            target_weight     REAL NOT NULL DEFAULT 0,
            reasons_json      TEXT NOT NULL,
            entry_window      TEXT,
            invalidation_rule TEXT,
            created_at        TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY(signal_date, code, strategy_version)
        );

        CREATE TABLE IF NOT EXISTS rotation_recommendations (
            signal_date      TEXT NOT NULL,
            code             TEXT NOT NULL,
            strategy_version TEXT NOT NULL,
            action           TEXT NOT NULL,
            rank             INTEGER,
            score            REAL NOT NULL,
            target_weight    REAL NOT NULL DEFAULT 0,
            category         TEXT NOT NULL,
            reasons_json     TEXT NOT NULL,
            created_at       TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY(signal_date, code, strategy_version)
        );

        CREATE TABLE IF NOT EXISTS emerging_fund_radar (
            signal_date          TEXT NOT NULL,
            code                 TEXT NOT NULL,
            strategy_version     TEXT NOT NULL,
            tier                 TEXT NOT NULL,
            signal               TEXT NOT NULL,
            rank                 INTEGER NOT NULL,
            score                REAL NOT NULL,
            confidence           REAL NOT NULL,
            history_days         INTEGER NOT NULL,
            momentum_score       REAL,
            trend_score          REAL,
            flow_score           REAL,
            risk_liquidity_score REAL,
            reasons_json         TEXT NOT NULL DEFAULT '[]',
            created_at           TEXT DEFAULT (datetime('now','localtime')),
            PRIMARY KEY(signal_date, code, strategy_version)
        );

        CREATE TABLE IF NOT EXISTS strategy_backtests (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_version TEXT NOT NULL,
            start_date       TEXT NOT NULL,
            end_date         TEXT NOT NULL,
            config_json      TEXT NOT NULL,
            metrics_json     TEXT NOT NULL,
            equity_curve_json TEXT NOT NULL,
            created_at       TEXT DEFAULT (datetime('now','localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_fund_daily_date ON fund_daily(date);
        CREATE INDEX IF NOT EXISTS idx_fund_daily_code ON fund_daily(code);
        CREATE INDEX IF NOT EXISTS idx_fund_daily_code_date ON fund_daily(code, date);
        CREATE INDEX IF NOT EXISTS idx_fund_daily_date_net_flow ON fund_daily(date, net_flow);
        CREATE INDEX IF NOT EXISTS idx_fund_daily_date_pct_change ON fund_daily(date, pct_change);
        CREATE INDEX IF NOT EXISTS idx_portfolio_session_id ON portfolio_transactions(session_id);
        CREATE INDEX IF NOT EXISTS idx_price_alert_session ON price_alert_rules(session_id);
        CREATE INDEX IF NOT EXISTS idx_fund_features_date_score ON fund_features_daily(signal_date, score DESC);
        CREATE INDEX IF NOT EXISTS idx_fund_signals_date_status ON fund_signals(signal_date, status, score DESC);
        CREATE INDEX IF NOT EXISTS idx_rotation_date_action ON rotation_recommendations(signal_date, action);
        CREATE INDEX IF NOT EXISTS idx_emerging_radar_date_rank ON emerging_fund_radar(signal_date, rank);
        CREATE INDEX IF NOT EXISTS idx_social_momentum_date_rank ON social_momentum_daily(scan_date, rank);
    """)

    # Mevcut kurulumlar için management_fee sütunu
    try:
        cursor.execute("ALTER TABLE fund_names ADD COLUMN management_fee REAL")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE fund_platform_metadata ADD COLUMN tefas_risk_value INTEGER")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    for column in ("flow_5d_ratio", "flow_20d_ratio", "flow_persistence"):
        try:
            cursor.execute(f"ALTER TABLE fund_features_daily ADD COLUMN {column} REAL")
            conn.commit()
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()
    logger.info("Veritabanı hazır: %s", DB_PATH)


def save_fund_names(names_dict: dict):
    """Fon kodlarını ve isimlerini veritabanına ekler/günceller."""
    if not names_dict:
        return
    conn = get_connection()
    cursor = conn.cursor()
    records = list(names_dict.items())
    cursor.executemany("""
        INSERT INTO fund_names (code, name)
        VALUES (?, ?)
        ON CONFLICT(code) DO UPDATE SET name = excluded.name
    """, records)
    conn.commit()
    conn.close()
    logger.info("%d fon ismi güncellendi.", len(records))


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


def get_recent_data(code: str, days: int = 35, end_date: str | None = None):
    """Belirli bir fonun end_date dahil son N kaydını kronolojik döndürür."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, net_flow, pct_change, investor_change, market_cap, num_investors
        FROM (
            SELECT date, net_flow, pct_change, investor_change, market_cap, num_investors
            FROM fund_daily
            WHERE code = ? AND (? IS NULL OR date <= ?)
            ORDER BY date DESC
            LIMIT ?
        )
        ORDER BY date ASC
    """, (code, end_date, end_date, days))
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


def save_social_trends(date: str, trends: list[dict]):
    """Sosyal medya trendlerini veritabanına ekler (UPSERT)."""
    if not trends:
        return
    conn = get_connection()
    cursor = conn.cursor()

    records = [
        {
            "date": date,
            "code": t["code"],
            "pct": str(t.get("pct", "")),
            "stat": str(t.get("stat", "")),
            "reason": str(t.get("reason", "")),
            "score": float(t.get("score", 0.0))
        }
        for t in trends
    ]

    cursor.executemany("""
        INSERT INTO social_trends (date, code, pct, stat, reason, score)
        VALUES (:date, :code, :pct, :stat, :reason, :score)
        ON CONFLICT(date, code) DO UPDATE SET
            pct = excluded.pct,
            stat = excluded.stat,
            reason = excluded.reason,
            score = excluded.score
    """, records)

    conn.commit()
    conn.close()
    logger.info("%d sosyal trend kaydı veritabanına yazıldı.", len(records))


def save_social_momentum(scan_date: str, as_of_date: str, rows: list[dict]):
    """Açıklanabilir günlük sosyal-momentum bileşenlerini saklar."""
    if not rows:
        return
    import json

    records = []
    for row in rows:
        records.append({
            "scan_date": scan_date,
            "as_of_date": as_of_date,
            "code": str(row["code"]),
            "label": str(row.get("label") or "İZLE"),
            "rank": int(row.get("rank") or 0),
            "score": float(row.get("score") or 0),
            "mention_count": int(row.get("mention_count") or 0),
            "unique_accounts": int(row.get("unique_accounts") or 0),
            "positive_count": int(row.get("positive_count") or 0),
            "negative_count": int(row.get("negative_count") or 0),
            "hype_count": int(row.get("hype_count") or 0),
            "acceleration_score": float(row.get("acceleration_score") or 0),
            "diversity_score": float(row.get("diversity_score") or 0),
            "sentiment_score": float(row.get("sentiment_score") or 0),
            "confirmation_score": float(row.get("confirmation_score") or 0),
            "technical_score": float(row.get("technical_score") or 0),
            "flow_score": float(row.get("flow_score") or 0),
            "details_json": json.dumps({
                "reason": row.get("reason"),
                "examples": row.get("examples") or [],
                "category": row.get("category"),
            }, ensure_ascii=False),
        })

    conn = get_connection()
    conn.execute("DELETE FROM social_momentum_daily WHERE scan_date = ?", (scan_date,))
    conn.executemany(
        """
        INSERT INTO social_momentum_daily (
            scan_date, as_of_date, code, label, rank, score, mention_count,
            unique_accounts, positive_count, negative_count, hype_count,
            acceleration_score, diversity_score, sentiment_score,
            confirmation_score, technical_score, flow_score, details_json
        ) VALUES (
            :scan_date, :as_of_date, :code, :label, :rank, :score, :mention_count,
            :unique_accounts, :positive_count, :negative_count, :hype_count,
            :acceleration_score, :diversity_score, :sentiment_score,
            :confirmation_score, :technical_score, :flow_score, :details_json
        )
        ON CONFLICT(scan_date, code) DO UPDATE SET
            as_of_date=excluded.as_of_date, label=excluded.label, rank=excluded.rank,
            score=excluded.score, mention_count=excluded.mention_count,
            unique_accounts=excluded.unique_accounts, positive_count=excluded.positive_count,
            negative_count=excluded.negative_count, hype_count=excluded.hype_count,
            acceleration_score=excluded.acceleration_score,
            diversity_score=excluded.diversity_score,
            sentiment_score=excluded.sentiment_score,
            confirmation_score=excluded.confirmation_score,
            technical_score=excluded.technical_score, flow_score=excluded.flow_score,
            details_json=excluded.details_json, created_at=datetime('now','localtime')
        """,
        records,
    )
    conn.commit()
    conn.close()
    logger.info("%d sosyal momentum kaydı veritabanına yazıldı.", len(records))

def save_fund_breakdown(date: str, data_list: list):
    """
    Tefas'tan gelen varlık dağılımı (breakdown) yüzdelerini fund_breakdown tablosuna kaydeder.
    data_list formatı: [{'code': 'HCV', 'allocation_json': '{"stock_pct": 20.5}'}]
    """
    if not data_list:
        return
        
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.executemany("""
            INSERT INTO fund_breakdown (date, code, allocation_json)
            VALUES (?, ?, ?)
            ON CONFLICT(date, code) DO UPDATE SET
                allocation_json=excluded.allocation_json
        """, [(date, d["code"], d["allocation_json"]) for d in data_list])
        conn.commit()
    except Exception as e:
        logger.error("fund_breakdown kaydetme hatası: %s", e)
        conn.rollback()
    finally:
        conn.close()
