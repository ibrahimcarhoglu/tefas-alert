"""High-resolution Telegram cards for legacy notification features."""

from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


WIDTH = 1600
MARGIN = 54
COLORS = {
    "bg": "#07131F", "surface": "#102337", "alt": "#0D1F31", "header": "#153047",
    "grid": "#29445D", "text": "#F4F7FA", "muted": "#9DB0C2", "cyan": "#38BDF8",
    "green": "#22C55E", "blue": "#3B82F6", "orange": "#F59E0B", "red": "#EF4444",
    "purple": "#A78BFA", "gray": "#94A3B8",
}


def _font_path(bold: bool) -> str | None:
    configured = os.getenv("TEFAS_FONT_BOLD_PATH" if bold else "TEFAS_FONT_PATH")
    candidates = [configured] if configured else []
    candidates += [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    return next((path for path in candidates if path and Path(path).exists()), None)


def _font(size: int, bold: bool = False):
    path = _font_path(bold)
    return ImageFont.truetype(path, size) if path else ImageFont.load_default(size=size)


F = {
    "title": _font(48, True), "subtitle": _font(23), "section": _font(27, True),
    "column": _font(21, True), "cell": _font(24), "bold": _font(25, True),
    "small": _font(20), "tiny": _font(18), "kpi": _font(30, True), "footer": _font(20),
}


def _fit(draw: ImageDraw.ImageDraw, value: Any, font, width: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "—")).strip()
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + "…", font=font) > width:
        text = text[:-1]
    return text.rstrip() + "…"


def _text(draw, xy, value, font, color, width):
    draw.text(xy, _fit(draw, value, font, width), font=font, fill=color)


def _num(value: Any, digits: int = 0) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any, digits: int = 1) -> str:
    try:
        return f"{float(value):+.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def _amount(value: Any) -> str:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return "—"
    if abs(amount) >= 1_000_000_000:
        return f"{amount / 1_000_000_000:+.2f} Mr"
    if abs(amount) >= 1_000_000:
        return f"{amount / 1_000_000:+.1f} Mn"
    return f"{amount:+,.0f}"


def _platform(value: Any) -> tuple[str, str]:
    status = str(value or "").upper()
    if "BEFAS" in status:
        return "BEFAS", COLORS["purple"]
    if "GÖRMÜYOR" in status or "KAPALI" in status or "DIŞI" in status:
        return "DIŞARIDA", COLORS["gray"]
    if "GÖRÜYOR" in status or "AÇIK" in status:
        return "TEFAS", COLORS["green"]
    return "BELİRSİZ", COLORS["gray"]


def _base(title: str, subtitle: str, date_text: str, height: int):
    image = Image.new("RGB", (WIDTH, height), COLORS["bg"])
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((MARGIN, MARGIN, WIDTH - MARGIN, height - MARGIN), radius=30, fill=COLORS["surface"], outline=COLORS["grid"], width=2)
    draw.ellipse((MARGIN + 34, MARGIN + 34, MARGIN + 94, MARGIN + 94), fill=COLORS["cyan"])
    draw.text((MARGIN + 51, MARGIN + 43), "T", font=_font(35, True), fill=COLORS["bg"])
    draw.text((MARGIN + 118, MARGIN + 27), title, font=F["title"], fill=COLORS["text"])
    draw.text((MARGIN + 120, MARGIN + 91), subtitle, font=F["subtitle"], fill=COLORS["muted"])
    date_width = int(draw.textlength(date_text, font=F["subtitle"])) + 42
    draw.rounded_rectangle((WIDTH - MARGIN - date_width, MARGIN + 38, WIDTH - MARGIN - 26, MARGIN + 88), radius=18, fill=COLORS["header"])
    draw.text((WIDTH - MARGIN - date_width + 20, MARGIN + 49), date_text, font=F["subtitle"], fill=COLORS["cyan"])
    return image, draw


def _footer(image: Image.Image, draw: ImageDraw.ImageDraw, text: str):
    y = image.height - MARGIN - 55
    draw.line((MARGIN + 26, y - 18, WIDTH - MARGIN - 26, y - 18), fill=COLORS["grid"])
    draw.text((MARGIN + 32, y), "Model çıktısıdır; kişiye özel yatırım tavsiyesi değildir.", font=F["footer"], fill=COLORS["muted"])
    width = int(draw.textlength(text, font=F["footer"]))
    draw.text((WIDTH - MARGIN - width - 30, y), text, font=F["footer"], fill=COLORS["muted"])


def _save(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def _row(draw: ImageDraw.ImageDraw, y: int, index: int, height: int = 84):
    draw.rectangle((MARGIN + 1, y, WIDTH - MARGIN - 1, y + height), fill=COLORS["alt"] if index % 2 else COLORS["surface"])
    draw.line((MARGIN + 26, y + height, WIDTH - MARGIN - 26, y + height), fill=COLORS["grid"])


def render_market_pulse_card(payload: dict[str, Any], limit: int = 5) -> bytes:
    inflows = list(payload.get("top_inflows") or [])[:limit]
    outflows = list(payload.get("top_outflows") or [])[:limit]
    height = 54 + 250 + 108 + 100 + len(inflows) * 84 + 100 + len(outflows) * 84 + 100
    image, draw = _base("TEFAS GÜNLÜK PİYASA NABZI", "PPF hariç  •  Mutlak ve fon büyüklüğüne göre normalize para akışı", str(payload.get("date") or "—"), height)
    x0 = MARGIN + 28
    y = MARGIN + 165
    kpis = [
        ("TOPLAM GİRİŞ", _amount(payload.get("gross_inflow")), COLORS["green"]),
        ("TOPLAM ÇIKIŞ", _amount(payload.get("gross_outflow")), COLORS["red"]),
        ("GERÇEK NET", _amount(payload.get("net_flow")), COLORS["cyan"]),
        ("FON EVRENİ", str(payload.get("universe_count") or 0), COLORS["purple"]),
    ]
    card_w = 342
    for index, (label, value, color) in enumerate(kpis):
        x = x0 + index * (card_w + 20)
        draw.rounded_rectangle((x, y, x + card_w, y + 88), radius=18, fill=COLORS["header"])
        draw.text((x + 20, y + 14), label, font=F["tiny"], fill=COLORS["muted"])
        draw.text((x + 20, y + 44), value, font=F["kpi"], fill=color)
    y += 112

    def section(title: str, rows: list[dict[str, Any]], color: str, direction: str):
        nonlocal y
        draw.rectangle((MARGIN + 1, y, WIDTH - MARGIN - 1, y + 100), fill=COLORS["header"])
        draw.text((x0, y + 12), title, font=F["section"], fill=color)
        headers = [("FON", x0 + 52), ("AKIŞ", 455), ("AUM%", 615), ("YAT.%", 730), ("1G", 845), ("M/T/A", 950), ("DEĞERLENDİRME", 1110)]
        for label, x in headers:
            draw.text((x, y + 66), label, font=F["column"], fill=COLORS["muted"])
        y += 100
        for index, item in enumerate(rows):
            _row(draw, y, index)
            baseline = y + 26
            draw.text((x0, baseline), f"{index + 1:02d}", font=F["cell"], fill=COLORS["muted"])
            draw.text((x0 + 52, baseline), str(item.get("code") or ""), font=F["bold"], fill=COLORS["cyan"])
            platform, platform_color = _platform(item.get("tefas_status"))
            draw.text((x0 + 126, baseline + 3), platform, font=F["tiny"], fill=platform_color)
            draw.text((455, baseline), _amount(item.get("net_flow")), font=F["bold"], fill=color)
            draw.text((615, baseline), _pct(item.get("flow_aum_pct"), 2), font=F["small"], fill=color)
            draw.text((730, baseline), _pct(item.get("investor_change_pct"), 1), font=F["small"], fill=COLORS["text"])
            daily = float(item.get("pct_change") or 0)
            draw.text((845, baseline), _pct(daily, 1), font=F["small"], fill=COLORS["green"] if daily >= 0 else COLORS["red"])
            mta = f"{_num(item.get('momentum_score'))}/{_num(item.get('trend_score'))}/{_num(item.get('flow_score'))}"
            draw.text((950, baseline), mta, font=F["small"], fill=COLORS["text"])
            label_color = COLORS["green"] if direction == "in" and "TEYİTLİ" in str(item.get("flow_label")) else COLORS["orange"] if direction == "out" else COLORS["text"]
            _text(draw, (1110, baseline), item.get("flow_label"), F["small"], label_color, 285)
            y += 84

    section("EN GÜÇLÜ PARA GİRİŞLERİ", inflows, COLORS["green"], "in")
    section("EN GÜÇLÜ PARA ÇIKIŞLARI", outflows, COLORS["red"], "out")
    _footer(image, draw, f"Veri tarihi: {payload.get('date') or '—'}")
    return _save(image)


def render_performance_card(payload: dict[str, Any], limit: int = 10) -> bytes:
    rows = list(payload.get("leaders") or [])[:limit]
    height = 54 + 190 + 64 + max(1, len(rows)) * 96 + 105
    image, draw = _base("GETİRİ VE DEVAMLILIK", "Günlük yükselişi momentum, trend ve para akışıyla doğrulayan ilk 10", str(payload.get("date") or "—"), height)
    x0, y = MARGIN + 28, MARGIN + 170
    draw.rectangle((MARGIN + 1, y, WIDTH - MARGIN - 1, y + 64), fill=COLORS["header"])
    columns = [("#", x0), ("FON", x0 + 54), ("DURUM", x0 + 150), ("SKOR", x0 + 390), ("1G", x0 + 480), ("3G", x0 + 585), ("1H", x0 + 690), ("1A", x0 + 795), ("M/T/A", x0 + 910), ("AKIŞ", x0 + 1060), ("PLATFORM", x0 + 1220)]
    for label, x in columns:
        draw.text((x, y + 20), label, font=F["column"], fill=COLORS["muted"])
    y += 64
    if not rows:
        draw.text((x0 + 20, y + 30), "Gösterilecek doğrulanmış performans kaydı bulunamadı.", font=F["cell"], fill=COLORS["muted"])
    label_colors = {"DEVAM EDEN MOMENTUM": COLORS["green"], "TEYİTSİZ SIÇRAMA": COLORS["orange"], "KÂR SATIŞI RİSKİ": COLORS["red"], "TEFAS DIŞI": COLORS["gray"]}
    for index, item in enumerate(rows):
        _row(draw, y, index, 96)
        baseline = y + 32
        draw.text((x0, baseline), f"{index + 1:02d}", font=F["cell"], fill=COLORS["muted"])
        draw.text((x0 + 54, baseline), str(item.get("code") or ""), font=F["bold"], fill=COLORS["cyan"])
        label = str(item.get("performance_label") or "—")
        label_display = {"DEVAM EDEN MOMENTUM": "DEVAM EDEN MOM.", "GÜÇLÜ PERFORMANS": "GÜÇLÜ PERFORM."}.get(label, label)
        _text(draw, (x0 + 150, baseline), label_display, F["small"], label_colors.get(label, COLORS["blue"]), 225)
        draw.text((x0 + 390, baseline), _num(item.get("continuation_score"), 1), font=F["bold"], fill=COLORS["text"])
        for field, x in (("return_1d", x0 + 480), ("return_3d", x0 + 585), ("return_1w", x0 + 690), ("return_1m_display", x0 + 795)):
            value = float(item.get(field) or 0)
            draw.text((x, baseline), _pct(value), font=F["small"], fill=COLORS["green"] if value >= 0 else COLORS["red"])
        draw.text((x0 + 910, baseline), f"{_num(item.get('momentum_score'))}/{_num(item.get('trend_score'))}/{_num(item.get('flow_score'))}", font=F["small"], fill=COLORS["text"])
        draw.text((x0 + 1060, baseline), _amount(item.get("net_flow")), font=F["small"], fill=COLORS["green"] if float(item.get("net_flow") or 0) >= 0 else COLORS["red"])
        platform, color = _platform(item.get("tefas_status"))
        draw.text((x0 + 1220, baseline), platform, font=F["small"], fill=color)
        y += 96
    _footer(image, draw, f"Veri tarihi: {payload.get('date') or '—'}")
    return _save(image)


def render_anomaly_card(payload: dict[str, Any], limit: int = 10) -> bytes:
    rows = list(payload.get("anomalies") or [])[:limit]
    height = 54 + 190 + 64 + max(1, len(rows)) * 108 + 105
    image, draw = _base("AKILLI ANOMALİ ALARMI", "PPF hariç  •  Aynı fondaki hareketler gruplanmış ve önem sırasına alınmıştır", str(payload.get("date") or "—"), height)
    x0, y = MARGIN + 28, MARGIN + 170
    draw.rectangle((MARGIN + 1, y, WIDTH - MARGIN - 1, y + 64), fill=COLORS["header"])
    for label, x in [("#", x0), ("FON", x0 + 54), ("ÖNEM", x0 + 150), ("ANOMALİLER", x0 + 270), ("MAX Z", x0 + 720), ("M/T/A", x0 + 835), ("1G", x0 + 990), ("PLATFORM / DETAY", x0 + 1100)]:
        draw.text((x, y + 20), label, font=F["column"], fill=COLORS["muted"])
    y += 64
    if not rows:
        draw.text((x0 + 20, y + 30), "Bugün eşikleri aşan anomali bulunmadı.", font=F["cell"], fill=COLORS["muted"])
    severity = {3: ("KRİTİK", COLORS["red"]), 2: ("YÜKSEK", COLORS["orange"]), 1: ("ORTA", COLORS["gray"])}
    for index, item in enumerate(rows):
        _row(draw, y, index, 108)
        baseline = y + 25
        draw.text((x0, baseline), f"{index + 1:02d}", font=F["cell"], fill=COLORS["muted"])
        draw.text((x0 + 54, baseline), str(item.get("code") or ""), font=F["bold"], fill=COLORS["cyan"])
        severity_text, severity_color = severity.get(int(item.get("severity_rank") or 1), severity[1])
        draw.text((x0 + 150, baseline), severity_text, font=F["small"], fill=severity_color)
        _text(draw, (x0 + 270, baseline), item.get("alert_summary"), F["small"], COLORS["text"], 425)
        draw.text((x0 + 720, baseline), _num(item.get("max_zscore"), 1), font=F["bold"], fill=severity_color)
        draw.text((x0 + 835, baseline), f"{_num(item.get('momentum_score'))}/{_num(item.get('trend_score'))}/{_num(item.get('flow_score'))}", font=F["small"], fill=COLORS["text"])
        draw.text((x0 + 990, baseline), _pct(item.get("pct_change")), font=F["small"], fill=COLORS["text"])
        platform, platform_color = _platform(item.get("tefas_status"))
        draw.text((x0 + 1100, baseline), platform, font=F["small"], fill=platform_color)
        details = " | ".join(str(alert.get("detail") or "") for alert in item.get("alerts") or [])
        _text(draw, (x0 + 270, y + 64), details, F["tiny"], COLORS["muted"], 1130)
        y += 108
    _footer(image, draw, f"Veri tarihi: {payload.get('date') or '—'}")
    return _save(image)


def render_rotation_card(payload: dict[str, Any], limit: int = 20) -> bytes:
    rows = list(payload.get("changes") or [])[:limit]
    date_text = str(payload.get("signal_date") or "—")
    height = 54 + 190 + 64 + max(1, len(rows)) * 98 + 105
    image, draw = _base("HAFTALIK ROTASYON DEĞİŞİMİ", "Yalnızca durumu değişen fonlar  •  Önceki → yeni teknik karar", date_text, height)
    x0, y = MARGIN + 28, MARGIN + 170
    draw.rectangle((MARGIN + 1, y, WIDTH - MARGIN - 1, y + 64), fill=COLORS["header"])
    columns = [("#", x0), ("FON", x0 + 54), ("DEĞİŞİM", x0 + 145), ("SKOR", x0 + 390), ("M/T/A", x0 + 485), ("1A / 3A", x0 + 640), ("RİSK", x0 + 825), ("HEDEF", x0 + 925), ("VALÖR", x0 + 1035), ("PLATFORM / GEREKÇE", x0 + 1150)]
    for label, x in columns:
        draw.text((x, y + 20), label, font=F["column"], fill=COLORS["muted"])
    y += 64
    if not rows:
        draw.text((x0 + 20, y + 30), "Bu hafta durum değiştiren fon bulunmadı.", font=F["cell"], fill=COLORS["muted"])
    status_short = {"ALIM_ADAYI": "ALIM", "CIKIS_ADAYI": "ÇIKIŞ", "TUT": "TUT", "YENİ": "YENİ"}
    for index, item in enumerate(rows):
        _row(draw, y, index, 98)
        baseline = y + 25
        draw.text((x0, baseline), f"{index + 1:02d}", font=F["cell"], fill=COLORS["muted"])
        draw.text((x0 + 54, baseline), str(item.get("code") or ""), font=F["bold"], fill=COLORS["cyan"])
        previous = status_short.get(str(item.get("previous_status")), str(item.get("previous_status") or "—"))
        current = status_short.get(str(item.get("current_status")), str(item.get("current_status") or "—"))
        current_color = COLORS["green"] if current == "ALIM" else COLORS["red"] if current == "ÇIKIŞ" else COLORS["blue"]
        draw.text((x0 + 145, baseline), f"{previous} → {current}", font=F["small"], fill=current_color)
        draw.text((x0 + 390, baseline), _num(item.get("score"), 1), font=F["bold"], fill=COLORS["text"])
        draw.text((x0 + 485, baseline), f"{_num(item.get('momentum_score'))}/{_num(item.get('trend_score'))}/{_num(item.get('flow_score'))}", font=F["small"], fill=COLORS["text"])
        draw.text((x0 + 640, baseline), f"{_pct(float(item.get('return_1m') or 0) * 100)} / {_pct(float(item.get('return_3m') or 0) * 100)}", font=F["small"], fill=COLORS["text"])
        risk = item.get("tefas_risk_value")
        draw.text((x0 + 825, baseline), f"{risk}/7" if risk else "?/7", font=F["small"], fill=COLORS["text"])
        draw.text((x0 + 925, baseline), _pct(float(item.get("target_weight") or 0) * 100, 0), font=F["small"], fill=COLORS["text"])
        draw.text((x0 + 1035, baseline), f"A{int(item.get('alis_valor') or 0)}/S{int(item.get('satis_valor') or 0)}", font=F["small"], fill=COLORS["text"])
        platform, platform_color = _platform(item.get("tefas_status"))
        draw.text((x0 + 1150, baseline), platform, font=F["small"], fill=platform_color)
        reasons = item.get("reasons") or []
        _text(draw, (x0 + 145, y + 62), reasons[0] if reasons else "Model durum değişimi", F["tiny"], COLORS["muted"], 1250)
        y += 98
    _footer(image, draw, f"Sinyal tarihi: {date_text}")
    return _save(image)
