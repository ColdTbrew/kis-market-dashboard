#!/usr/bin/env python3
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = Path(os.getenv("KIS_DASHBOARD_JSON", ROOT / "tmp" / "kis_market_dashboard.json"))
PNG_PATH = Path(os.getenv("KIS_DASHBOARD_PNG", ROOT / "tmp" / "kis_market_dashboard.png"))

WIDTH = 1080
PADDING = 32
GAP = 24
CARD_HEIGHT = 500
SUMMARY_GAP = 12
SUMMARY_HEIGHT = 108
HEADER_HEIGHT = 122
BOTTOM_PADDING = 32
COLS = 2


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


FONT_H1 = load_font(46, bold=True)
FONT_SUB = load_font(20)
FONT_NAME = load_font(30, bold=True)
FONT_PRICE = load_font(54, bold=True)
FONT_META = load_font(24, bold=True)
FONT_SMALL = load_font(18)
FONT_TINY = load_font(18)
FONT_AXIS = load_font(16)
FONT_TAB = load_font(20, bold=True)


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
    chart_bottom = y1 - 70
    return x0 + 16, y0 + 150, x1 - 16, chart_bottom


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


def draw_chart(draw, box, chart):
    cx0, cy0, cx1, cy1 = chart_bounds(box)
    rounded(draw, (cx0, cy0, cx1, cy1), 20, fill="#ffffff", outline="#e5ebf2")
    inner = (cx0 + 12, cy0 + 12, cx1 - 12, cy1 - 12)
    rounded(draw, inner, 14, fill="#ffffff")

    segments = [segment for segment in chart.get("segments", []) if segment.get("points")]
    if not segments:
        draw_text(draw, (cx0 + 18, cy0 + 18), "No intraday data from KIS", FONT_SMALL, "#c2410c")
        return

    all_points = flatten_segments(segments)
    prices = [value for point in all_points for value in (point["low"], point["high"])]
    volumes = [point["volume"] for point in all_points]
    min_price = min(prices)
    max_price = max(prices)
    price_span = max(1, max_price - min_price)
    max_volume = max(volumes) if volumes else 1
    plot_x0, plot_y0, plot_x1, plot_y1 = inner[0] + 18, inner[1] + 18, inner[2] - 18, inner[3] - 74
    plot_height = plot_y1 - plot_y0
    plot_width = plot_x1 - plot_x0
    volume_y0 = plot_y1 + 24
    volume_y1 = inner[3] - 20
    volume_height = max(16, volume_y1 - volume_y0)

    draw.line((plot_x0, volume_y0 - 14, plot_x1, volume_y0 - 14), fill="#eef2f6", width=2)

    for ratio in (0.0, 0.5, 1.0):
        y = plot_y0 + ratio * plot_height
        draw.line((plot_x0, y, plot_x1, y), fill="#f0f3f7", width=1)

    min_minute = min(hhmmss_to_minutes(point["time_raw"]) for point in all_points)
    max_minute = max(hhmmss_to_minutes(point["time_raw"]) for point in all_points)
    minute_span = max(1, max_minute - min_minute)
    dividers = []
    candle_width = max(6, int(plot_width / max(72, minute_span / 5)))
    highest = None
    lowest = None

    for segment_index, segment in enumerate(segments):
        seg_points = segment["points"]
        converted = []
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
                "volume": point["volume"],
            })

        if converted:
            for candle in converted:
                if candle["close"] > candle["open"]:
                    body_fill = "#f43f5e"
                    body_outline = "#f43f5e"
                elif candle["close"] < candle["open"]:
                    body_fill = "#3b82f6"
                    body_outline = "#3b82f6"
                else:
                    body_fill = "#b8c2cf"
                    body_outline = "#b8c2cf"
                wick_color = "#c7d0da"
                draw.line((candle["x"], candle["high"], candle["x"], candle["low"]), fill=wick_color, width=1)
                top = min(candle["open"], candle["close"])
                bottom = max(candle["open"], candle["close"])
                if bottom - top < 2:
                    bottom = top + 2
                draw.rectangle(
                    (
                        candle["x"] - candle_width / 2,
                        top,
                        candle["x"] + candle_width / 2,
                        bottom,
                    ),
                    fill=body_fill,
                    outline=body_outline,
                    width=1,
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
                if highest is None or candle["raw_high"] > highest["value"]:
                    highest = {"value": candle["raw_high"], "x": candle["x"], "y": candle["high"]}
                if lowest is None or candle["raw_low"] < lowest["value"]:
                    lowest = {"value": candle["raw_low"], "x": candle["x"], "y": candle["low"]}
            band_x0 = converted[0]["x"]
            if segment_index > 0:
                divider_x = converted[0]["x"]
                dividers.append(divider_x)

    for divider_x in dividers:
        draw.line((divider_x, plot_y0, divider_x, plot_y1), fill="#eef2f6", width=1)

    if highest is not None:
        label = f"최고 {format_axis_value(highest['value'])}"
        lw, lh = measure(FONT_SMALL, label)
        lx = min(plot_x1 - lw, highest["x"] + 6)
        ly = max(plot_y0, highest["y"] - lh - 10)
        draw_text(draw, (lx, ly), label, FONT_SMALL, "#98a4b3")

    if lowest is not None:
        label = f"최저 {format_axis_value(lowest['value'])}"
        lw, lh = measure(FONT_SMALL, label)
        lx = max(plot_x0, lowest["x"] - 6)
        ly = min(plot_y1 - lh, lowest["y"] + 8)
        draw_text(draw, (lx, ly), label, FONT_SMALL, "#98a4b3")

    axis_marks = [
        ("08:00", "080000"),
        ("09:00", "090000"),
        ("12:00", "120000"),
        ("15:30", "153000"),
        ("19:59", "195900"),
    ]
    for label, raw in axis_marks:
        minute = hhmmss_to_minutes(raw)
        if minute < min_minute or minute > max_minute:
            continue
        x = plot_x0 + (plot_width * (minute - min_minute) / minute_span)
        draw.line((x, plot_y0, x, plot_y1), fill="#f5f7fa", width=1)
        text_w, _ = measure(FONT_AXIS, label)
        draw_text(draw, (x - text_w / 2, plot_y1 + 12), label, FONT_AXIS, "#7c8ea0")

    warnings = chart.get("warnings", [])
    if warnings:
        warning_y = cy1 + 12
        for warning in warnings[:2]:
            draw_text(draw, (cx0 + 2, warning_y), warning, FONT_TINY, "#c2410c")
            warning_y += 20


def draw_card(draw, box, card):
    x0, y0, x1, y1 = box
    rounded(draw, box, 28, fill="#ffffff", outline="#dbe6f0")

    draw_text(draw, (x0 + 22, y0 + 22), card.get("name", "-"), FONT_NAME, "#14202b")
    draw_text(draw, (x0 + 22, y0 + 66), card.get("price", "-"), FONT_PRICE, "#14202b")
    market = card.get("market", "-")
    market_w, market_h = measure(FONT_TINY, market)
    pill_x1 = x1 - 22
    pill_x0 = pill_x1 - market_w - 26
    pill_y0 = y0 + 24
    pill_y1 = pill_y0 + market_h + 14
    rounded(draw, (pill_x0, pill_y0, pill_x1, pill_y1), 14, fill="#f5f9fd", outline="#dbe6f0")
    draw_text(draw, (pill_x0 + 13, pill_y0 + 6), market, FONT_TINY, "#6f8295")

    pct = str(card.get("pct", ""))
    meta_color = "#ef4444" if pct.startswith("+") else "#3b82f6" if pct.startswith("-") else "#64748b"
    draw_text(draw, (x0 + 22, y0 + 126), f"어제보다 {card.get('diff', '-')} ({pct})", FONT_META, meta_color)

    draw_chart(draw, box, card.get("chart", {}))

    footer_y = y1 - 36
    draw_text(draw, (x0 + 22, footer_y), "KIS Open API", FONT_SMALL, "#7b8a9b")
    interval = card.get("chart", {}).get("interval_minutes")
    tag = f"KIS {interval}m candles" if interval else "KIS intraday"
    tag_width, _ = measure(FONT_SMALL, tag)
    draw_text(draw, (x1 - 22 - tag_width, footer_y), tag, FONT_SMALL, "#7b8a9b")


def draw_summary_card(draw, box, card):
    x0, y0, x1, y1 = box
    rounded(draw, box, 22, fill="#ffffff", outline="#dbe6f0")
    draw_text(draw, (x0 + 12, y0 + 10), card.get("name", "-"), FONT_AXIS, "#66788a")
    market = card.get("market", "")
    if market:
        mw, mh = measure(FONT_AXIS, market)
        rounded(draw, (x1 - mw - 18, y0 + 8, x1 - 10, y0 + mh + 16), 9, fill="#f5f9fd", outline="#dbe6f0")
        draw_text(draw, (x1 - mw - 14, y0 + 10), market, FONT_AXIS, "#90a2b5")
    draw_text(draw, (x0 + 12, y0 + 34), card.get("price", "-"), FONT_META, "#14202b")
    pct = str(card.get("pct", ""))
    status = card.get("status", "")
    meta_color = "#ef4444" if pct.startswith("+") else "#3b82f6" if pct.startswith("-") else "#64748b"
    if status == "unavailable":
        meta_color = "#94a3b8"
    label = card.get("label", "")
    diff = card.get("diff", "-")
    if pct:
        meta = f"{label} {diff} ({pct})".strip()
    else:
        meta = f"{label} {diff}".strip()
    draw_text(draw, (x0 + 12, y0 + 72), meta, FONT_AXIS, meta_color)


def main():
    data = json.loads(JSON_PATH.read_text())
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
    draw_text(draw, (PADDING, PADDING + 68), data.get("subtitle", "KIS intraday"), FONT_SUB, "#6f8295")
    generated_at = data.get("generated_at", "")
    if generated_at:
        stamp = generated_at.replace("T", " ")
        stamp_w, _ = measure(FONT_TINY, stamp)
        draw_text(draw, (WIDTH - PADDING - stamp_w, PADDING + 18), stamp, FONT_TINY, "#93a4b5")

    for idx, card in enumerate(summary_cards):
        draw_summary_card(draw, summary_layouts[idx], card)

    for idx, card in enumerate(stock_cards):
        draw_card(draw, layouts[idx], card)

    PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    image.save(PNG_PATH)
    print(str(PNG_PATH))


if __name__ == "__main__":
    main()
