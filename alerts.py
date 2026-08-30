import asyncio
import logging
import html
import io
import re
import sqlite3
from telegram import Bot
from telegram.constants import ParseMode
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, DB_PATH
from database import get_dashboard_data

logger = logging.getLogger(__name__)

# python-telegram-bot uses httpx. INFO-level request logs include the full
# Telegram Bot API URL, which contains the secret bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

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


async def _send_photo_bytes(data: bytes, filename: str, caption: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID or not data:
        return
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    photo = io.BytesIO(data)
    photo.name = filename
    try:
        await bot.send_photo(
            chat_id=TELEGRAM_CHAT_ID,
            photo=photo,
            caption=caption,
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        logger.error("Görsel mesaj gönderilemedi: %s", exc)
        raise

def _fmt_try(amount: float) -> str:
    if amount is None:
        return "0.00 ₺"
    if abs(amount) >= 1_000_000_000:
        return f"{amount/1_000_000_000:+.2f}B ₺"
    elif abs(amount) >= 1_000_000:
        return f"{amount/1_000_000:+.2f}M ₺"
    return f"{amount:+.2f} ₺"

def get_tefas_status(code: str, name: str, investor_count: int = None) -> str:
    """Fon adından ve yatırımcı sayısından yola çıkarak TEFAS'ta işlem görüp görmediğini belirler."""
    code_upper = code.upper()
    name_upper = name.upper() if name else ""

    # 1. İstisna Kuralı: TEFAS'ta kesinlikle işlem gören serbest fonlar
    always_open_codes = {
        'BMU', 'KLH', 'TTA', 'TLY', 'ZPR', 'PPS', 'KSV', 'KLU', 'DZM', 'DPB', 'DIP', 'AES'
    }
    if code_upper in always_open_codes:
        return "Açık"

    if "ÖZEL" in name_upper or "MÜNFERİT" in name_upper:
        return "Kapalı"

    if "SERBEST" not in name_upper:
        return "Açık"

    if investor_count is not None and investor_count > 100:
        return "Açık"

    return "Kapalı"

def _get_fund_metadata(code: str, date_str: str) -> tuple[str, int]:
    """SQLite veritabanından fonun ismini ve o tarihteki yatırımcı sayısını çeker."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # İsmi bul
        cursor.execute("SELECT name FROM fund_names WHERE code = ?", (code,))
        name_row = cursor.fetchone()
        name = name_row[0] if name_row else "Bilinmeyen Fon"

        # Yatırımcı sayısını bul
        cursor.execute("SELECT num_investors FROM fund_daily WHERE code = ? AND date = ?", (code, date_str))
        inv_row = cursor.fetchone()
        num_investors = inv_row[0] if inv_row else None

        conn.close()
        return name, num_investors
    except Exception as e:
        logger.error("Metadata çekme hatası (%s): %s", code, e)
        return "Bilinmeyen Fon", None

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

        # TEFAS durumunu çek
        status = get_tefas_status(code, fname, r[3])
        status_label = "🟢 Açık" if status == "Açık" else "🔴 Kapalı"

        medal = medals[idx] if idx < len(medals) else "🔹"

        lines.append(f"{medal} <a href='{TEFAS_URL}{code}'><b>{code}</b></a> ({status_label}) ➜ <code>{_fmt_try(r[1])}</code>")
        lines.append(f"    └── <i>{name_str}</i>\n")

    lines.append("────────────────────────")
    lines.append("⚠️ <i>Yatırım tavsiyesi değildir.</i>")
    await _send_message("\n".join(lines))

async def send_social_pulse(date_str: str, trending_funds: list[dict]):
    lines = [
        "🔥 <b>SOSYAL MEDYA & YATIRIMCI TRENDLERİ</b>",
        f"📅 <code>{date_str}</code> · ⚡ <code>TEFAS Pulse</code>",
        "────────────────────────\n"
    ]

    if not trending_funds:
        lines.append("▫️ <i>Piyasada anormal bir hareketlilik tespit edilmedi.</i>")
    else:
        for idx, f in enumerate(trending_funds, 1):
            code = f['code']
            code_str = f"<a href='{TEFAS_URL}{code}'><b>{code}</b></a>"
            pct_str = f"<code>{f['pct']}</code>"
            stat_str = f" ({f['stat']})" if f['stat'] else ""
            reason = html.escape(re.sub(r'\s+', ' ', f['reason']).strip())

            # TEFAS durumunu çek
            name, num_investors = _get_fund_metadata(code, date_str)
            status = get_tefas_status(code, name, num_investors)
            status_label = "🟢 Açık" if status == "Açık" else "🔴 Kapalı"

            lines.append(f"<b>{idx:02d}.</b> {code_str} ({status_label}) ➜ {pct_str}{stat_str}")
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
            emoji = "🔺" if pct >= 0 else "🔻"
            pct_str = f"<code>{pct:+.2f}%</code>"

            code_str = f"<a href='{TEFAS_URL}{code}'><b>{code}</b></a>"

            # TEFAS durumunu çek
            fund_name_db, num_investors = _get_fund_metadata(code, date_str)
            status = get_tefas_status(code, fund_name_db if fund_name_db else fname, num_investors)
            status_label = "🟢 Açık" if status == "Açık" else "🔴 Kapalı"

            lines.append(f"<b>{idx:02d}.</b> {code_str} ({status_label})  {emoji} {pct_str}")
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

        # TEFAS durumunu çek
        name, num_investors = _get_fund_metadata(code, date)
        status = get_tefas_status(code, name, num_investors)
        status_label = "🟢 Açık" if status == "Açık" else "🔴 Kapalı"

        lines.append(f"\n{severity} <a href='{TEFAS_URL}{code}'><b>{code}</b></a> ({status_label}) ➜ <b>{safe_label}</b>")
        lines.append(f"    └── <i>{safe_detail}</i>")

    lines.append("\n────────────────────────")
    await _send_message("\n".join(lines))


async def send_rotation_signal_alert(rotation: dict):
    """Yeni haftalık rotasyondaki durum geçişlerini Telegram'a gönderir."""
    if not rotation.get("generated"):
        return
    recommendations = rotation.get("recommendations", [])
    if not recommendations:
        return

    lines = [
        "🧭 <b>TEFAS HAFTALIK MOMENTUM ROTASYONU</b>",
        f"📅 <code>{html.escape(str(rotation.get('signal_date', '')))}</code>",
        f"🧪 Model: <code>{html.escape(str(rotation.get('strategy_version', '')))}</code>",
        "────────────────────────",
    ]
    labels = {
        "ALIM_ADAYI": "🟢 ALIM ADAYI",
        "TUT": "🔵 TUT",
        "CIKIS_ADAYI": "🔴 ÇIKIŞ ADAYI",
    }
    for item in recommendations[:20]:
        code = html.escape(str(item.get("code", "")))
        action = labels.get(item.get("action"), str(item.get("action", "")))
        score = float(item.get("score") or 0)
        weight = float(item.get("target_weight") or 0) * 100
        reasons = item.get("reasons") or []
        reason = html.escape(str(reasons[0])) if reasons else "Model rotasyon kararı"
        weight_text = f" · Hedef %{weight:.0f}" if weight > 0 else ""
        lines.append(f"{action} · <b>{code}</b> · Skor <code>{score:.1f}</code>{weight_text}")
        lines.append(f"    └── <i>{reason}</i>")
    lines.extend([
        "────────────────────────",
        "⚠️ <i>Model sinyalidir; kesin emir veya kişiye özel yatırım tavsiyesi değildir. Fon valörü ve KAP işlem esasları ayrıca doğrulanmalıdır.</i>",
    ])
    await _send_message("\n".join(lines))


def _pct(value) -> str:
    if value is None:
        return "—"
    try:
        # Sinyal motoru getirileri 0.159 = %15,9 biçiminde oran olarak saklar.
        return f"{float(value) * 100:+.1f}%"
    except (TypeError, ValueError):
        return "—"


def _score(value) -> str:
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "—"


def _short(value, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "BİLİNMİYOR")).strip()
    return html.escape(text if len(text) <= limit else text[: limit - 1] + "…")


def _compact_founder(value) -> str:
    """Mobil mesajda şirketin hukuki eklerini kaldırarak kurucuyu okunur tut."""
    text = re.sub(r"\s+", " ", str(value or "BİLİNMİYOR")).strip()
    for suffix in (
        " PORTFÖY YÖNETİMİ A.Ş.",
        " EMEKLİLİK VE HAYAT A.Ş.",
        " HAYAT VE EMEKLİLİK A.Ş.",
        " EMEKLİLİK A.Ş.",
    ):
        if text.upper().endswith(suffix):
            text = text[: -len(suffix)].strip()
            break
    return _short(text, 20)


def _telegram_visible_length(value: str) -> int:
    """Telegram sınırı HTML işaretleri çözüldükten sonraki görünen metne uygulanır."""
    without_tags = re.sub(r"<[^>]*>", "", value)
    return len(html.unescape(without_tags))


def _tefas_label(value) -> str:
    status = str(value or "BİLİNMİYOR").upper()
    if "BEFAS" in status:
        return "🟣 BEFAS"
    if "KAPALI" in status or "DIŞI" in status or "GÖRMÜYOR" in status:
        return "⚫ DIŞARIDA"
    if "AÇIK" in status or "ACIK" in status or "GÖRÜYOR" in status:
        return "🟢 TEFAS"
    return "⚪ BELİRSİZ"


async def _send_table(title: str, date_str: str, rows: list[str], empty_text: str) -> None:
    """Telegram'ın 4096 karakter sınırını aşmadan mobil tablo gönder."""
    header = [
        title,
        f"📅 {html.escape(str(date_str or '—'))}",
    ]
    footer = [
        "",
        "⚠️ <i>Model çıktısıdır; kişiye özel yatırım tavsiyesi değildir.</i>",
    ]
    if not rows:
        await _send_message("\n".join(header + [empty_text] + footer))
        return

    chunks: list[list[str]] = []
    current: list[str] = []
    for row in rows:
        candidate = "\n".join(header) + "\n\n" + "\n\n".join(current + [row]) + "\n" + "\n".join(footer)
        if current and _telegram_visible_length(candidate) > 3900:
            chunks.append(current)
            current = [row]
        else:
            current.append(row)
    if current:
        chunks.append(current)

    for index, chunk in enumerate(chunks, start=1):
        chunk_header = list(header)
        if len(chunks) > 1:
            chunk_header[0] += f" · {index}/{len(chunks)}"
        await _send_message(
            "\n".join(chunk_header) + "\n\n" + "\n\n".join(chunk) + "\n" + "\n".join(footer)
        )


def _signal_icon(signal) -> str:
    label = str(signal or "").upper()
    if "GÜÇLÜ AL" in label:
        return "🟢"
    if label == "AL" or "POTANSİYEL" in label:
        return "🟢"
    if label == "TUT" or "İZLE" in label:
        return "🔵"
    if "GÜÇLÜ SAT" in label:
        return "🔴"
    if label == "SAT":
        return "🟠"
    return "⚪"


async def send_main_signal_table(payload: dict, limit: int = 20) -> None:
    """Kategori kotasız ana momentum/trend İlk 20 tablosunu Telegram'a gönder."""
    ranking = (payload or {}).get("ranking") or []
    rows: list[str] = []
    for item in ranking[:limit]:
        code = html.escape(str(item.get("code") or ""))
        url = html.escape(str(item.get("tefas_url") or f"{TEFAS_URL}{code}"), quote=True)
        signal = _short(item.get("signal"), 18)
        icon = _signal_icon(item.get("signal"))
        risk_value = item.get("tefas_risk_value")
        risk_text = f"{risk_value}/7" if risk_value is not None else "?/7"
        rows.append(
            "\n".join([
                f"<b>{int(item.get('rank') or len(rows) + 1):02d}  "
                f"<a href='{url}'>{code}</a></b>  {icon} <b>{signal}</b>  •  Skor <b>{_score(item.get('opportunity_score'))}</b>",
                f"M {_score(item.get('momentum_score'))}  •  T {_score(item.get('trend_score'))}  │  "
                f"1A {_pct(item.get('return_1m'))}  •  3A {_pct(item.get('return_3m'))}",
                f"6A {_pct(item.get('return_6m'))}  •  1Y {_pct(item.get('return_1y'))}  │  "
                f"R {risk_text} {_short(item.get('risk_band'), 10)}",
                f"{_compact_founder(item.get('founder'))}  /  {_short(item.get('category'), 16)}  •  {_tefas_label(item.get('tefas_status'))}",
            ])
        )
    await _send_table(
        "🏆 <b>ANA SİNYAL LİSTESİ</b> · İlk 20\n<i>M: momentum  •  T: trend</i>",
        (payload or {}).get("signal_date"),
        rows,
        "Ana listede gösterilecek fon bulunamadı.",
    )


async def send_emerging_signal_table(payload: dict, limit: int = 20) -> None:
    """Yeni Fon Radarı İlk 20 tablosunu Telegram'a gönder."""
    radar = (payload or {}).get("radar") or (payload or {}).get("emerging_radar") or []
    rows: list[str] = []
    for item in radar[:limit]:
        code = html.escape(str(item.get("code") or ""))
        url = html.escape(str(item.get("tefas_url") or f"{TEFAS_URL}{code}"), quote=True)
        icon = _signal_icon(item.get("signal"))
        risk_value = item.get("tefas_risk_value")
        risk_text = f"{risk_value}/7" if risk_value is not None else "?/7"
        rows.append(
            "\n".join([
                f"<b>{int(item.get('rank') or len(rows) + 1):02d}  "
                f"<a href='{url}'>{code}</a></b>  {icon} <b>{_short(item.get('signal'), 20)}</b>  •  Skor <b>{_score(item.get('score'))}</b>",
                f"{_short(item.get('tier'), 9)} {int(item.get('history_days') or 0)}g  •  "
                f"Güven {_score(item.get('confidence'))}  │  R {risk_text} {_short(item.get('risk_band'), 10)}",
                f"M {_score(item.get('momentum_score'))}  •  T {_score(item.get('trend_score'))}  •  "
                f"A {_score(item.get('flow_score'))}  │  1A {_pct(item.get('return_1m'))}  •  3A {_pct(item.get('return_3m'))}",
                f"{_compact_founder(item.get('founder'))}  /  {_short(item.get('category'), 16)}  •  {_tefas_label(item.get('tefas_status'))}",
            ])
        )
    await _send_table(
        "🌱 <b>YENİ FON RADARI</b> · İlk 20\n<i>M: momentum  •  T: trend  •  A: para akışı</i>",
        (payload or {}).get("signal_date"),
        rows,
        "Radarın sıkı koşullarını geçen yeni fon bulunamadı.",
    )


async def send_latest_signal_tables(limit: int = 20) -> None:
    """Son başarılı haftalık taramadaki ana ve yeni-fon tablolarını gönder."""
    from signals import get_emerging_fund_radar, get_ranked_signals

    await send_main_signal_table(get_ranked_signals(limit=limit), limit=limit)
    await send_emerging_signal_table(get_emerging_fund_radar(limit=limit), limit=limit)


def _caption_links(items: list[dict], limit: int) -> str:
    links = []
    for item in items[:limit]:
        code = html.escape(str(item.get("code") or ""))
        url = html.escape(str(item.get("tefas_url") or f"{TEFAS_URL}{code}"), quote=True)
        links.append(f"<a href='{url}'>{code}</a>")
    return " · ".join(links)


async def send_signal_images(main_payload: dict, emerging_payload: dict, limit: int = 20) -> None:
    """Ana ve yeni fon tablolarını iki yüksek çözünürlüklü PNG olarak gönder."""
    try:
        from signal_cards import render_emerging_card, render_main_card

        main_rows = (main_payload or {}).get("ranking") or []
        emerging_rows = (emerging_payload or {}).get("radar") or []
        main_date = str((main_payload or {}).get("signal_date") or "—")
        emerging_date = str((emerging_payload or {}).get("signal_date") or "—")
        main_caption = (
            f"🏆 <b>ANA SİNYAL LİSTESİ · İLK 20</b>\n"
            f"📅 {html.escape(main_date)}\n"
            f"🔗 {_caption_links(main_rows, limit)}"
        )
        emerging_caption = (
            f"🌱 <b>YENİ FON RADARI · İLK 20</b>\n"
            f"📅 {html.escape(emerging_date)}\n"
            f"🔗 {_caption_links(emerging_rows, limit)}"
        )
        await _send_photo_bytes(
            render_main_card(main_payload, limit=limit),
            f"tefas-ana-{main_date}.png",
            main_caption,
        )
        await _send_photo_bytes(
            render_emerging_card(emerging_payload, limit=limit),
            f"tefas-yeni-{emerging_date}.png",
            emerging_caption,
        )
    except Exception:
        logger.exception("Sinyal görselleri üretilemedi; metin tablosuna dönülüyor")
        await send_main_signal_table(main_payload, limit=limit)
        await send_emerging_signal_table(emerging_payload, limit=limit)


async def send_latest_signal_images(limit: int = 20) -> None:
    from signals import get_emerging_fund_radar, get_ranked_signals

    await send_signal_images(
        get_ranked_signals(limit=limit),
        get_emerging_fund_radar(limit=limit),
        limit=limit,
    )


async def _test_telegram_connection_async() -> str:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError("TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID .env dosyasında tanımlı olmalı")
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    me = await bot.get_me()
    await bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text="✅ TEFAS Alert bağlantı testi başarılı.",
        parse_mode=ParseMode.HTML,
    )
    return me.username or ""


def test_telegram_connection() -> str:
    """Telegram bot ve chat erişimini doğrular; test mesajı gönderir."""
    return asyncio.run(_test_telegram_connection_async())
