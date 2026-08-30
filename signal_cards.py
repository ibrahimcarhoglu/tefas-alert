"""Render TEFAS signal tables as high-resolution Telegram PNG cards."""

from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1600
MARGIN = 54
HEADER_HEIGHT = 210
COLUMN_HEIGHT = 68
ROW_HEIGHT = 106
FOOTER_HEIGHT = 92

COLORS = {
    "background": "#07131F", "surface": "#102337", "surface_alt": "#0D1F31",
    "header": "#153047", "grid": "#29445D", "text": "#F4F7FA",
    "muted": "#9DB0C2", "cyan": "#38BDF8", "green": "#22C55E",
    "blue": "#3B82F6", "orange": "#F59E0B", "red": "#EF4444",
    "gray": "#94A3B8", "purple": "#A78BFA",
}


def _font_candidates(bold: bool) -> list[str]:
    configured = os.getenv("TEFAS_FONT_BOLD_PATH" if bold else "TEFAS_FONT_PATH")
    candidates = [configured] if configured else []
    candidates.extend([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
    ])
    return [path for path in candidates if path]


def _font(size: int, bold: bool = False):
    for candidate in _font_candidates(bold):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default(size=size)


FONTS = {
    "title": _font(50, True), "subtitle": _font(25), "column": _font(24, True),
    "cell": _font(26), "cell_bold": _font(27, True), "small": _font(21),
    "tiny": _font(19), "footer": _font(21),
}


def _num(value: Any, digits: int = 0) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return f"{float(value) * 100:+.1f}%"
    except (TypeError, ValueError):
        return "—"


def _risk(item: dict[str, Any]) -> str:
    value = item.get("tefas_risk_value")
    band = str(item.get("risk_band") or "").upper()
    value_text = f"{value}/7" if value is not None else "?/7"
    band = {
        "ÇOK YÜKSEK": "Ç.YÜK.", "YÜKSEK": "YÜK.", "DÜŞÜK": "DÜŞ.",
    }.get(band, band)
    return f"{value_text} {band}" if band and band != "BİLİNMİYOR" else value_text


def _compact_founder(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "BİLİNMİYOR")).strip()
    for suffix in (
        " PORTFÖY YÖNETİMİ A.Ş.", " EMEKLİLİK VE HAYAT A.Ş.",
        " HAYAT VE EMEKLİLİK A.Ş.", " EMEKLİLİK A.Ş.",
    ):
        if text.upper().endswith(suffix):
            return text[: -len(suffix)].strip()
    return text


def _platform(value: Any) -> tuple[str, str]:
    status = str(value or "").upper()
    if "BEFAS" in status:
        return "BEFAS", COLORS["purple"]
    if "KAPALI" in status or "DIŞI" in status or "GÖRMÜYOR" in status:
        return "DIŞARIDA", COLORS["gray"]
    if "AÇIK" in status or "ACIK" in status or "GÖRÜYOR" in status:
        return "TEFAS", COLORS["green"]
    return "BELİRSİZ", COLORS["gray"]


def _signal_color(value: Any) -> str:
    signal = str(value or "").upper()
    if "GÜÇLÜ AL" in signal or "POTANSİYEL" in signal or signal == "AL":
        return COLORS["green"]
    if "İZLE" in signal or signal == "TUT":
        return COLORS["blue"]
    if "GÜÇLÜ SAT" in signal:
        return COLORS["red"]
    if signal == "SAT":
        return COLORS["orange"]
    return COLORS["gray"]


def _social_label_color(value: Any) -> str:
    label = str(value or "").upper()
    if "TEYİTLİ" in label:
        return COLORS["green"]
    if "SESSİZ" in label:
        return COLORS["purple"]
    if "ERKEN" in label:
        return COLORS["blue"]
    if "HYPE" in label:
        return COLORS["orange"]
    return COLORS["gray"]


def _social_label(value: Any) -> str:
    return {
        "TEYİTLİ İLGİ": "TEYİTLİ İLGİ",
        "SESSİZ YÜKSELİŞ": "SESSİZ YÜK.",
        "ERKEN RADAR": "ERKEN RADAR",
        "AŞIRI HYPE": "AŞIRI HYPE",
    }.get(str(value or "").upper(), str(value or "İZLE"))


def _fit(draw: ImageDraw.ImageDraw, text: Any, font, max_width: int) -> str:
    value = re.sub(r"\s+", " ", str(text or "—")).strip()
    if draw.textlength(value, font=font) <= max_width:
        return value
    while value and draw.textlength(value + "…", font=font) > max_width:
        value = value[:-1]
    return value.rstrip() + "…"


def _draw_text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: Any, font, fill: str, width: int) -> None:
    draw.text(xy, _fit(draw, text, font, width), font=font, fill=fill)


def _base_image(title: str, subtitle: str, date_text: str, row_count: int):
    height = MARGIN + HEADER_HEIGHT + COLUMN_HEIGHT + row_count * ROW_HEIGHT + FOOTER_HEIGHT + MARGIN
    image = Image.new("RGB", (WIDTH, height), COLORS["background"])
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (MARGIN, MARGIN, WIDTH - MARGIN, height - MARGIN), radius=30,
        fill=COLORS["surface"], outline=COLORS["grid"], width=2,
    )
    draw.ellipse((MARGIN + 34, MARGIN + 34, MARGIN + 94, MARGIN + 94), fill=COLORS["cyan"])
    draw.text((MARGIN + 51, MARGIN + 43), "T", font=_font(35, True), fill=COLORS["background"])
    draw.text((MARGIN + 118, MARGIN + 28), title, font=FONTS["title"], fill=COLORS["text"])
    draw.text((MARGIN + 120, MARGIN + 92), subtitle, font=FONTS["subtitle"], fill=COLORS["muted"])
    date_width = int(draw.textlength(date_text, font=FONTS["subtitle"])) + 42
    draw.rounded_rectangle(
        (WIDTH - MARGIN - date_width, MARGIN + 38, WIDTH - MARGIN - 26, MARGIN + 88),
        radius=18, fill=COLORS["header"],
    )
    draw.text((WIDTH - MARGIN - date_width + 20, MARGIN + 49), date_text, font=FONTS["subtitle"], fill=COLORS["cyan"])
    return image, draw


def _column_header(draw: ImageDraw.ImageDraw, y: int, columns: list[tuple[str, int, int]]) -> None:
    draw.rectangle((MARGIN + 1, y, WIDTH - MARGIN - 1, y + COLUMN_HEIGHT), fill=COLORS["header"])
    for label, x, width in columns:
        _draw_text(draw, (x, y + 20), label, FONTS["column"], COLORS["muted"], width)


def _row_background(draw: ImageDraw.ImageDraw, y: int, index: int) -> None:
    fill = COLORS["surface_alt"] if index % 2 else COLORS["surface"]
    draw.rectangle((MARGIN + 1, y, WIDTH - MARGIN - 1, y + ROW_HEIGHT), fill=fill)
    draw.line((MARGIN + 26, y + ROW_HEIGHT, WIDTH - MARGIN - 26, y + ROW_HEIGHT), fill=COLORS["grid"], width=1)


def _footer(draw: ImageDraw.ImageDraw, image: Image.Image, date_text: str) -> None:
    y = image.height - MARGIN - FOOTER_HEIGHT + 31
    draw.text((MARGIN + 32, y), "Model çıktısıdır; kişiye özel yatırım tavsiyesi değildir.", font=FONTS["footer"], fill=COLORS["muted"])
    stamp = f"Veri tarihi: {date_text}"
    stamp_width = int(draw.textlength(stamp, font=FONTS["footer"]))
    draw.text((WIDTH - MARGIN - stamp_width - 30, y), stamp, font=FONTS["footer"], fill=COLORS["muted"])


def _save(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def render_main_card(payload: dict[str, Any], limit: int = 20) -> bytes:
    rows = list((payload or {}).get("ranking") or [])[:limit]
    date_text = str((payload or {}).get("signal_date") or "—")
    image, draw = _base_image(
        "ANA SİNYAL LİSTESİ", "Kategori kotası yok  •  Momentum + trend + para akışı  •  İlk 20",
        date_text, len(rows),
    )
    x0 = MARGIN + 26
    columns = [
        ("#", x0, 42), ("FON", x0 + 52, 82), ("SİNYAL", x0 + 145, 165),
        ("SKOR", x0 + 320, 84), ("M", x0 + 414, 68), ("T", x0 + 492, 68),
        ("1 AY", x0 + 570, 105), ("3 AY", x0 + 685, 105), ("6 AY", x0 + 800, 105),
        ("1 YIL", x0 + 915, 112), ("RİSK", x0 + 1037, 175), ("KURUCU / TİP", x0 + 1222, 215),
    ]
    y = MARGIN + HEADER_HEIGHT
    _column_header(draw, y, columns)
    y += COLUMN_HEIGHT
    for index, item in enumerate(rows):
        _row_background(draw, y, index)
        baseline = y + 31
        draw.text((x0, baseline), f"{int(item.get('rank') or index + 1):02d}", font=FONTS["cell"], fill=COLORS["muted"])
        draw.text((x0 + 52, baseline), str(item.get("code") or ""), font=FONTS["cell_bold"], fill=COLORS["cyan"])
        signal = str(item.get("signal") or "—")
        draw.ellipse((x0 + 145, baseline + 6, x0 + 163, baseline + 24), fill=_signal_color(signal))
        _draw_text(draw, (x0 + 172, baseline), signal, FONTS["small"], COLORS["text"], 132)
        draw.text((x0 + 320, baseline), _num(item.get("opportunity_score"), 1), font=FONTS["cell_bold"], fill=COLORS["text"])
        draw.text((x0 + 414, baseline), _num(item.get("momentum_score"), 0), font=FONTS["cell"], fill=COLORS["text"])
        draw.text((x0 + 492, baseline), _num(item.get("trend_score"), 0), font=FONTS["cell"], fill=COLORS["text"])
        for value, x in ((item.get("return_1m"), x0 + 570), (item.get("return_3m"), x0 + 685),
                         (item.get("return_6m"), x0 + 800), (item.get("return_1y"), x0 + 915)):
            color = COLORS["green"] if value is not None and float(value) >= 0 else COLORS["red"]
            draw.text((x, baseline), _pct(value), font=FONTS["small"], fill=color)
        _draw_text(draw, (x0 + 1037, baseline), _risk(item), FONTS["small"], COLORS["text"], 170)
        founder = _compact_founder(item.get("founder"))
        category = str(item.get("category") or "BİLİNMİYOR")
        platform, platform_color = _platform(item.get("tefas_status"))
        _draw_text(draw, (x0 + 1222, y + 18), founder, FONTS["small"], COLORS["text"], 210)
        _draw_text(draw, (x0 + 1222, y + 55), f"{category}  •  {platform}", FONTS["small"], platform_color, 210)
        y += ROW_HEIGHT
    _footer(draw, image, date_text)
    return _save(image)


def render_emerging_card(payload: dict[str, Any], limit: int = 20) -> bytes:
    rows = list((payload or {}).get("radar") or (payload or {}).get("emerging_radar") or [])[:limit]
    date_text = str((payload or {}).get("signal_date") or "—")
    image, draw = _base_image(
        "YENİ FON RADARI", "64–251 günlük fonlar  •  Erken momentum ve trend takibi  •  İlk 20",
        date_text, len(rows),
    )
    x0 = MARGIN + 26
    columns = [
        ("#", x0, 42), ("FON", x0 + 52, 82), ("SİNYAL", x0 + 145, 180),
        ("SKOR", x0 + 345, 80), ("EVRE / GÜN", x0 + 435, 160), ("GÜV.", x0 + 605, 80),
        ("M / T / AKIŞ", x0 + 695, 140), ("1 AY / 3 AY", x0 + 845, 170),
        ("RİSK", x0 + 1025, 120), ("KURUCU / TİP", x0 + 1155, 282),
    ]
    y = MARGIN + HEADER_HEIGHT
    _column_header(draw, y, columns)
    y += COLUMN_HEIGHT
    for index, item in enumerate(rows):
        _row_background(draw, y, index)
        baseline = y + 31
        draw.text((x0, baseline), f"{int(item.get('rank') or index + 1):02d}", font=FONTS["cell"], fill=COLORS["muted"])
        draw.text((x0 + 52, baseline), str(item.get("code") or ""), font=FONTS["cell_bold"], fill=COLORS["cyan"])
        signal = str(item.get("signal") or "—")
        draw.ellipse((x0 + 145, baseline + 6, x0 + 163, baseline + 24), fill=_signal_color(signal))
        _draw_text(draw, (x0 + 172, baseline), signal, FONTS["small"], COLORS["text"], 166)
        draw.text((x0 + 345, baseline), _num(item.get("score"), 1), font=FONTS["cell_bold"], fill=COLORS["text"])
        _draw_text(draw, (x0 + 435, baseline), f"{item.get('tier') or '—'} / {int(item.get('history_days') or 0)}g", FONTS["tiny"], COLORS["text"], 156)
        draw.text((x0 + 605, baseline), _num(item.get("confidence"), 0), font=FONTS["cell"], fill=COLORS["text"])
        mta = f"{_num(item.get('momentum_score'), 0)} / {_num(item.get('trend_score'), 0)} / {_num(item.get('flow_score'), 0)}"
        _draw_text(draw, (x0 + 695, baseline), mta, FONTS["tiny"], COLORS["text"], 136)
        returns = f"{_pct(item.get('return_1m'))} / {_pct(item.get('return_3m'))}"
        return_color = COLORS["green"] if float(item.get("return_1m") or 0) >= 0 else COLORS["red"]
        _draw_text(draw, (x0 + 845, baseline), returns, FONTS["tiny"], return_color, 166)
        _draw_text(draw, (x0 + 1025, baseline), _risk(item), FONTS["small"], COLORS["text"], 116)
        founder = _compact_founder(item.get("founder"))
        category = str(item.get("category") or "BİLİNMİYOR")
        platform, platform_color = _platform(item.get("tefas_status"))
        _draw_text(draw, (x0 + 1155, y + 18), founder, FONTS["small"], COLORS["text"], 278)
        _draw_text(draw, (x0 + 1155, y + 55), f"{category} • {platform}", FONTS["small"], platform_color, 278)
        y += ROW_HEIGHT
    _footer(draw, image, date_text)
    return _save(image)


def render_social_momentum_card(payload: dict[str, Any], limit: int = 10) -> bytes:
    rows = list((payload or {}).get("radar") or [])[:limit]
    scan_date = str((payload or {}).get("scan_date") or "—")
    as_of_date = str((payload or {}).get("as_of_date") or "—")
    source_available = bool((payload or {}).get("source_available"))
    subtitle = (
        "X ilgisi + teknik trend + TEFAS akışı  •  Ana AL/TUT/SAT skorundan bağımsız"
        if source_available else
        "X veri kaynağına erişilemedi  •  Ana AL/TUT/SAT skoru etkilenmedi"
    )
    image, draw = _base_image("SOSYAL MOMENTUM RADARI", subtitle, scan_date, max(1, len(rows)))
    x0 = MARGIN + 26
    columns = [
        ("#", x0, 42), ("FON", x0 + 52, 82), ("RADAR", x0 + 145, 205),
        ("SKOR", x0 + 360, 72), ("HIZ", x0 + 442, 72),
        ("X / KAY.", x0 + 524, 120), ("DUYGU", x0 + 654, 86),
        ("TEYİT", x0 + 750, 82), ("TEK. / AKIŞ", x0 + 842, 146),
        ("YAT.%", x0 + 998, 104), ("NEDEN", x0 + 1112, 325),
    ]
    y = MARGIN + HEADER_HEIGHT
    _column_header(draw, y, columns)
    y += COLUMN_HEIGHT
    if not rows:
        message = "Bugün gösterilecek doğrulanmış sosyal momentum kaydı bulunamadı."
        draw.text((x0 + 20, y + 30), message, font=FONTS["cell"], fill=COLORS["muted"])
    for index, item in enumerate(rows):
        _row_background(draw, y, index)
        baseline = y + 31
        draw.text((x0, baseline), f"{int(item.get('rank') or index + 1):02d}", font=FONTS["cell"], fill=COLORS["muted"])
        draw.text((x0 + 52, baseline), str(item.get("code") or ""), font=FONTS["cell_bold"], fill=COLORS["cyan"])
        label = str(item.get("label") or "İZLE")
        label_color = _social_label_color(label)
        draw.ellipse((x0 + 145, baseline + 6, x0 + 163, baseline + 24), fill=label_color)
        _draw_text(draw, (x0 + 172, baseline), _social_label(label), FONTS["small"], label_color, 172)
        draw.text((x0 + 360, baseline), _num(item.get("score"), 1), font=FONTS["cell_bold"], fill=COLORS["text"])
        draw.text((x0 + 442, baseline), _num(item.get("acceleration_score"), 0), font=FONTS["cell"], fill=COLORS["text"])
        mentions = int(item.get("mention_count") or 0)
        accounts = int(item.get("unique_accounts") or 0)
        draw.text((x0 + 524, baseline), f"{mentions} / {accounts}", font=FONTS["cell"], fill=COLORS["text"])
        sentiment = float(item.get("sentiment_score") or 0)
        sentiment_color = COLORS["green"] if sentiment >= 60 else COLORS["red"] if sentiment < 40 else COLORS["text"]
        draw.text((x0 + 654, baseline), _num(sentiment, 0), font=FONTS["cell"], fill=sentiment_color)
        draw.text((x0 + 750, baseline), _num(item.get("confirmation_score"), 0), font=FONTS["cell"], fill=COLORS["text"])
        technical_flow = f"{_num(item.get('technical_score'), 0)} / {_num(item.get('flow_score'), 0)}"
        _draw_text(draw, (x0 + 842, baseline), technical_flow, FONTS["small"], COLORS["text"], 140)
        draw.text((x0 + 998, baseline), _pct(item.get("investor_growth")), font=FONTS["small"], fill=COLORS["text"])
        _draw_text(draw, (x0 + 1112, y + 18), item.get("reason"), FONTS["tiny"], COLORS["text"], 320)
        _draw_text(
            draw, (x0 + 1112, y + 55),
            f"{item.get('category') or '—'} • {item.get('tefas_status') or '—'}",
            FONTS["tiny"], COLORS["muted"], 320,
        )
        y += ROW_HEIGHT
    _footer(draw, image, f"TEFAS {as_of_date} • X {scan_date}")
    return _save(image)
