import asyncio
import logging
import html
import re
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
        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID, 
            text=text, 
            parse_mode=ParseMode.HTML, 
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error("Mesaj gönderilemedi: %s", e)

def _fmt_try(amount: float) -> str:
    if amount is None:
        return "0.00 ₺"
    if abs(amount) >= 1_000_000_000:
        return f"{amount/1_000_000_000:+.2f}B ₺"
    elif abs(amount) >= 1_000_000:
        return f"{amount/1_000_000:+.2f}M ₺"
    return f"{amount:+.2f} ₺"

async def send_daily_summary(date: str = None, names: dict = None):
    data = get_dashboard_data()
    if not data: 
        return
    total_inflow = data.get("total_inflow", 0)
    top_inflows = data.get("top_inflows", [])[:5]
    names = names or {}
    
    lines = [
        f"📊 <b>TEFAS GÜNLÜK ÖZET REPORT</b>",
        f"📅 <code>{date}</code>",
        "────────────────────────",
        f"📈 <b>Toplam Net Giriş:</b> <code>{_fmt_try(total_inflow)}</code>",
        "\n💰 <b>EN YÜKSEK PARA GİRİŞİ (TOP 5)</b>",
        "────────────────────────"
    ]
    
    medals = ["🥇", "🥈", "🥉", "🔹", "🔹"]
    for idx, r in enumerate(top_inflows):
        code = r[0]
        fname = html.escape(names.get(code, "Bilinmeyen Fon"))
        name_str = fname[:30] + "..." if len(fname) > 30 else fname
        
        medal = medals[idx] if idx < len(medals) else "🔹"
        
        # Kod ve Para miktarını net ayırıp alt satıra ağaç çizgisiyle fon adını koyuyoruz
        lines.append(f"{medal} <a href='{TEFAS_URL}{code}'><b>{code}</b></a> ➜ <code>{_fmt_try(r[1])}</code>")
        lines.append(f"    └── <i>{name_str}</i>\n")
    
    lines.append("────────────────────────")
    lines.append("⚠️ <i>Yatırım tavsiyesi değildir.</i>")
    await _send_message("\n".join(lines))

async def send_social_pulse(date_str: str, trending_funds: list[dict]):
    lines = [
        "🔥 <b>SOSYAL MEDYA &amp; YATIRIMCI TRENDLERİ</b>",
        f"📅 <code>{date_str}</code> · ⚡ <code>TEFAS Pulse</code>",
        "────────────────────────\n"
    ]
    
    if not trending_funds:
        lines.append("▫️ <i>Piyasada anormal bir hareketlilik tespit edilmedi.</i>")
    else:
        for idx, f in enumerate(trending_funds, 1):
            code_str = f"<a href='{TEFAS_URL}{f['code']}'><b>{f['code']}</b></a>"
            pct_str = f"<code>{f['pct']}</code>"
            stat_str = f" ({f['stat']})" if f['stat'] else ""
            reason = html.escape(re.sub(r'\s+', ' ', f['reason']).strip())
            
            lines.append(f"<b>{idx:02d}.</b> {code_str} ➜ {pct_str}{stat_str}")
            lines.append(f"    💬 <i>{reason}</i>\n")
        
    lines.append("────────────────────────")
    lines.append("⚠️ <i>Geçmiş performans gelecek getirinin garantisi değildir.</i>")
    await _send_message("\n".join(lines))

async def send_periodic_summary(date_str: str, periodic_results: dict):
    for label, df in periodic_results.items():
        lines = [
            "⚡ <b>PERİYODİK PERFORMANS ANALİZİ</b>",
            f"🚀 <b>TOP 15 LİSTESİ ({label.upper()} VADE)</b>",
            "────────────────────────",
            f"📅 <code>{date_str}</code> · 📈 <code>TEFAS Verileri</code>",
            "────────────────────────\n"
        ]
        
        for idx, (_, row) in enumerate(df.iterrows(), 1):
            code = row['fund_code']
            fname = row.get('fund_name', 'Bilinmeyen Fon')
            safe_name = html.escape(str(fname))
            name = safe_name[:32] + "..." if len(safe_name) > 32 else safe_name
            
            pct = row['pct_change']
            # Değişime göre renkli emoji belirleme
            emoji = "🔺" if pct >= 0 else "🔻"
            pct_str = f"<code>{pct:+.2f}%</code>"
            
            code_str = f"<a href='{TEFAS_URL}{code}'><b>{code}</b></a>"
            
            lines.append(f"<b>{idx:02d}.</b> {code_str}  {emoji} {pct_str}")
            lines.append(f"    └── <i>{name}</i>\n")
            
        lines.append("────────────────────────")
        lines.append("⚠️ <i>Yatırım tavsiyesi değildir.</i>")
        await _send_message("\n".join(lines))

async def send_anomaly_alerts(anomalies: list[dict], date: str):
    if not anomalies: 
        return
    lines = [
        "🚨 <b>HASSAS ANOMALİ ALARMI</b>",
        f"📅 <code>{date}</code>",
        "────────────────────────"
    ]
    for a in anomalies[:15]:
        code = a['code']
        severity = a.get('severity', '🟡')
        safe_label = html.escape(a['label'])
        safe_detail = html.escape(a['detail'])
        
        lines.append(f"\n{severity} <a href='{TEFAS_URL}{code}'><b>{code}</b></a> ➜ <b>{safe_label}</b>")
        lines.append(f"    └── <i>{safe_detail}</i>")
        
    lines.append("\n────────────────────────")
    await _send_message("\n".join(lines))