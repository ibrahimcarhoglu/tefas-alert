"""
TEFAS Platform — FastAPI Backend
SOA mimarili, async, cache'li API servisi.
"""
import json
import math
import time
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional
from functools import lru_cache

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── Config ─────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tefas.db")

app = FastAPI(
    title="TEFAS Platform API",
    version="2.0.0",
    description="SOA TEFAS fon analiz platformu backend'i",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── TTL Cache ──────────────────────────────────────────
_cache: dict[str, tuple[float, any]] = {}

def cached(key: str, ttl_seconds: int = 300):
    """Simple TTL decorator for dict-based caching."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            now = time.time()
            if key in _cache:
                ts, data = _cache[key]
                if now - ts < ttl_seconds:
                    return data
            result = fn(*args, **kwargs)
            _cache[key] = (now, result)
            return result
        return wrapper
    return decorator

def invalidate_cache(prefix: str = ""):
    """Clear cache entries matching prefix."""
    keys = [k for k in _cache if k.startswith(prefix)]
    for k in keys:
        del _cache[k]

# ── DB helper ──────────────────────────────────────────
_schema_ready = False

def get_conn():
    global _schema_ready
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    if not _schema_ready:
        try:
            conn.execute("ALTER TABLE fund_names ADD COLUMN management_fee REAL")
            conn.commit()
        except sqlite3.OperationalError:
            pass
        _schema_ready = True
    return conn

def get_tefas_status(code: str, name: str, investor_count: int = None) -> str:
    code_upper = code.upper()
    name_upper = (name or "").upper()
    always_open = {'BMU','KLH','TTA','TLY','ZPR','PPS','KSV','KLU','DZM','DPB','DIP','AES'}
    if code_upper in always_open:
        return "Açık"
    if "ÖZEL" in name_upper or "MÜNFERİT" in name_upper:
        return "Kapalı"
    if "SERBEST" not in name_upper:
        return "Açık"
    if investor_count is not None and investor_count > 100:
        return "Açık"
    return "Kapalı"

def classify_category(name: str) -> str:
    n = (name or "").upper()
    if "HİSSE" in n or "BİST" in n:
        return "Hisse Senedi"
    if "KATILIM" in n:
        return "Katılım"
    if "SERBEST" in n:
        return "Serbest"
    if "DEĞİŞKEN" in n:
        return "Değişken"
    if "PARA PİYASASI" in n:
        return "Para Piyasası"
    if "BORÇLANMA" in n or "TAHVİL" in n or "BONO" in n:
        return "Borçlanma Araçları"
    if "FON SEPETİ" in n:
        return "Fon Sepeti"
    if "ALTIN" in n or "KIYMETLİ" in n or "GÜMÜŞ" in n:
        return "Kıymetli Madenler"
    return "Diğer"

def classify_risk(name: str, code: str) -> str:
    n = (name or "").upper()
    if "PARA PİYASASI" in n or "KISA VADELİ" in n:
        return "low"
    if "HİSSE" in n or "BİST" in n or code.upper() in ("HCV","KLH","BMU"):
        return "high"
    return "mid"

def get_manager(code: str, name: str) -> str:
    overrides = {"HCV":"HEDEF","BMU":"BULLS","KLH":"ATLAS"}
    if code.upper() in overrides:
        return f"{overrides[code.upper()]} PORTFÖY YÖNETİMİ A.Ş."
    words = (name or "").upper().split()
    if len(words) > 1:
        return f"{words[0]} PORTFÖY YÖNETİMİ A.Ş."
    return "BİLİNMEYEN PORTFÖY YÖNETİMİ A.Ş."

RETURN_PERIOD_DAYS = {"1d": 1, "1w": 7, "1m": 30, "3m": 90, "1y": 365}

def get_management_fee(name: str, code: str, db_fee: Optional[float] = None) -> Optional[float]:
    """Yönetim ücreti: DB'de varsa kullan, yoksa kategori bazlı tahmin."""
    if db_fee is not None:
        return db_fee
    n = (name or "").upper()
    c = (code or "").upper()
    if "PARA PİYASASI" in n or "KISA VADELİ" in n or c == "TI1":
        return 0.75
    if "HİSSE" in n or "BİST" in n or c in ("MAC", "YAS", "KLH", "BMU"):
        return 2.25
    return 1.50

def compute_period_return(history: list[dict], days: int) -> Optional[float]:
    """history: tarih ASC sıralı günlük satırlar."""
    if not history:
        return None
    last = history[-1]
    if days <= 1:
        return last.get("pct_change")
    last_price = last.get("price")
    if not last_price or last_price <= 0:
        return None
    idx = max(0, len(history) - 1 - days)
    start_price = history[idx].get("price")
    if not start_price or start_price <= 0:
        return None
    return round((last_price - start_price) / start_price * 100, 2)

def compute_volatility(history: list[dict]) -> Optional[float]:
    """Günlük getirilerin standart sapması (%)."""
    returns = [h["pct_change"] for h in history if h.get("pct_change") is not None]
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return round(math.sqrt(variance), 2)

def load_history_map(conn, lookback_days: int = 400) -> dict[str, list[dict]]:
    c = conn.cursor()
    c.execute("SELECT MAX(date) FROM fund_daily")
    last_date = c.fetchone()[0]
    if not last_date:
        return {}
    c.execute("""
        SELECT code, date, price, pct_change
        FROM fund_daily
        WHERE date >= date(?, ?)
        ORDER BY code, date ASC
    """, (last_date, f"-{lookback_days} days"))
    hist_map: dict[str, list[dict]] = {}
    for r in c.fetchall():
        hist_map.setdefault(r["code"], []).append(dict(r))
    return hist_map

# ── Health ─────────────────────────────────────────────
@app.get("/health")
def health():
    try:
        conn = get_conn()
        conn.execute("SELECT 1")
        conn.close()
        return {"status": "ok", "db": DB_PATH}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})

# ── Dashboard ──────────────────────────────────────────
@app.get("/api/dashboard")
def dashboard():
    return _get_dashboard()

@cached("dashboard", ttl_seconds=300)
def _get_dashboard():
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT MAX(date) FROM fund_daily")
    last_date = c.fetchone()[0]
    if not last_date:
        conn.close()
        return {}

    def fetch_top(order_col, order_dir="DESC", limit=15):
        c.execute(f"""
            SELECT fd.code, fd.price, fd.pct_change, fd.net_flow,
                   fd.num_investors, fd.market_cap, fn.name
            FROM fund_daily fd
            LEFT JOIN fund_names fn ON fd.code = fn.code
            WHERE fd.date = ? AND fd.{order_col} IS NOT NULL
            ORDER BY fd.{order_col} {order_dir}
            LIMIT ?
        """, (last_date, limit))
        return [
            {
                "code": r["code"], "price": r["price"],
                "pct_change": r["pct_change"], "net_flow": r["net_flow"],
                "num_investors": r["num_investors"], "market_cap": r["market_cap"],
                "name": r["name"] or "Bilinmeyen Fon",
                "tefas_status": get_tefas_status(r["code"], r["name"], r["num_investors"]),
            }
            for r in c.fetchall()
        ]

    top_inflows = fetch_top("net_flow", "DESC")
    top_outflows = fetch_top("net_flow", "ASC")
    top_returns = fetch_top("pct_change", "DESC")
    top_losers = fetch_top("pct_change", "ASC")

    # Stats
    c.execute("""
        SELECT COUNT(*),
               SUM(CASE WHEN net_flow > 0 THEN net_flow ELSE 0 END),
               SUM(CASE WHEN net_flow < 0 THEN net_flow ELSE 0 END)
        FROM fund_daily WHERE date = ?
    """, (last_date,))
    stats = c.fetchone()

    # Alerts
    c.execute("""
        SELECT date, code, alert_type, value, z_score, message
        FROM alerts_log ORDER BY sent_at DESC LIMIT 30
    """)
    alerts = [dict(r) for r in c.fetchall()]

    # Social
    c.execute("SELECT MAX(date) FROM social_trends")
    sd = c.fetchone()[0]
    social = []
    if sd:
        c.execute("""
            SELECT st.code, st.pct, st.stat, st.reason, st.score, fn.name, fd.num_investors
            FROM social_trends st
            LEFT JOIN fund_names fn ON st.code = fn.code
            LEFT JOIN fund_daily fd ON st.code = fd.code AND fd.date = st.date
            WHERE st.date = ? ORDER BY st.score DESC
        """, (sd,))
        social = [
            {
                "code": r["code"], "pct": r["pct"], "stat": r["stat"],
                "reason": r["reason"], "score": r["score"],
                "name": r["name"] or "Bilinmeyen Fon",
                "tefas_status": get_tefas_status(r["code"], r["name"], r["num_investors"]),
            }
            for r in c.fetchall()
        ]

    # Periodic
    def periodic_top(days, limit=15):
        target = (datetime.strptime(last_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")
        c.execute("SELECT MAX(date) FROM fund_daily WHERE date <= ?", (target,))
        prev = c.fetchone()[0]
        if not prev:
            return []
        c.execute("""
            SELECT fd1.code, fd1.price, fd2.price as prev_price,
                   ((fd1.price - fd2.price) / fd2.price * 100) as pct_change,
                   fn.name, fd1.num_investors, fd1.net_flow, fd1.market_cap
            FROM fund_daily fd1
            JOIN fund_daily fd2 ON fd1.code = fd2.code AND fd2.date = ?
            LEFT JOIN fund_names fn ON fd1.code = fn.code
            WHERE fd1.date = ?
            ORDER BY pct_change DESC LIMIT ?
        """, (prev, last_date, limit))
        return [
            {
                "code": r["code"], "price": r["price"], "prev_price": r["prev_price"],
                "pct_change": r["pct_change"], "name": r["name"] or "Bilinmeyen Fon",
                "num_investors": r["num_investors"], "net_flow": r["net_flow"],
                "market_cap": r["market_cap"],
                "tefas_status": get_tefas_status(r["code"], r["name"], r["num_investors"]),
            }
            for r in c.fetchall()
        ]

    periodic = {
        "3gun": periodic_top(3),
        "1hafta": periodic_top(7),
        "2hafta": periodic_top(14),
        "1ay": periodic_top(30),
    }

    conn.close()
    return {
        "last_date": last_date,
        "total_funds": stats[0] or 0,
        "total_inflow": stats[1] or 0,
        "total_outflow": stats[2] or 0,
        "top_inflows": top_inflows,
        "top_outflows": top_outflows,
        "top_returns": top_returns,
        "top_losers": top_losers,
        "recent_alerts": alerts,
        "social_trends": social,
        "periodic": periodic,
    }

# ── Fund List (YENİ) ──────────────────────────────────
@app.get("/api/funds")
def fund_list(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    manager: Optional[str] = Query(None),
    risk: Optional[str] = Query(None),
    codes: Optional[str] = Query(None),
    return_period: str = Query("1d"),
    max_fee: Optional[float] = Query(None),
    sort_by: str = Query("net_flow"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    return _get_fund_list(
        search, category, manager, risk, codes, return_period, max_fee,
        sort_by, order, page, page_size,
    )

def _get_fund_list(search, category, manager, risk, codes, return_period, max_fee, sort_by, order, page, page_size):
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT MAX(date) FROM fund_daily")
    last_date = c.fetchone()[0]
    if not last_date:
        conn.close()
        return {"funds": [], "total": 0, "page": 1, "page_size": page_size}

    period_key = return_period if return_period in RETURN_PERIOD_DAYS else "1d"
    period_days = RETURN_PERIOD_DAYS[period_key]

    c.execute("""
        SELECT fd.code, fd.price, fd.pct_change, fd.net_flow,
               fd.num_investors, fd.market_cap, fd.investor_change, fn.name,
               fn.management_fee
        FROM fund_daily fd
        LEFT JOIN fund_names fn ON fd.code = fn.code
        WHERE fd.date = ?
    """, (last_date,))
    rows = c.fetchall()

    hist_map = load_history_map(conn) if period_key != "1d" else {}

    funds = []
    for r in rows:
        name = r["name"] or "Bilinmeyen Fon"
        code = r["code"]
        cat = classify_category(name)
        mgr = get_manager(code, name)
        fund_risk = classify_risk(name, code)
        status = get_tefas_status(code, name, r["num_investors"])

        # Filtreler
        if codes:
            allowed_codes = [x.strip().upper() for x in codes.split(",") if x.strip()]
            if code.upper() not in allowed_codes:
                continue
        if search:
            q = search.upper()
            if q not in code.upper() and q not in name.upper():
                continue
        if category and category.lower() != cat.lower():
            continue
        if manager and manager.upper() not in mgr.upper():
            continue
        if risk and risk.lower() != fund_risk.lower():
            continue

        mgmt_fee = get_management_fee(name, code, r["management_fee"] if "management_fee" in r.keys() else None)
        if max_fee is not None and mgmt_fee is not None and mgmt_fee > max_fee:
            continue

        if period_key == "1d":
            period_return = r["pct_change"]
        else:
            hist = hist_map.get(code, [])
            period_return = compute_period_return(hist, period_days)

        funds.append({
            "code": code,
            "name": name,
            "price": r["price"],
            "pct_change": r["pct_change"],
            "period_return": period_return,
            "return_period": period_key,
            "management_fee": mgmt_fee,
            "net_flow": r["net_flow"],
            "num_investors": r["num_investors"],
            "market_cap": r["market_cap"],
            "investor_change": r["investor_change"],
            "category": cat,
            "manager": mgr,
            "risk": fund_risk,
            "tefas_status": status,
        })

    # Sıralama
    allowed_sorts = {"net_flow","pct_change","period_return","market_cap","num_investors","price","code","name","management_fee"}
    if sort_by not in allowed_sorts:
        sort_by = "net_flow"
    reverse = order.lower() == "desc"
    def sort_key(x):
        v = x.get(sort_by)
        if v is None:
            return (0, 0) if reverse else (1, "")
        if isinstance(v, (int, float)):
            return (0, v)
        return (1, str(v))
    funds.sort(key=sort_key, reverse=reverse)

    total = len(funds)
    start = (page - 1) * page_size
    end = start + page_size

    conn.close()
    return {
        "funds": funds[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "last_date": last_date,
    }

# ── Fund Detail ────────────────────────────────────────
@app.get("/api/fund/{code}")
def fund_detail(code: str):
    return _get_fund_detail(code.upper())

def _get_fund_detail(code: str):
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT name FROM fund_names WHERE code = ?", (code,))
    row = c.fetchone()
    name = row["name"] if row else "Bilinmeyen Fon"

    # Last 365 days for heatmap + drawdown
    c.execute("""
        SELECT date, price, num_investors, net_flow, pct_change, market_cap
        FROM fund_daily WHERE code = ? ORDER BY date ASC LIMIT 365
    """, (code,))
    all_rows = [dict(r) for r in c.fetchall()]

    # Compute max drawdown & monthly returns
    max_dd = 0.0
    peak = 0.0
    monthly_prices: dict[str, dict] = {}

    for i, h in enumerate(all_rows):
        p = h["price"]
        if p and p > 0:
            if p > peak:
                peak = p
            dd = (peak - p) / peak * 100
            if dd > max_dd:
                max_dd = dd
            mk = h["date"][:7]
            if mk not in monthly_prices:
                monthly_prices[mk] = {"start": p, "end": p}
            monthly_prices[mk]["end"] = p

    monthly_returns = {}
    for mk, v in monthly_prices.items():
        if v["start"] > 0:
            monthly_returns[mk] = round((v["end"] - v["start"]) / v["start"] * 100, 2)

    history_30 = all_rows[-30:] if len(all_rows) > 30 else all_rows
    last = all_rows[-1] if all_rows else {}

    performance = {
        "return_1m": compute_period_return(all_rows, 30),
        "return_3m": compute_period_return(all_rows, 90),
        "return_6m": compute_period_return(all_rows, 180),
        "return_1y": compute_period_return(all_rows, 365),
        "max_drawdown": round(max_dd, 2),
        "volatility": compute_volatility(all_rows[-90:] if len(all_rows) > 90 else all_rows),
    }

    c.execute("SELECT management_fee FROM fund_names WHERE code = ?", (code,))
    fee_row = c.fetchone()
    db_fee = fee_row["management_fee"] if fee_row and "management_fee" in fee_row.keys() else None
    management_fee = get_management_fee(name, code, db_fee)

    # Allocation
    c.execute("""
        SELECT allocation_json FROM fund_breakdown
        WHERE code = ? ORDER BY date DESC LIMIT 1
    """, (code,))
    alloc_row = c.fetchone()
    allocation = {}
    if alloc_row and alloc_row["allocation_json"]:
        try:
            allocation = json.loads(alloc_row["allocation_json"])
        except Exception:
            pass

    conn.close()

    status = get_tefas_status(code, name, last.get("num_investors"))
    cat = classify_category(name)
    mgr = get_manager(code, name)
    risk = classify_risk(name, code)

    return {
        "code": code,
        "name": name,
        "tefas_status": status,
        "category": cat,
        "manager": mgr,
        "risk": risk,
        "max_drawdown": round(max_dd, 2),
        "management_fee": management_fee,
        "performance": performance,
        "monthly_returns": monthly_returns,
        "allocation": allocation,
        "history": history_30,
    }

@app.get("/api/fund/{code}/similar")
def similar_funds(code: str, limit: int = Query(5, ge=1, le=10)):
    code = code.upper()
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT name FROM fund_names WHERE code = ?", (code,))
    row = c.fetchone()
    if not row:
        conn.close()
        return {"funds": [], "source_code": code}

    name = row["name"] or ""
    target_cat = classify_category(name)
    target_risk = classify_risk(name, code)

    c.execute("SELECT MAX(date) FROM fund_daily")
    last_date = c.fetchone()[0]
    if not last_date:
        conn.close()
        return {"funds": [], "source_code": code}

    hist_map = load_history_map(conn)
    c.execute("""
        SELECT fd.code, fd.price, fd.pct_change, fn.name
        FROM fund_daily fd
        LEFT JOIN fund_names fn ON fd.code = fn.code
        WHERE fd.date = ? AND fd.code != ?
    """, (last_date, code))
    candidates = []
    for r in c.fetchall():
        fname = r["name"] or ""
        fcode = r["code"]
        cat = classify_category(fname)
        frisk = classify_risk(fname, fcode)
        if cat != target_cat or frisk != target_risk:
            continue
        ret_1m = compute_period_return(hist_map.get(fcode, []), 30)
        candidates.append({
            "code": fcode,
            "name": fname,
            "category": cat,
            "risk": frisk,
            "price": r["price"],
            "pct_change": r["pct_change"],
            "return_1m": ret_1m,
        })

    candidates.sort(key=lambda x: (x["return_1m"] is None, -(x["return_1m"] or -9999)))
    conn.close()
    return {"source_code": code, "funds": candidates[:limit]}

# ── Fund History (flexible days) ──────────────────────
@app.get("/api/fund/{code}/history")
def fund_history(code: str, days: int = Query(30, ge=7, le=1825)):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT date, price, num_investors, net_flow, pct_change, market_cap
        FROM fund_daily WHERE code = ? ORDER BY date DESC LIMIT ?
    """, (code.upper(), days))
    rows = [dict(r) for r in c.fetchall()]
    rows.reverse()
    conn.close()
    return {"code": code.upper(), "days": days, "history": rows}

# ── Managers ───────────────────────────────────────────
@app.get("/api/managers")
def managers():
    return _get_managers()

@cached("managers", ttl_seconds=600)
def _get_managers():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT MAX(date) FROM fund_daily")
    last_date = c.fetchone()[0]
    if not last_date:
        conn.close()
        return []

    c.execute("""
        SELECT fd.code, fd.market_cap, fd.num_investors, fd.net_flow, fd.pct_change, fn.name
        FROM fund_daily fd
        LEFT JOIN fund_names fn ON fd.code = fn.code
        WHERE fd.date = ?
    """, (last_date,))

    mgr_dict: dict = {}
    total_mcap = 0.0

    for r in c.fetchall():
        code = r["code"]
        name = r["name"] or ""
        mcap = r["market_cap"] or 0.0
        mgr_name = get_manager(code, name)
        risk = classify_risk(name, code)
        total_mcap += mcap

        if mgr_name not in mgr_dict:
            mgr_dict[mgr_name] = {
                "manager": mgr_name, "fund_count": 0, "total_investors": 0,
                "total_net_flow": 0.0, "total_aum": 0.0,
                "w_ret_sum": 0.0, "w_ret_mcap": 0.0,
                "low": 0, "mid": 0, "high": 0,
            }
        m = mgr_dict[mgr_name]
        m["fund_count"] += 1
        m["total_investors"] += r["num_investors"] or 0
        m["total_net_flow"] += r["net_flow"] or 0.0
        m["total_aum"] += mcap
        if mcap > 0:
            m["w_ret_sum"] += (r["pct_change"] or 0) * mcap
            m["w_ret_mcap"] += mcap
        m[risk] += 1

    result = []
    for v in mgr_dict.values():
        avg = v["w_ret_sum"] / v["w_ret_mcap"] if v["w_ret_mcap"] > 0 else 0
        result.append({
            "manager": v["manager"],
            "fund_count": v["fund_count"],
            "total_investors": v["total_investors"],
            "total_net_flow": round(v["total_net_flow"], 2),
            "total_aum": round(v["total_aum"], 2),
            "market_share": round(v["total_aum"] / total_mcap * 100, 2) if total_mcap > 0 else 0,
            "average_return": round(avg, 2),
            "low_risk_count": v["low"],
            "mid_risk_count": v["mid"],
            "high_risk_count": v["high"],
        })

    result.sort(key=lambda x: x["total_aum"], reverse=True)
    conn.close()
    return result

# ── Categories ─────────────────────────────────────────
@app.get("/api/categories")
def categories():
    return _get_categories()

@cached("categories", ttl_seconds=600)
def _get_categories():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT MAX(date) FROM fund_daily")
    last_date = c.fetchone()[0]
    if not last_date:
        conn.close()
        return []

    c.execute("""
        SELECT fd.code, fd.market_cap, fd.net_flow, fd.pct_change, fn.name
        FROM fund_daily fd LEFT JOIN fund_names fn ON fd.code = fn.code
        WHERE fd.date = ?
    """, (last_date,))

    cat_dict: dict = {}
    for r in c.fetchall():
        cat = classify_category(r["name"] or "")
        mcap = r["market_cap"] or 0.0
        if cat not in cat_dict:
            cat_dict[cat] = {"category": cat, "fund_count": 0, "net_flow": 0.0, "aum": 0.0, "w_sum": 0.0, "w_mcap": 0.0}
        d = cat_dict[cat]
        d["fund_count"] += 1
        d["net_flow"] += r["net_flow"] or 0.0
        d["aum"] += mcap
        if mcap > 0:
            d["w_sum"] += (r["pct_change"] or 0) * mcap
            d["w_mcap"] += mcap

    result = []
    for v in cat_dict.values():
        avg = v["w_sum"] / v["w_mcap"] if v["w_mcap"] > 0 else 0
        result.append({
            "category": v["category"],
            "fund_count": v["fund_count"],
            "total_net_flow": round(v["net_flow"], 2),
            "total_aum": round(v["aum"], 2),
            "average_return": round(avg, 2),
        })
    result.sort(key=lambda x: x["total_aum"], reverse=True)
    conn.close()
    return result

# ── Cash Flow History (YENİ) ──────────────────────────
@app.get("/api/cashflow")
def cashflow(days: int = Query(30, ge=7, le=90)):
    return _get_cashflow(days)

def _get_cashflow(days: int):
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT MAX(date) FROM fund_daily")
    last_date = c.fetchone()[0]
    if not last_date:
        conn.close()
        return {"daily": [], "by_category": []}

    target = (datetime.strptime(last_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d")

    # Daily totals
    c.execute("""
        SELECT date,
               SUM(CASE WHEN net_flow > 0 THEN net_flow ELSE 0 END) as inflow,
               SUM(CASE WHEN net_flow < 0 THEN net_flow ELSE 0 END) as outflow,
               SUM(net_flow) as net
        FROM fund_daily
        WHERE date >= ?
        GROUP BY date ORDER BY date
    """, (target,))
    daily = [dict(r) for r in c.fetchall()]

    # Category breakdown for latest date
    c.execute("""
        SELECT fd.net_flow, fn.name
        FROM fund_daily fd LEFT JOIN fund_names fn ON fd.code = fn.code
        WHERE fd.date = ?
    """, (last_date,))
    cat_flows: dict = {}
    for r in c.fetchall():
        cat = classify_category(r["name"] or "")
        cat_flows.setdefault(cat, 0.0)
        cat_flows[cat] += r["net_flow"] or 0.0

    by_category = [{"category": k, "net_flow": round(v, 2)} for k, v in cat_flows.items()]
    by_category.sort(key=lambda x: abs(x["net_flow"]), reverse=True)

    conn.close()
    return {"daily": daily, "by_category": by_category, "last_date": last_date}

# ── Anomalies (YENİ) ──────────────────────────────────
@app.get("/api/anomalies")
def anomalies(
    limit: int = Query(50, ge=10, le=200),
    alert_type: Optional[str] = Query(None),
    min_zscore: Optional[float] = Query(None),
):
    conn = get_conn()
    c = conn.cursor()

    query = "SELECT date, code, alert_type, value, z_score, message FROM alerts_log WHERE 1=1"
    params: list = []

    if alert_type:
        query += " AND alert_type = ?"
        params.append(alert_type)
    if min_zscore is not None:
        query += " AND ABS(z_score) >= ?"
        params.append(min_zscore)

    query += " ORDER BY sent_at DESC LIMIT ?"
    params.append(limit)

    c.execute(query, params)
    rows = [dict(r) for r in c.fetchall()]

    # Stats
    c.execute("SELECT COUNT(*), AVG(ABS(z_score)), MAX(ABS(z_score)) FROM alerts_log")
    st = c.fetchone()

    conn.close()
    return {
        "alerts": rows,
        "stats": {
            "total": st[0] or 0,
            "avg_zscore": round(st[1] or 0, 2),
            "max_zscore": round(st[2] or 0, 2),
        },
    }

# ── Social Trends (YENİ endpoint) ─────────────────────
@app.get("/api/social")
def social(codes: Optional[str] = Query(None)):
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT MAX(date) FROM social_trends")
    sd = c.fetchone()[0]
    if not sd:
        conn.close()
        return {"trends": [], "date": None}

    allowed_codes = None
    if codes:
        allowed_codes = {x.strip().upper() for x in codes.split(",") if x.strip()}

    c.execute("""
        SELECT st.code, st.pct, st.stat, st.reason, st.score,
               fn.name, fd.num_investors, fd.pct_change, fd.net_flow
        FROM social_trends st
        LEFT JOIN fund_names fn ON st.code = fn.code
        LEFT JOIN fund_daily fd ON st.code = fd.code AND fd.date = st.date
        WHERE st.date = ? ORDER BY st.score DESC
    """, (sd,))
    trends = []
    for r in c.fetchall():
        if allowed_codes and r["code"].upper() not in allowed_codes:
            continue
        trends.append({
            "code": r["code"], "pct": r["pct"], "stat": r["stat"],
            "reason": r["reason"], "score": r["score"],
            "name": r["name"] or "Bilinmeyen Fon",
            "fund_pct_change": r["pct_change"],
            "fund_net_flow": r["net_flow"],
            "tefas_status": get_tefas_status(r["code"], r["name"], r["num_investors"]),
        })
    conn.close()
    return {"trends": trends, "date": sd}

# ── Portföy Takip APIs (YENİ) ──────────────────────────
from pydantic import BaseModel

class TransactionRequest(BaseModel):
    session_id: str
    code: str
    tx_type: str  # "BUY" veya "SELL"
    date: str     # "YYYY-MM-DD"
    units: float
    unit_price: float

@app.post("/api/portfolio/transaction")
def add_transaction(req: TransactionRequest):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO portfolio_transactions (session_id, code, tx_type, date, units, unit_price)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (req.session_id, req.code.upper(), req.tx_type.upper(), req.date, req.units, req.unit_price))
    conn.commit()
    tx_id = c.lastrowid
    conn.close()
    return {"status": "success", "id": tx_id}

class TransactionInput(BaseModel):
    code: str
    tx_type: str = "BUY"
    date: str
    units: float
    unit_price: float

class BulkTransactionRequest(BaseModel):
    session_id: str
    transactions: list[TransactionInput]

@app.post("/api/portfolio/transactions/bulk")
def add_transactions_bulk(req: BulkTransactionRequest):
    conn = get_conn()
    c = conn.cursor()
    ids = []
    for tx in req.transactions:
        c.execute("""
            INSERT INTO portfolio_transactions (session_id, code, tx_type, date, units, unit_price)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            req.session_id,
            tx.code.upper(),
            (tx.tx_type or "BUY").upper(),
            tx.date,
            tx.units,
            tx.unit_price,
        ))
        ids.append(c.lastrowid)
    conn.commit()
    conn.close()
    return {"status": "success", "ids": ids, "count": len(ids)}

@app.delete("/api/portfolio/transaction/{tx_id}")
def delete_transaction(tx_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM portfolio_transactions WHERE id = ?", (tx_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/portfolio/transactions")
def get_transactions(session_id: str = Query(...)):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT pt.id, pt.code, pt.tx_type, pt.date, pt.units, pt.unit_price, fn.name
        FROM portfolio_transactions pt
        LEFT JOIN fund_names fn ON pt.code = fn.code
        WHERE pt.session_id = ?
        ORDER BY pt.date DESC, pt.id DESC
    """, (session_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"transactions": rows}

@app.get("/api/portfolio/summary")
def get_portfolio_summary(session_id: str = Query(...)):
    conn = get_conn()
    c = conn.cursor()

    # Son tarih
    c.execute("SELECT MAX(date) FROM fund_daily")
    last_date = c.fetchone()[0]

    # Tüm işlemleri kronolojik çek
    c.execute("""
        SELECT code, tx_type, date, units, unit_price
        FROM portfolio_transactions
        WHERE session_id = ?
        ORDER BY date ASC, id ASC
    """, (session_id,))
    transactions = c.fetchall()

    if not transactions or not last_date:
        conn.close()
        return {
            "summary": {
                "total_value": 0.0,
                "total_cost": 0.0,
                "total_profit": 0.0,
                "total_profit_pct": 0.0,
                "daily_profit": 0.0,
            },
            "holdings": []
        }

    # Ortalama Maliyet Hesabı (FIFO/Weighted Average)
    holdings_calc = {}
    for tx in transactions:
        code = tx["code"].upper()
        txtype = tx["tx_type"].upper()
        units = tx["units"]
        price = tx["unit_price"]

        if code not in holdings_calc:
            holdings_calc[code] = {"units": 0.0, "total_cost": 0.0, "avg_cost": 0.0}

        curr = holdings_calc[code]
        if txtype == "BUY":
            new_units = curr["units"] + units
            new_cost = curr["total_cost"] + (units * price)
            curr["units"] = new_units
            curr["total_cost"] = new_cost
            curr["avg_cost"] = new_cost / new_units if new_units > 0 else 0.0
        elif txtype == "SELL":
            new_units = max(0.0, curr["units"] - units)
            curr["units"] = new_units
            curr["total_cost"] = new_units * curr["avg_cost"]  # Maliyet orantısal düşer

    # Güncel fiyatları tek seferde çek
    c.execute("""
        SELECT fd.code, fd.price, fd.pct_change, fn.name
        FROM fund_daily fd
        LEFT JOIN fund_names fn ON fd.code = fn.code
        WHERE fd.date = ?
    """, (last_date,))
    price_rows = {r["code"].upper(): r for r in c.fetchall()}

    holdings_list = []
    total_value = 0.0
    total_cost = 0.0
    daily_profit = 0.0

    for code, calc in holdings_calc.items():
        if calc["units"] <= 0:
            continue

        price_info = price_rows.get(code)
        curr_price = price_info["price"] if price_info else calc["avg_cost"]
        pct_change = price_info["pct_change"] if price_info else 0.0
        name = price_info["name"] if price_info else "Bilinmeyen Fon"

        curr_value = calc["units"] * curr_price
        curr_cost = calc["units"] * calc["avg_cost"]
        profit = curr_value - curr_cost
        profit_pct = (profit / curr_cost * 100) if curr_cost > 0 else 0.0

        # Günlük Kar/Zarar: adet * dünkü fiyata göre değişim miktarı
        # dünkü fiyat = curr_price / (1 + pct_change / 100)
        prev_price = curr_price / (1 + (pct_change or 0.0) / 100)
        daily_pnl = calc["units"] * (curr_price - prev_price)

        total_value += curr_value
        total_cost += curr_cost
        daily_profit += daily_pnl

        holdings_list.append({
            "code": code,
            "name": name,
            "units": calc["units"],
            "avg_cost": calc["avg_cost"],
            "current_price": curr_price,
            "current_value": curr_value,
            "total_cost": curr_cost,
            "profit": profit,
            "profit_pct": profit_pct,
            "pct_change": pct_change,
            "daily_profit": daily_pnl,
            "category": classify_category(name),
        })

    conn.close()

    total_profit = total_value - total_cost
    total_profit_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0.0

    return {
        "summary": {
            "total_value": total_value,
            "total_cost": total_cost,
            "total_profit": total_profit,
            "total_profit_pct": total_profit_pct,
            "daily_profit": daily_profit,
        },
        "holdings": holdings_list
    }

@app.get("/api/portfolio/allocation")
def get_portfolio_allocation(session_id: str = Query(...)):
    summary = get_portfolio_summary(session_id)
    holdings = summary.get("holdings", [])
    total_val = summary["summary"]["total_value"]

    allocation = []
    for h in holdings:
        val = h["current_value"]
        pct = (val / total_val * 100) if total_val > 0 else 0.0
        risk = classify_risk(h["name"], h["code"])
        allocation.append({
            "category": h["code"],
            "code": h["code"],
            "name": h["name"],
            "value": val,
            "percentage": pct,
            "risk": risk,
        })

    allocation.sort(key=lambda x: x["value"], reverse=True)
    return {"allocation": allocation}

# ── Eşik Alarmları ve Getiri Simülatörü APIs (Faz 3) ───

class AlertRequest(BaseModel):
    session_id: str
    code: str
    threshold: float

@app.post("/api/portfolio/alerts")
def add_alert_rule(req: AlertRequest):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO price_alert_rules (session_id, code, threshold, is_active)
        VALUES (?, ?, ?, 1)
    """, (req.session_id, req.code.upper(), req.threshold))
    conn.commit()
    rule_id = c.lastrowid
    conn.close()
    return {"status": "success", "id": rule_id}

@app.get("/api/portfolio/alerts")
def get_alert_rules(session_id: str = Query(...)):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT pr.id, pr.code, pr.threshold, pr.is_active, fn.name
        FROM price_alert_rules pr
        LEFT JOIN fund_names fn ON pr.code = fn.code
        WHERE pr.session_id = ?
        ORDER BY pr.id DESC
    """, (session_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return {"alerts": rows}

@app.delete("/api/portfolio/alerts/{alert_id}")
def delete_alert_rule(alert_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("DELETE FROM price_alert_rules WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/api/portfolio/notifications")
def get_notifications(session_id: str = Query(...)):
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT MAX(date) FROM fund_daily")
    last_date = c.fetchone()[0]

    if not last_date:
        conn.close()
        return {"notifications": []}

    c.execute("""
        SELECT pr.id, pr.code, pr.threshold, fn.name
        FROM price_alert_rules pr
        LEFT JOIN fund_names fn ON pr.code = fn.code
        WHERE pr.session_id = ? AND pr.is_active = 1
    """, (session_id,))
    rules = c.fetchall()

    notifications = []
    for rule in rules:
        code = rule["code"].upper()
        threshold = rule["threshold"]
        name = rule["name"] or "Bilinmeyen Fon"

        c.execute("""
            SELECT price, pct_change
            FROM fund_daily
            WHERE code = ? AND date = ?
        """, (code, last_date))
        price_info = c.fetchone()

        if price_info:
            pct_change = price_info["pct_change"] or 0.0
            is_triggered = False
            if threshold > 0 and pct_change >= threshold:
                is_triggered = True
            elif threshold < 0 and pct_change <= threshold:
                is_triggered = True

            if is_triggered:
                notifications.append({
                    "rule_id": rule["id"],
                    "code": code,
                    "name": name,
                    "threshold": threshold,
                    "pct_change": pct_change,
                    "current_price": price_info["price"],
                    "date": last_date,
                })

    conn.close()
    return {"notifications": notifications}

@app.get("/api/portfolio/performance")
def get_portfolio_performance(session_id: str = Query(...)):
    conn = get_conn()
    c = conn.cursor()

    # 1. Fetch all transactions for this session_id chronologically
    c.execute("""
        SELECT code, tx_type, date, units, unit_price
        FROM portfolio_transactions
        WHERE session_id = ?
        ORDER BY date ASC, id ASC
    """, (session_id,))
    transactions = [dict(r) for r in c.fetchall()]

    if not transactions:
        conn.close()
        return {"performance": []}

    # 2. Get last 30 unique dates available in fund_daily, in chronological order
    c.execute("SELECT DISTINCT date FROM fund_daily ORDER BY date DESC LIMIT 30")
    dates = [r[0] for r in c.fetchall()]
    dates.reverse() # oldest to newest

    if not dates:
        conn.close()
        return {"performance": []}

    # 3. Get unique fund codes in the portfolio
    codes = list(set(t["code"].upper() for t in transactions))

    # 4. Fetch all historical prices for these funds in the date range
    start_date = dates[0]
    placeholders = ",".join("?" for _ in codes)
    c.execute(f"""
        SELECT code, date, price
        FROM fund_daily
        WHERE code IN ({placeholders}) AND date >= ?
        ORDER BY date ASC
    """, codes + [start_date])
    price_rows = c.fetchall()

    # Organize prices: price_map[date][code] = price
    price_map = {}
    for r in price_rows:
        d = r["date"]
        code = r["code"].upper()
        p = r["price"]
        price_map.setdefault(d, {})[code] = p

    # To handle missing prices (like weekends/holidays) we keep track of the last known price for each fund
    last_known_prices = {}

    # Pre-fill with average cost or initial prices before the 30-day window
    for tx in transactions:
        code = tx["code"].upper()
        if code not in last_known_prices:
            last_known_prices[code] = tx["unit_price"]

    performance_timeline = []

    for d in dates:
        # Calculate holdings up to date `d`
        holdings = {}
        for tx in transactions:
            if tx["date"] > d:
                continue
            code = tx["code"].upper()
            txtype = tx["tx_type"].upper()
            units = tx["units"]
            price = tx["unit_price"]

            if code not in holdings:
                holdings[code] = {"units": 0.0, "total_cost": 0.0, "avg_cost": 0.0}

            curr = holdings[code]
            if txtype == "BUY":
                new_units = curr["units"] + units
                new_cost = curr["total_cost"] + (units * price)
                curr["units"] = new_units
                curr["total_cost"] = new_cost
                curr["avg_cost"] = new_cost / new_units if new_units > 0 else 0.0
            elif txtype == "SELL":
                new_units = max(0.0, curr["units"] - units)
                curr["units"] = new_units
                curr["total_cost"] = new_units * curr["avg_cost"]

        # Calculate portfolio value on date `d`
        daily_value = 0.0
        daily_cost = 0.0

        for code, h in holdings.items():
            if h["units"] <= 0:
                continue

            # Get price on date `d` or fall back to last known price
            day_price = price_map.get(d, {}).get(code)
            if day_price is not None:
                last_known_prices[code] = day_price
            else:
                day_price = last_known_prices.get(code, h["avg_cost"])

            daily_value += h["units"] * day_price
            daily_cost += h["units"] * h["avg_cost"]

        performance_timeline.append({
            "date": d,
            "value": round(daily_value, 2),
            "cost": round(daily_cost, 2),
            "profit": round(daily_value - daily_cost, 2)
        })

    conn.close()
    return {"performance": performance_timeline}

@app.get("/api/simulator/run")
def run_simulation(code: str = Query(...), amount: float = Query(...), start_date: str = Query(...)):
    conn = get_conn()
    c = conn.cursor()
    code = code.upper()

    # 1. Başlangıç tarihindeki en yakın fiyatı bul
    c.execute("""
        SELECT price, date
        FROM fund_daily
        WHERE code = ? AND date >= ?
        ORDER BY date ASC
        LIMIT 1
    """, (code, start_date))
    start_row = c.fetchone()

    # 2. Bitiş (en güncel) tarihteki fiyatı bul
    c.execute("""
        SELECT price, date
        FROM fund_daily
        WHERE code = ?
        ORDER BY date DESC
        LIMIT 1
    """, (code,))
    end_row = c.fetchone()

    if not start_row or not end_row:
        conn.close()
        return {"status": "error", "message": f"{code} fonu için yeterli tarihsel fiyat verisi bulunamadı."}

    start_price = start_row["price"]
    end_price = end_row["price"]
    actual_start_date = start_row["date"]
    actual_end_date = end_row["date"]

    units_bought = amount / start_price
    end_value = units_bought * end_price
    profit = end_value - amount
    profit_pct = (profit / amount) * 100 if amount > 0 else 0.0

    # Benchmarks: Altın (TTA) ve BIST 100 (TI1)
    benchmarks = []
    for b_name, b_code in [("Gram Altın (Fon)", "TTA"), ("BIST 100 (Fon)", "TI1")]:
        c.execute("""
            SELECT price FROM fund_daily WHERE code = ? AND date >= ? ORDER BY date ASC LIMIT 1
        """, (b_code, start_date))
        b_start = c.fetchone()

        c.execute("""
            SELECT price FROM fund_daily WHERE code = ? ORDER BY date DESC LIMIT 1
        """, (b_code,))
        b_end = c.fetchone()

        if b_start and b_end:
            b_val = (amount / b_start["price"]) * b_end["price"]
            benchmarks.append({
                "name": b_name,
                "value": b_val,
                "profit": b_val - amount,
                "profit_pct": ((b_val - amount) / amount) * 100
            })
        else:
            fallback_rate = 0.35 if b_code == "TTA" else 0.45
            b_val = amount * (1 + fallback_rate)
            benchmarks.append({
                "name": b_name,
                "value": b_val,
                "profit": b_val - amount,
                "profit_pct": fallback_rate * 100
            })

    # Amerikan Doları kıyaslaması (ortalama %22 getiri varsayımı)
    usd_val = amount * 1.22
    benchmarks.append({
        "name": "Amerikan Doları ($)",
        "value": usd_val,
        "profit": usd_val - amount,
        "profit_pct": 22.0
    })

    conn.close()
    return {
        "status": "success",
        "fund": {
            "code": code,
            "start_date": actual_start_date,
            "end_date": actual_end_date,
            "start_price": start_price,
            "end_price": end_price,
            "units": units_bought,
            "amount": amount,
            "end_value": end_value,
            "profit": profit,
            "profit_pct": profit_pct,
        },
        "benchmarks": benchmarks
    }


# ── Yapay Zeka (AI) Modülü (Faz 4) ────────────────────

def get_fund_risk_score(name: str, code: str) -> int:
    n = (name or "").upper()
    c = (code or "").upper()
    if "PARA PİYASASI" in n or "KISA VADELİ" in n or c == "TI1":
        return 1
    if "BORÇLANMA" in n or "KIRA" in n or c == "HCV":
        return 3
    if "ALTIN" in n or "GÜMÜŞ" in n or "KIYMETLİ" in n or c == "TTA":
        return 5
    if "HİSSE" in n or "BİST" in n or c in ["MAC", "YAS", "KLH", "BMU"]:
        return 7
    return 4

def call_gemini(prompt: str) -> str:
    import os
    import requests
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return (
            "### 🤖 Yapay Zeka Özellikleri Devre Dışı\n\n"
            "Portföy ve fon analizi yapay zekasını aktifleştirmek için lütfen `.env` dosyanıza "
            "aşağıdaki gibi geçerli bir API anahtarı ekleyin:\n\n"
            "```env\nGEMINI_API_KEY=AIzaSy...\n```\n\n"
            "Ardından analizlerinizi tek tıkla üretebilirsiniz!"
        )
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=25)
        if response.status_code == 200:
            res_json = response.json()
            return res_json["candidates"][0]["content"]["parts"][0]["text"]
        else:
            return f"Yapay zeka analiz motoru şu anda meşgul. Lütfen daha sonra tekrar deneyin (Hata Kodu: {response.status_code})."
    except Exception as e:
        return f"Analiz motoru ile bağlantı kurulamadı: {str(e)}"

@app.get("/api/ai/interpret")
def get_ai_interpretation(code: str, risk_profile: Optional[str] = None):
    conn = get_conn()
    c = conn.cursor()
    code = code.upper()
    
    c.execute("SELECT MAX(date) FROM fund_daily")
    last_date = c.fetchone()[0]
    if not last_date:
        conn.close()
        return {"analysis": "Veritabanında tarihsel fiyat verisi bulunamadı."}
    
    c.execute("""
        SELECT fd.price, fd.pct_change, fd.net_flow, fd.num_investors, fd.market_cap, fn.name
        FROM fund_daily fd
        LEFT JOIN fund_names fn ON fd.code = fn.code
        WHERE fd.code = ? AND fd.date = ?
    """, (code, last_date))
    fund = c.fetchone()
    
    if not fund:
        conn.close()
        return {"analysis": f"{code} kodu için güncel veri bulunamadı."}
        
    c.execute("""
        SELECT allocation_json FROM fund_breakdown
        WHERE code = ? ORDER BY date DESC LIMIT 1
    """, (code,))
    alloc_row = c.fetchone()
    allocation_str = "Varlık dağılım detayı bulunmuyor."
    if alloc_row and alloc_row["allocation_json"]:
        try:
            import json
            alloc_data = json.loads(alloc_row["allocation_json"])
            allocation_str = ", ".join(f"%{v:.2f} {k}" for k, v in alloc_data.items() if v > 0)
        except Exception:
            pass
            
    conn.close()
    
    name = fund["name"] or "Bilinmeyen Fon"
    price = fund["price"]
    pct_change = fund["pct_change"] or 0.0
    net_flow = fund["net_flow"] or 0.0
    num_investors = fund["num_investors"] or 0
    mcap = fund["market_cap"] or 0.0
    
    risk_level = classify_risk(name, code)
    risk_num = get_fund_risk_score(name, code)
    
    prompt = f"""
    Sen TEFAS Platformunun gelişmiş yapay zeka yatırım asistanısın. Görevin, aşağıda detayları belirtilen TEFAS fonunu teknik ve temel açıdan analiz etmek.
    
    Fon Bilgileri:
    - Fon Kodu: {code}
    - Fon Adı: {name}
    - Son Birim Fiyat: {price:.4f} TL
    - Günlük Getiri: %{pct_change:.2f}
    - Son Seans Net Giriş/Çıkış: {net_flow:,.2f} TL
    - Yatırımcı Sayısı: {num_investors:,}
    - Fon Toplam Değeri (Portföy Büyüklüğü): {mcap:,.2f} TL
    - Varlık Dağılım Kompozisyonu: {allocation_str}
    - Sistem Tahmini Risk Seviyesi: {risk_num} / 7 ({risk_level} Risk)
    
    Kullanıcı Risk Profili: {risk_profile or "Belirtilmedi"}
    
    Lütfen bu fonu profesyonel bir finans analisti gözüyle analiz et.
    Analizinde şu alt başlıkları kullan:
    1. **Genel Özet:** Fonun temel yapısı, büyüklüğü ve son performansı hakkında kısa bir özet.
    2. **Varlık Dağılım Analizi:** Varlık dağılımının ne anlama geldiği ve getiriye/riske olası etkileri.
    3. **Risk & Volatilite Değerlendirmesi:** Risk seviyesi 1-7 skalasında nerede, kimler için uygun?
    4. **Risk Profili Uygunluğu:** Bu fon, '{risk_profile or "Genel"}' profilindeki bir yatırımcıya uygun mudur? (Eğer risk profili belirtilmediyse, genel olarak hangi profil tipi için uygun olduğunu belirt).
    
    *Önemli Not:* Analizinin en altına belirgin kalın veya italik harflerle "Bu analiz tamamen bilgilendirme amaçlı olup, 6362 sayılı Sermaye Piyasası Kanunu kapsamında bir yatırım tavsiyesi (yönlendirme) taşımamaktadır." uyarısı ekle.
    
    Türkçe, anlaşılır, yatırımcıyı eğiten ve profesyonel bir üslupla markdown formatında yaz.
    """
    
    analysis = call_gemini(prompt)
    return {"analysis": analysis}

@app.get("/api/ai/portfolio-review")
def get_ai_portfolio_review(session_id: str):
    summary = get_portfolio_summary(session_id)
    holdings = summary.get("holdings", [])
    sum_metrics = summary.get("summary", {})
    
    if not holdings:
        return {"analysis": "Yapay zeka portföy analizi için lütfen öncelikle portföyünüze en az bir işlem (alım) ekleyin."}
        
    total_val = sum_metrics.get("total_value", 0.0)
    total_cost = sum_metrics.get("total_cost", 0.0)
    total_profit = sum_metrics.get("total_profit", 0.0)
    total_profit_pct = sum_metrics.get("total_profit_pct", 0.0)
    
    weighted_risk = 0.0
    weighted_fee = 0.0
    
    holdings_info = []
    for h in holdings:
        units = h["units"]
        code = h["code"]
        name = h["name"]
        val = h["current_value"]
        avg_cost = h["avg_cost"]
        profit = h["profit"]
        profit_pct = h["profit_pct"]
        
        risk_score = get_fund_risk_score(name, code)
        fee_rate = 1.50
        n = name.upper()
        if "PARA PİYASASI" in n or "KISA VADELİ" in n or code == "TI1":
            fee_rate = 0.75
        elif "HİSSE" in n or "BİST" in n or code in ["MAC", "YAS", "KLH", "BMU"]:
            fee_rate = 2.25
            
        weighted_risk += val * risk_score
        weighted_fee += val * fee_rate
        
        holdings_info.append(
            f"- **{code}** ({name}): Adet: {units:,.4f}, Ortalama Maliyet: {avg_cost:.4f} TL, Güncel Değer: {val:,.2f} TL, "
            f"Risk Skoru: {risk_score}/7, Tahmini Yönetim Ücreti: %{fee_rate:.2f}, Kâr/Zarar: {profit:,.2f} TL (%{profit_pct:.2f})"
        )
        
    blended_risk = (weighted_risk / total_val) if total_val > 0 else 0.0
    blended_fee = (weighted_fee / total_val) if total_val > 0 else 0.0
    
    holdings_str = "\n".join(holdings_info)
    
    allocation_summary = get_portfolio_allocation(session_id)
    alloc_list = allocation_summary.get("allocation", [])
    alloc_str = ", ".join(f"%{a['percentage']:.1f} {a['category']}" for a in alloc_list)
    
    prompt = f"""
    Sen TEFAS Platformunun son derece yetkin, premium yapay zeka baş yatırım danışmanısın. Kullanıcının aşağıda detayları verilen gerçek fon portföyünü profesyonelce inceleyeceksin.
    
    Kullanıcı Portföy Özeti:
    - Toplam Portföy Değeri: {total_val:,.2f} TL
    - Toplam Maliyet (Sermaye): {total_cost:,.2f} TL
    - Toplam Net Kâr/Zarar: {total_profit:,.2f} TL (Toplam Getiri: %{total_profit_pct:.2f})
    - Ağırlıklı Portföy Risk Puanı: {blended_risk:.1f} / 7.0
    - Ağırlıklı Yıllık Yönetim Ücreti: %{blended_fee:.2f}
    - Kategori Bazlı Varlık Dağılımı: {alloc_str}
    
    Aktif Varlıklar ve Pozisyon Detayları:
    {holdings_str}
    
    Lütfen bu portföyü finans dünyasının en prestijli analiz teknikleriyle incele ve Türkçe markdown formatında ayrıntılı bir rapor sun.
    Raporunda şu bölümleri bulundur:
    
    1. **Portföy Sağlık Karnesi:** Portföyün genel performansı, maliyeti ve risk seviyesinin hızlı bir değerlendirmesi (Örn: Çok İyi, Dengeli, Yüksek Riskli, Yüksek Maliyetli vb.).
    2. **Çeşitlendirme & Varlık Dağılımı Kalitesi:** Kategori bazlı dağılımın dengeli olup olmadığı, tek bir fona veya sektöre aşırı bağımlılık (yoğunlaşma riski) bulunup bulunmadığı analizi.
    3. **Maliyet & Verimlilik Değerlendirmesi:** Ağırlıklı yıllık yönetim ücretinin (%{blended_fee:.2f}) makul olup olmadığı. Daha ucuz alternatiflerle nasıl optimize edilebileceği.
    4. **Risk Profile Göre Durum:** Bu portföyün ağırlıklı risk puanı ({blended_risk:.1f}/7) hangi yatırımcı tipine uygundur? (Defansif mi, Dengeli mi, Agresif mi?).
    5. **Stratejik İyileştirme Önerileri:** Portföyü daha dirençli ve verimli kılmak için somut, analitik öneriler (Varlık satışı önermeden, oranların nasıl optimize edilebileceğine dair taktikler).
    
    *Önemli Not:* Raporunun en altına belirgin kalın veya italik harflerle "Bu portföy incelemesi tamamen yapay zeka tarafından üretilen analitik bir simülasyon olup, 6362 sayılı Sermaye Piyasası Kanunu kapsamında kişiye özel bir yatırım danışmanlığı veya portföy yönetim faaliyeti teşkil etmemektedir." uyarısı ekle.
    
    Çıktıyı harika ve okuması çok kolay bir markdown yapısında sun. Tablolar, kalın metinler ve listeler kullan.
    """
    
    analysis = call_gemini(prompt)
    return {"analysis": analysis}

# ── Run ────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8085, reload=True)

