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
        return f"{amount/1_000_000:+.2f}M ₺"
    elif abs(amount) >= 1_000:
        return f"{amount/1_000:+.2f}K ₺"
    return f"{amount:+.2f} ₺"


async def _send_message(text: str):
    """Telegram'a mesaj gönderir."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("Telegram token veya chat ID eksik! .env dosyasını kontrol et.")
        return
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=text,
        parse_mode=ParseMode.HTML,
    )


def send_message_sync(text: str):
    asyncio.run(_send_message(text))


async def _send_anomaly_alerts(anomalies: list[dict], date: str):
    """Tespit edilen anomaliler için Telegram mesajı gönderir."""
    if not anomalies:
        return

    # Kritikliğe göre sırala
    priority_order = {"🔴 KRİTİK": 0, "🟠 YÜKSEK": 1, "🟡 ORTA": 2}
    anomalies_sorted = sorted(anomalies, key=lambda x: priority_order.get(x.get("severity", "🟡 ORTA"), 3))

    # Her 10 anomalide bir mesaj (Telegram mesaj limiti aşmamak için)
    chunks = [anomalies_sorted[i:i+10] for i in range(0, len(anomalies_sorted), 10)]

    bot = Bot(token=TELEGRAM_BOT_TOKEN)

    for i, chunk in enumerate(chunks):
        lines = [
            f"🚨 <b>TEFAS ANOMALİ ALARMI</b> — {date}",
            f"━━━━━━━━━━━━━━━━━━━━━━━━",
        ]

        if len(chunks) > 1:
            lines.append(f"📋 Grup {i+1}/{len(chunks)}")

        for a in chunk:
            lines.append(
                f"\n{a['severity']} <b>{a['code']}</b>\n"
                f"  ↳ {a['label']}: {a['detail']}"
            )

        lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"<i>Toplam {len(anomalies)} anomali tespit edildi</i>")

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="\n".join(lines),
            parse_mode=ParseMode.HTML,
        )


async def _send_daily_summary(date: str):
    """Günlük özet raporunu gönderir."""
    data = get_dashboard_data()
    if not data or not data.get("last_date"):
        return

    top_inflows = data.get("top_inflows", [])[:5]
    top_outflows = data.get("top_outflows", [])[:5]
    top_returns = data.get("top_returns", [])[:5]
    total_inflow = data.get("total_inflow", 0)
    total_outflow = data.get("total_outflow", 0)
    total_funds = data.get("total_funds", 0)

    lines = [
        f"📊 <b>TEFAS GÜNLÜK ÖZET</b> — {date}",
        f"━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📈 Toplam Para Girişi: <b>{_fmt_try(total_inflow)}</b>",
        f"📉 Toplam Para Çıkışı: <b>{_fmt_try(total_outflow)}</b>",
        f"🏦 İzlenen Fon Sayısı: <b>{total_funds}</b>",
        "",
        "💰 <b>En Fazla Para Girişi:</b>",
    ]

    for r in top_inflows:
        code, net_flow, pct_change, num_inv, market_cap = r
        lines.append(f"  • <b>{code}</b>: {_fmt_try(net_flow or 0)} (%{pct_change:.1f} getiri)" if pct_change else f"  • <b>{code}</b>: {_fmt_try(net_flow or 0)}")

    lines.append("\n🚪 <b>En Fazla Para Çıkışı:</b>")
    for r in top_outflows:
        code, net_flow, pct_change, num_inv, market_cap = r
        lines.append(f"  • <b>{code}</b>: {_fmt_try(net_flow or 0)}")

    lines.append("\n🚀 <b>En Yüksek Getiri:</b>")
    for r in top_returns:
        code, pct_change, net_flow, num_inv, market_cap = r
        lines.append(f"  • <b>{code}</b>: %{pct_change:.2f}" if pct_change else f"  • <b>{code}</b>")

    lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"⏰ {datetime.now().strftime('%H:%M')}")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="\n".join(lines),
        parse_mode=ParseMode.HTML,
    )


def send_anomaly_alerts(anomalies: list[dict], date: str = None):
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram yapılandırılmamış — alert gönderilemiyor.")
        return
    asyncio.run(_send_anomaly_alerts(anomalies, date))


def send_daily_summary(date: str = None):
    if date is None:
        date = datetime.today().strftime("%Y-%m-%d")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram yapılandırılmamış — özet gönderilemiyor.")
        return
    asyncio.run(_send_daily_summary(date))


async def _test_connection():
    """Telegram bağlantısını test eder."""
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    me = await bot.get_me()
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=(
            "✅ <b>TEFAS Alert Botu Aktif!</b>\n\n"
            "Merhaba! Ben her sabah TEFAS fon verilerini analiz edip "
            "anormal para girişi/çıkışlarını sana bildireceğim.\n\n"
            "📊 Günlük özet + 🚨 Anomali alertleri burada görünecek."
        ),
        parse_mode=ParseMode.HTML,
    )
    return me.username


def test_telegram_connection():
    """Senkron test wrapper'ı."""
    return asyncio.run(_test_connection())
