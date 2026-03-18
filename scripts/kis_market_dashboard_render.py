#!/usr/bin/env python3
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent

BASE_WIDTH = 1080
BASE_PADDING = 32
BASE_GAP = 24
BASE_CARD_HEIGHT = 500
BASE_SUMMARY_GAP = 12
BASE_SUMMARY_HEIGHT = 108
BASE_HEADER_HEIGHT = 122
BASE_BOTTOM_PADDING = 32

WIDTH = BASE_WIDTH
PADDING = BASE_PADDING
GAP = BASE_GAP
CARD_HEIGHT = BASE_CARD_HEIGHT
SUMMARY_GAP = BASE_SUMMARY_GAP
SUMMARY_HEIGHT = BASE_SUMMARY_HEIGHT
HEADER_HEIGHT = BASE_HEADER_HEIGHT
BOTTOM_PADDING = BASE_BOTTOM_PADDING


def load_font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/NotoSansGothic-Regular.ttf",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    ]
    if bold:
        candidates.extend([
            "/System/Library/Fonts/Supplemental/HelveticaNeue.ttc",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ])
    candidates.extend([
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ])

    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


OUTPUT_WIDTH = BASE_WIDTH
OUTPUT_HEIGHT = None
RENDER_SCALE = 2.0


def set_fonts(scale):
    global FONT_H1, FONT_SUB, FONT_NAME, FONT_PRICE, FONT_META, FONT_SMALL, FONT_TINY, FONT_AXIS, FONT_TAB
    FONT_H1 = load_font(int(46 * scale), bold=True)
    FONT_SUB = load_font(int(20 * scale))
    FONT_NAME = load_font(int(30 * scale), bold=True)
    FONT_PRICE = load_font(int(54 * scale), bold=True)
    FONT_META = load_font(int(24 * scale), bold=True)
    FONT_SMALL = load_font(int(18 * scale))
    FONT_TINY = load_font(int(18 * scale))
    FONT_AXIS = load_font(int(16 * scale))
    FONT_TAB = load_font(int(20 * scale), bold=True)


def apply_render_settings():
    global WIDTH, PADDING, GAP, CARD_HEIGHT, SUMMARY_GAP, SUMMARY_HEIGHT, HEADER_HEIGHT, BOTTOM_PADDING
    global OUTPUT_WIDTH, OUTPUT_HEIGHT, RENDER_SCALE

    raw_width = os.getenv("KIS_DASHBOARD_WIDTH_PX", str(BASE_WIDTH))
    raw_height = os.getenv("KIS_DASHBOARD_HEIGHT_PX", "")
    raw_render_scale = os.getenv("KIS_DASHBOARD_RENDER_SCALE", "2.0")

    try:
        OUTPUT_WIDTH = max(320, int(raw_width))
    except ValueError:
        OUTPUT_WIDTH = BASE_WIDTH

    try:
        OUTPUT_HEIGHT = max(320, int(raw_height)) if raw_height else None
    except ValueError:
        OUTPUT_HEIGHT = None

    try:
        RENDER_SCALE = max(1.0, min(4.0, float(raw_render_scale)))
    except ValueError:
        RENDER_SCALE = 2.0

    layout_scale = RENDER_SCALE
    WIDTH = int(BASE_WIDTH * layout_scale)
    PADDING = int(BASE_PADDING * layout_scale)
    GAP = int(BASE_GAP * layout_scale)
    CARD_HEIGHT = int(BASE_CARD_HEIGHT * layout_scale)
    SUMMARY_GAP = int(BASE_SUMMARY_GAP * layout_scale)
    SUMMARY_HEIGHT = int(BASE_SUMMARY_HEIGHT * layout_scale)
    HEADER_HEIGHT = int(BASE_HEADER_HEIGHT * layout_scale)
    BOTTOM_PADDING = int(BASE_BOTTOM_PADDING * layout_scale)
    set_fonts(layout_scale)


def json_path():
    return Path(os.getenv("KIS_DASHBOARD_JSON", ROOT / "tmp" / "kis_market_dashboard.json"))


def png_path():
    return Path(os.getenv("KIS_DASHBOARD_PNG", ROOT / "tmp" / "kis_market_dashboard.png"))


def candle_width_scale():
    raw = os.getenv("KIS_DASHBOARD_CANDLE_WIDTH_SCALE", "1.0")
    try:
        value = float(raw)
    except ValueError:
        return 1.0
    return max(0.3, min(2.0, value))


def su(value):
    return int(value * RENDER_SCALE)


def market_palette(market):
    if str(market or "").lower() == "us":
        return {
            "up": "#16a34a",
            "down": "#ef4444",
            "flat": "#64748b",
            "candle_up": "#22c55e",
            "candle_down": "#ef4444",
            "candle_flat": "#b8c2cf",
        }
    return {
        "up": "#ef4444",
        "down": "#3b82f6",
        "flat": "#64748b",
        "candle_up": "#f43f5e",
        "candle_down": "#3b82f6",
        "candle_flat": "#b8c2cf",
    }


def draw_text(draw, xy, text, font, fill):
    draw.text(xy, text, font=font, fill=fill)


def measure(font, text):
    box = font.getbbox(text)
    return box[2] - box[0], box[3] - box[1]


def rounded(draw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_line(draw, points, fill, width):
    if len(points) >= 2:
        draw.line(points, fill=fill, width=width, joint="curve")


def stock_card_layout(cards, start_y):
    layouts = []
    card_width = (WIDTH - (PADDING * 2) - GAP) // 2
    index = 0
    y = start_y
    while index < len(cards):
        remaining = len(cards) - index
        if remaining == 1:
            layouts.append((PADDING, y, WIDTH - PADDING, y + CARD_HEIGHT))
            break
        layouts.append((PADDING, y, PADDING + card_width, y + CARD_HEIGHT))
        layouts.append((PADDING + card_width + GAP, y, WIDTH - PADDING, y + CARD_HEIGHT))
        y += CARD_HEIGHT + GAP
        index += 2
    return layouts


def summary_card_layout(cards, start_y):
    layouts = []
    if not cards:
        return layouts
    cols = len(cards)
    card_width = (WIDTH - (PADDING * 2) - SUMMARY_GAP * (cols - 1)) // cols
    x = PADDING
    for _ in cards:
        layouts.append((x, start_y, x + card_width, start_y + SUMMARY_HEIGHT))
        x += card_width + SUMMARY_GAP
    return layouts


def chart_bounds(box):
    x0, y0, x1, y1 = box
    chart_bottom = y1 - su(70)
    return x0 + su(16), y0 + su(150), x1 - su(16), chart_bottom


def flatten_segments(segments):
    merged = []
    for segment_index, segment in enumerate(segments):
        for point in segment.get("points", []):
            merged.append({
                "session": segment.get("session", ""),
                "color": segment.get("color", "#5ad7ff"),
                "time": point.get("time", ""),
                "time_raw": point.get("time_raw", ""),
                "price": float(point.get("price", 0)),
                "open": float(point.get("open", point.get("price", 0))),
                "high": float(point.get("high", point.get("price", 0))),
                "low": float(point.get("low", point.get("price", 0))),
                "close": float(point.get("close", point.get("price", 0))),
                "volume": int(point.get("volume", 0)),
            })
    return merged


def format_axis_value(value):
    rounded = round(value)
    if abs(value - rounded) < 1e-6:
        return f"{int(rounded):,}"
    return f"{value:,.2f}"


def hhmmss_to_minutes(value):
    raw = str(value or "").zfill(6)
    return int(raw[:2]) * 60 + int(raw[2:4])


def minutes_to_label(value):
    hour = int(value // 60) % 24
    minute = int(value % 60)
    return f"{hour:02d}:{minute:02d}"


def build_axis_marks(all_points):
    minutes = sorted({hhmmss_to_minutes(point["time_raw"]) for point in all_points})
    if len(minutes) <= 4:
        return [(minutes_to_label(value), value) for value in minutes]

    indices = sorted({0, len(minutes) // 3, (len(minutes) * 2) // 3, len(minutes) - 1})
    return [(minutes_to_label(minutes[index]), minutes[index]) for index in indices]


def candle_direction(point, previous_close, market):
    if previous_close is not None:
        if point["close"] > previous_close:
            return "up"
        if point["close"] < previous_close:
            return "down"
        return "flat"
    if point["close"] > point["open"]:
        return "up"
    if point["close"] < point["open"]:
        return "down"
    return "flat"


def draw_chart(draw, box, chart, palette, market):
    cx0, cy0, cx1, cy1 = chart_bounds(box)
    rounded(draw, (cx0, cy0, cx1, cy1), su(20), fill="#ffffff", outline="#e5ebf2")
    inner = (cx0 + su(12), cy0 + su(12), cx1 - su(12), cy1 - su(12))
    rounded(draw, inner, su(14), fill="#ffffff")

    segments = [segment for segment in chart.get("segments", []) if segment.get("points")]
    if not segments:
        draw_text(draw, (cx0 + su(18), cy0 + su(18)), "No intraday data from KIS", FONT_SMALL, "#c2410c")
        return {"highest": None, "lowest": None}

    all_points = flatten_segments(segments)
    prices = [value for point in all_points for value in (point["low"], point["high"])]
    volumes = [point["volume"] for point in all_points]
    min_price = min(prices)
    max_price = max(prices)
    price_span = max(1, max_price - min_price)
    max_volume = max(volumes) if volumes else 1
    plot_x0, plot_y0, plot_x1, plot_y1 = inner[0] + su(18), inner[1] + su(18), inner[2] - su(18), inner[3] - su(74)
    plot_height = plot_y1 - plot_y0
    plot_width = plot_x1 - plot_x0
    volume_y0 = plot_y1 + su(24)
    volume_y1 = inner[3] - su(20)
    volume_height = max(su(16), volume_y1 - volume_y0)

    draw.line((plot_x0, volume_y0 - su(14), plot_x1, volume_y0 - su(14)), fill="#eef2f6", width=max(1, su(2)))

    for ratio in (0.0, 0.5, 1.0):
        y = plot_y0 + ratio * plot_height
        draw.line((plot_x0, y, plot_x1, y), fill="#f0f3f7", width=1)

    min_minute = min(hhmmss_to_minutes(point["time_raw"]) for point in all_points)
    max_minute = max(hhmmss_to_minutes(point["time_raw"]) for point in all_points)
    minute_span = max(1, max_minute - min_minute)
    dividers = []
    base_candle_width = max(4, int(plot_width / max(96, minute_span / 5)))
    candle_width = max(2, int(base_candle_width * candle_width_scale()))
    highest = None
    lowest = None
    converted_segments = []

    for segment_index, segment in enumerate(segments):
        seg_points = segment["points"]
        converted = []
        previous_close = None
        for point in seg_points:
            minute = hhmmss_to_minutes(point["time_raw"])
            x = plot_x0 + (plot_width * (minute - min_minute) / minute_span)
            y_open = plot_y0 + ((max_price - point["open"]) / price_span) * plot_height
            y_high = plot_y0 + ((max_price - point["high"]) / price_span) * plot_height
            y_low = plot_y0 + ((max_price - point["low"]) / price_span) * plot_height
            y_close = plot_y0 + ((max_price - point["close"]) / price_span) * plot_height
            converted.append({
                "x": x,
                "open": y_open,
                "high": y_high,
                "low": y_low,
                "close": y_close,
                "raw_high": point["high"],
                "raw_low": point["low"],
                "raw_close": point["close"],
                "direction": candle_direction(point, previous_close, market),
                "volume": point["volume"],
            })
            previous_close = point["close"]

        if converted:
            converted_segments.append(converted)
            for candle in converted:
                if highest is None or candle["raw_high"] > highest["value"]:
                    highest = {"value": candle["raw_high"], "x": candle["x"], "y": candle["high"]}
                if lowest is None or candle["raw_low"] < lowest["value"]:
                    lowest = {"value": candle["raw_low"], "x": candle["x"], "y": candle["low"]}
            if segment_index > 0:
                divider_x = converted[0]["x"]
                dividers.append(divider_x)

    axis_marks = build_axis_marks(all_points)
    for label, minute in axis_marks:
        x = plot_x0 + (plot_width * (minute - min_minute) / minute_span)
        draw.line((x, plot_y0, x, plot_y1), fill="#f5f7fa", width=1)
        text_w, _ = measure(FONT_AXIS, label)
        draw_text(draw, (x - text_w / 2, plot_y1 + su(12)), label, FONT_AXIS, "#7c8ea0")

    for divider_x in dividers:
        draw.line((divider_x, plot_y0, divider_x, plot_y1), fill="#eef2f6", width=1)

    for converted in converted_segments:
        for candle in converted:
            if candle["direction"] == "up":
                body_fill = palette["candle_up"]
                body_outline = palette["candle_up"]
            elif candle["direction"] == "down":
                body_fill = palette["candle_down"]
                body_outline = palette["candle_down"]
            else:
                body_fill = palette["candle_flat"]
                body_outline = palette["candle_flat"]
            wick_color = "#c7d0da"
            draw.line((candle["x"], candle["high"], candle["x"], candle["low"]), fill=wick_color, width=max(1, su(1)))
            top = min(candle["open"], candle["close"])
            bottom = max(candle["open"], candle["close"])
            if bottom - top < su(2):
                bottom = top + su(2)
            draw.rectangle(
                (
                    candle["x"] - candle_width / 2,
                    top,
                    candle["x"] + candle_width / 2,
                    bottom,
                ),
                fill=body_fill,
                outline=body_outline,
                width=max(1, su(1)),
            )
            vol_h = 0 if max_volume == 0 else (candle["volume"] / max_volume) * volume_height
            draw.rectangle(
                (
                    candle["x"] - max(1, candle_width / 2),
                    volume_y1 - vol_h,
                    candle["x"] + max(1, candle_width / 2),
                    volume_y1,
                ),
                fill="#d6dde7",
                outline=None,
            )

    warnings = chart.get("warnings", [])
    if warnings:
        warning_y = cy1 + su(12)
        for warning in warnings[:2]:
            draw_text(draw, (cx0 + 2, warning_y), warning, FONT_TINY, "#c2410c")
            warning_y += su(20)

    return {"highest": highest, "lowest": lowest}


def draw_card(draw, box, card, palette):
    x0, y0, x1, y1 = box
    rounded(draw, box, su(28), fill="#ffffff", outline="#dbe6f0")

    draw_text(draw, (x0 + su(22), y0 + su(22)), card.get("name", "-"), FONT_NAME, "#14202b")
    draw_text(draw, (x0 + su(22), y0 + su(66)), card.get("price", "-"), FONT_PRICE, "#14202b")
    market = card.get("market", "-")
    market_w, market_h = measure(FONT_TINY, market)
    pill_x1 = x1 - su(22)
    pill_x0 = pill_x1 - market_w - su(26)
    pill_y0 = y0 + su(24)
    pill_y1 = pill_y0 + market_h + su(14)
    rounded(draw, (pill_x0, pill_y0, pill_x1, pill_y1), su(14), fill="#f5f9fd", outline="#dbe6f0")
    draw_text(draw, (pill_x0 + su(13), pill_y0 + su(6)), market, FONT_TINY, "#6f8295")

    pct = str(card.get("pct", ""))
    meta_color = palette["up"] if pct.startswith("+") else palette["down"] if pct.startswith("-") else palette["flat"]
    draw_text(draw, (x0 + su(22), y0 + su(126)), f"어제보다 {card.get('diff', '-')} ({pct})", FONT_META, meta_color)

    extrema = draw_chart(draw, box, card.get("chart", {}), palette, card.get("market", ""))

    stats_y = y1 - su(66)
    left_text = "-"
    right_text = "-"
    if extrema.get("lowest") is not None:
        left_text = f"최저 {format_axis_value(extrema['lowest']['value'])}"
    if extrema.get("highest") is not None:
        right_text = f"최고 {format_axis_value(extrema['highest']['value'])}"
    draw_text(draw, (x0 + su(22), stats_y), left_text, FONT_SMALL, "#98a4b3")
    right_w, _ = measure(FONT_SMALL, right_text)
    draw_text(draw, (x1 - su(22) - right_w, stats_y), right_text, FONT_SMALL, "#98a4b3")

    footer_y = y1 - su(36)
    interval = card.get("chart", {}).get("interval_minutes")
    tag = f"KIS {interval}m candles" if interval else "KIS intraday"
    tag_width, _ = measure(FONT_SMALL, tag)
    draw_text(draw, (x1 - su(22) - tag_width, footer_y), tag, FONT_SMALL, "#7b8a9b")


def draw_summary_card(draw, box, card, palette):
    x0, y0, x1, y1 = box
    rounded(draw, box, su(22), fill="#ffffff", outline="#dbe6f0")
    draw_text(draw, (x0 + su(12), y0 + su(10)), card.get("name", "-"), FONT_AXIS, "#66788a")
    market = card.get("market", "")
    if market:
        mw, mh = measure(FONT_AXIS, market)
        rounded(draw, (x1 - mw - su(18), y0 + su(8), x1 - su(10), y0 + mh + su(16)), su(9), fill="#f5f9fd", outline="#dbe6f0")
        draw_text(draw, (x1 - mw - su(14), y0 + su(10)), market, FONT_AXIS, "#90a2b5")
    draw_text(draw, (x0 + su(12), y0 + su(34)), card.get("price", "-"), FONT_META, "#14202b")
    pct = str(card.get("pct", ""))
    status = card.get("status", "")
    meta_color = palette["up"] if pct.startswith("+") else palette["down"] if pct.startswith("-") else palette["flat"]
    if status == "unavailable":
        meta_color = "#94a3b8"
    label = card.get("label", "")
    diff = card.get("diff", "-")
    if pct:
        meta = f"{label} {diff} ({pct})".strip()
    else:
        meta = f"{label} {diff}".strip()
    draw_text(draw, (x0 + su(12), y0 + su(72)), meta, FONT_AXIS, meta_color)


def main():
    apply_render_settings()
    data = json.loads(json_path().read_text())
    palette = market_palette(data.get("market", "kr"))
    summary_cards = data.get("summary_cards", [])
    stock_cards = data.get("stock_cards", [])
    summary_y = PADDING + HEADER_HEIGHT
    summary_layouts = summary_card_layout(summary_cards, summary_y)
    stocks_y = (max(box[3] for box in summary_layouts) + 22) if summary_layouts else (PADDING + HEADER_HEIGHT)
    layouts = stock_card_layout(stock_cards, stocks_y)
    content_bottom = max(
        [box[3] for box in summary_layouts] + [box[3] for box in layouts] + [PADDING + HEADER_HEIGHT + CARD_HEIGHT]
    )
    height = content_bottom + BOTTOM_PADDING

    image = Image.new("RGBA", (WIDTH, height), "#f5f8fb")
    draw = ImageDraw.Draw(image)

    for y in range(height):
        ratio = y / max(1, height - 1)
        r1, g1, b1 = (250, 252, 255)
        r2, g2, b2 = (241, 246, 251)
        color = (
            int(r1 + (r2 - r1) * ratio),
            int(g1 + (g2 - g1) * ratio),
            int(b1 + (b2 - b1) * ratio),
            255,
        )
        draw.line((0, y, WIDTH, y), fill=color)

    draw_text(draw, (PADDING, PADDING), data.get("title", "KR Market Dashboard"), FONT_H1, "#10202f")
    draw_text(draw, (PADDING, PADDING + su(68)), data.get("subtitle", "KIS intraday"), FONT_SUB, "#6f8295")
    generated_at = data.get("generated_at", "")
    if generated_at:
        stamp = generated_at.replace("T", " ")
        stamp_w, _ = measure(FONT_TINY, stamp)
        draw_text(draw, (WIDTH - PADDING - stamp_w, PADDING + su(18)), stamp, FONT_TINY, "#93a4b5")

    for idx, card in enumerate(summary_cards):
        draw_summary_card(draw, summary_layouts[idx], card, palette)

    for idx, card in enumerate(stock_cards):
        draw_card(draw, layouts[idx], card, palette)

    output = png_path()
    output.parent.mkdir(parents=True, exist_ok=True)
    target_width = OUTPUT_WIDTH
    base_height = max(1, int(height / RENDER_SCALE))
    scaled_height = max(1, int(base_height * (OUTPUT_WIDTH / BASE_WIDTH)))
    target_height = OUTPUT_HEIGHT or scaled_height
    if image.size != (target_width, target_height):
        image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    image.save(output, optimize=True, compress_level=6)
    print(str(output))


if __name__ == "__main__":
    main()
