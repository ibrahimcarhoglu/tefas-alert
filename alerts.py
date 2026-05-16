import asyncio
import logging
import html
import re
from datetime import datetime
from telegram import Bot
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from database import get_dashboard_data

logger = logging.getLogger(__name__)

TEFAS_URL = "https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod="

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
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📈 Toplam Giriş: <b>{_fmt_try(total_inflow)}</b>",
        "\n💰 <b>En Çok Para Girişi:</b>"
    ]
    for r in top_inflows:
        code = r[0]
        fname = html.escape(names.get(code, ""))
        name_str = f"\n<pre>{fname[:25]}...</pre>" if fname else ""
        lines.append(f"• <a href='{TEFAS_URL}{code}'><b>{code}</b></a>: {_fmt_try(r[1])}{name_str}")
    
    asyncio.run(_send_message("\n".join(lines)))

def send_social_pulse(date_str: str, trending_funds: list[dict]):
    """Sosyal medya ve yatırımcı trendlerini HTML temasına göre raporlar."""
    lines = [
        "🟢 <b>SOSYAL MEDYA &amp; TRENDLER</b>",
        "🏆 <b>TOP 10 FON TRENDİ</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📅 <code>{date_str}</code> · ⚡ <code>TEFAS</code> · 📊 <code>TREND</code>",
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    
    if not trending_funds:
        lines.append("<i>Şu an sosyal medyada ve yatırımcı akışında anormal bir hareketlilik tespit edilmedi. Piyasa sakin.</i>")
    else:
        for idx, f in enumerate(trending_funds, 1):
            rank_str = f"<b>{idx:02d}.</b>"
            code_str = f"<a href='{TEFAS_URL}{f['code']}'><b>{f['code']}</b></a>"
            pct_str = f"<b>{f['pct']}</b>"
            stat_str = f"({f['stat']})" if f['stat'] else ""
            
            # Clean up duplicate newlines/whitespaces in reason
            reason = html.escape(re.sub(r'\s+', ' ', f['reason']).strip())
            
            lines.append(f"{rank_str} {code_str}  🟢 {pct_str} {stat_str}")
            lines.append(f"↳ <i>{reason}</i>\n")
        
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ <i>Yatırım tavsiyesi değildir · Geçmiş getiri garanti oluşturmaz</i>")
    asyncio.run(_send_message("\n".join(lines)))

def send_periodic_summary(date_str: str, periodic_results: dict):
    """TOP 15 Periyodik Getiri Listesini zengin tasarımla raporlar."""
    for label, df in periodic_results.items():
        lines = [
            "⚡ <b>PERİYODİK ANALİZ</b>",
            f"🚀 <b>TOP 15 GETİRİ LİSTESİ ({label.upper()})</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📅 <code>{date_str}</code> · 📈 <code>{label} Vade</code> · 🏛️ <code>TEFAS</code>",
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        ]
        
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            code = row['fund_code']
            fname = row.get('fund_name', 'Bilinmeyen Fon')
            safe_name = html.escape(str(fname))
            name = safe_name[:40] + "..." if len(safe_name) > 40 else safe_name
            
            pct = row['pct_change']
            pct_str = f"+%{pct:.2f}" if pct >= 0 else f"-%{abs(pct):.2f}"
            emoji = "🔼" if pct >= 0 else "🔽"
            
            rank_str = f"<b>{idx:02d}.</b>"
            code_str = f"<a href='{TEFAS_URL}{code}'><b>{code}</b></a>"
            
            lines.append(f"{rank_str} {code_str}  {emoji} <b>{pct_str}</b>")
            lines.append(f"↳ <i>{name}</i>\n")
            
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("⚠️ <i>Yatırım tavsiyesi değildir · Geçmiş getiri garanti oluşturmaz</i>")
        asyncio.run(_send_message("\n".join(lines)))

def send_anomaly_alerts(anomalies: list[dict], date: str):
    if not anomalies: return
    lines = [f"🚨 <b>ANOMALİ ALARMI</b> — {date}", "━━━━━━━━━━━━━━━━━━━━━━━━"]
    for a in anomalies[:15]:
        code = a['code']
        safe_label = html.escape(a['label'])
        safe_detail = html.escape(a['detail'])
        lines.append(f"\n{a.get('severity', '🟡')} <a href='{TEFAS_URL}{code}'><b>{code}</b></a>\n  ↳ {safe_label}: {safe_detail}")
    asyncio.run(_send_message("\n".join(lines)))

def _fmt_try(amount: float) -> str:
    if abs(amount) >= 1_000_000_000:
        return f"{amount/1_000_000_000:+.2f}B ₺"
    elif abs(amount) >= 1_000_000:
        return f"{amount/1_000:+.2f}M ₺"
    return f"{amount:+.2f} ₺"
