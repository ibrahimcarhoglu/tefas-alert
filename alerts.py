import asyncio
import logging
import html
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from database import get_dashboard_data

logger = logging.getLogger(__name__)

# TEFAS Fon Analiz Linki Sabiti
TEFAS_URL = "https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod="

def _fmt_try(amount: float) -> str:
    if abs(amount) >= 1_000_000_000:
        return f"{amount/1_000_000_000:+.2f}B ₺"
    elif abs(amount) >= 1_000_000:
        return f"{amount/1_000:+.2f}M ₺"
    return f"{amount:+.2f} ₺"

async def _send_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not text:
        return
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
    except Exception as e:
        logger.error("Mesaj gönderilemedi: %s", e)

def send_daily_summary(date: str = None, names: dict = None):
    data = get_dashboard_data()
    if not data: return
    total_inflow = data.get("total_inflow", 0)
    top_inflows = data.get("top_inflows", [])[:5]
    names = names or {}
    
    lines = [
        f"📊 <b>GÜNLÜK ÖZET</b> — {date}",
        f"🌐 <a href='https://www.tefas.gov.tr'>TEFAS Platformu Aktif</a>",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📈 Toplam Giriş: <b>{_fmt_try(total_inflow)}</b>",
        "\n💰 <b>En Çok Para Girişi:</b>"
    ]
    for r in top_inflows:
        code = r[0]
        fname = html.escape(names.get(code, ""))
        name_str = f"\n<pre>{fname[:25]}...</pre>" if fname else ""
        # Kod üzerine TEFAS linki ekle
        lines.append(f"• <a href='{TEFAS_URL}{code}'><b>{code}</b></a>: {_fmt_try(r[1])}{name_str}")
    
    asyncio.run(_send_message("\n".join(lines)))

def send_periodic_summary(date_str: str, periodic_results: dict):
    header = f"🚀 <b>TOP 20 PERİYODİK ANALİZ</b>\n📅 Tarih: {date_str}\n━━━━━━━━━━━━━━━━━━━━━━━━"
    asyncio.run(_send_message(header))
    
    for label, df in periodic_results.items():
        lines = [f"🔥 <b>{label}:</b>"]
        for _, row in df.iterrows():
            code = row['fund_code']
            fname = row.get('fund_name', 'Bilinmeyen Fon')
            safe_name = html.escape(str(fname))
            name = safe_name[:35] + "..." if len(safe_name) > 35 else safe_name
            # Kod üzerine TEFAS linki ekle
            lines.append(f"<a href='{TEFAS_URL}{code}'><b>{code}</b></a> - %{row['pct_change']:>5.2f}\n<pre>{name}</pre>")
        lines.append(f"────────────────────────")
        asyncio.run(_send_message("\n".join(lines)))

def send_anomaly_alerts(anomalies: list[dict], date: str):
    if not anomalies: return
    lines = [f"🚨 <b>ANOMALİ ALARMI</b> — {date}", "━━━━━━━━━━━━━━━━━━━━━━━━"]
    for a in anomalies[:15]:
        code = a['code']
        safe_label = html.escape(a['label'])
        safe_detail = html.escape(a['detail'])
        # Kod üzerine TEFAS linki ekle
        lines.append(f"\n{a.get('severity', '🟡')} <a href='{TEFAS_URL}{code}'><b>{code}</b></a>\n  ↳ {safe_label}: {safe_detail}")
    asyncio.run(_send_message("\n".join(lines)))
