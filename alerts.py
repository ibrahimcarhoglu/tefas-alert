import asyncio
import logging
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from database import get_dashboard_data

logger = logging.getLogger(__name__)

def _fmt_try(amount: float) -> str:
    if abs(amount) >= 1_000_000_000:
        return f"{amount/1_000_000_000:+.2f}B ₺"
    elif abs(amount) >= 1_000_000:
        return f"{amount/1_000:+.2f}M ₺"
    return f"{amount:+.2f} ₺"

async def _send_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text[i:i+4000], parse_mode=ParseMode.HTML)
    else:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode=ParseMode.HTML)

def send_daily_summary(date: str = None):
    """Günlük özet raporu."""
    data = get_dashboard_data()
    if not data: return
    
    total_inflow = data.get("total_inflow", 0)
    top_inflows = data.get("top_inflows", [])[:5]
    
    lines = [
        f"📊 <b>GÜNLÜK ÖZET</b> — {date}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📈 Para Girişi: <b>{_fmt_try(total_inflow)}</b>",
        "\n💰 <b>En Çok Para Girişi:</b>"
    ]
    for r in top_inflows:
        lines.append(f"  • {r[0]}: {_fmt_try(r[1])}")
    
    asyncio.run(_send_message("\n".join(lines)))

def send_periodic_summary(date_str: str, periodic_results: dict):
    """Periyotlara göre Top 20 listesi."""
    lines = [
        f"🚀 <b>TOP 20 PERİYODİK GETİRİ ANALİZİ</b>",
        f"📅 Tarih: {date_str}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━"
    ]
    
    for label, df in periodic_results.items():
        lines.append(f"\n<b>{label}:</b>")
        lines.append(f"<code>{'Kod':<6} {'Değişim':<10}</code>")
        for _, row in df.iterrows():
            lines.append(f"<code>{row['fund_code']:<6} %{row['pct_change']:>7.2f}</code>")
        lines.append(f"────────────────────────")

    asyncio.run(_send_message("\n".join(lines)))

def send_anomaly_alerts(anomalies: list[dict], date: str):
    """Anomali bildirimleri."""
    if not anomalies: return
    lines = [f"🚨 <b>ANOMALİ ALARMI</b> — {date}", "━━━━━━━━━━━━━━━━━━━━━━━━"]
    for a in anomalies[:15]: # Limitli
        lines.append(f"\n{a.get('severity', '🟡')} <b>{a['code']}</b>\n  ↳ {a['label']}: {a['detail']}")
    asyncio.run(_send_message("\n".join(lines)))
