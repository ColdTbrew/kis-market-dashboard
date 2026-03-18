#!/usr/bin/env python3
import json
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = Path(os.getenv("KIS_DASHBOARD_JSON", ROOT / "tmp" / "kis_market_dashboard.json"))
PNG_PATH = Path(os.getenv("KIS_DASHBOARD_PNG", ROOT / "tmp" / "kis_market_dashboard.png"))

WIDTH = 1200
PADDING = 28
GAP = 22
CARD_HEIGHT = 470
HEADER_HEIGHT = 86
BOTTOM_PADDING = 28
COLS = 2


def load_font(size, bold=False):
    candidates = []
    if bold:
        candidates.extend([
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/HelveticaNeue.ttc",
        ])
    candidates.extend([
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    ])

    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


FONT_H1 = load_font(36, bold=True)
FONT_SUB = load_font(17)
FONT_NAME = load_font(28, bold=True)
FONT_PRICE = load_font(42, bold=True)
FONT_META = load_font(21, bold=True)
FONT_SMALL = load_font(16)
FONT_TINY = load_font(14)
FONT_AXIS = load_font(13)


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


def card_box(index):
    row = index // COLS
    col = index % COLS
    card_width = (WIDTH - (PADDING * 2) - GAP) // COLS
    x0 = PADDING + col * (card_width + GAP)
    y0 = PADDING + HEADER_HEIGHT + row * (CARD_HEIGHT + GAP)
    return x0, y0, x0 + card_width, y0 + CARD_HEIGHT


def chart_bounds(box):
    x0, y0, x1, y1 = box
    return x0 + 16, y0 + 156, x1 - 16, y0 + 352


def flatten_segments(segments):
    merged = []
    for segment in segments:
        for point in segment.get("points", []):
            merged.append({
                "session": segment.get("session", ""),
                "color": segment.get("color", "#5ad7ff"),
                "time": point.get("time", ""),
                "time_raw": point.get("time_raw", ""),
                "price": int(point.get("price", 0)),
                "open": int(point.get("open", point.get("price", 0))),
                "high": int(point.get("high", point.get("price", 0))),
                "low": int(point.get("low", point.get("price", 0))),
                "close": int(point.get("close", point.get("price", 0))),
            })
    return merged


def hhmmss_to_minutes(value):
    raw = str(value or "").zfill(6)
    return int(raw[:2]) * 60 + int(raw[2:4])


def draw_chart(draw, box, chart):
    cx0, cy0, cx1, cy1 = chart_bounds(box)
    rounded(draw, (cx0, cy0, cx1, cy1), 20, fill="#ffffff", outline="#dbe6f0")
    inner = (cx0 + 12, cy0 + 14, cx1 - 12, cy1 - 14)
    rounded(draw, inner, 14, fill="#f8fbff")

    segments = [segment for segment in chart.get("segments", []) if segment.get("points")]
    if not segments:
        draw_text(draw, (cx0 + 18, cy0 + 18), "No intraday data from KIS", FONT_SMALL, "#c2410c")
        return

    all_points = flatten_segments(segments)
    prices = [value for point in all_points for value in (point["low"], point["high"])]
    min_price = min(prices)
    max_price = max(prices)
    price_span = max(1, max_price - min_price)
    plot_x0, plot_y0, plot_x1, plot_y1 = inner[0] + 16, inner[1] + 14, inner[2] - 16, inner[3] - 30
    plot_height = plot_y1 - plot_y0
    plot_width = plot_x1 - plot_x0

    for ratio in (0.0, 0.5, 1.0):
        y = plot_y0 + ratio * plot_height
        draw.line((plot_x0, y, plot_x1, y), fill="#e5edf5", width=1)

    min_minute = min(hhmmss_to_minutes(point["time_raw"]) for point in all_points)
    max_minute = max(hhmmss_to_minutes(point["time_raw"]) for point in all_points)
    minute_span = max(1, max_minute - min_minute)
    dividers = []
    session_labels = []
    candle_width = max(4, int(plot_width / max(70, minute_span / 5)))

    for segment in segments:
        seg_points = segment["points"]
        color = segment.get("color", "#5ad7ff")
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
            })

        if converted:
            for candle in converted:
                wick_color = color
                body_fill = "#ffffff" if candle["close"] < candle["open"] else color
                body_outline = color
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
            band_x0 = converted[0]["x"]
            band_x1 = converted[-1]["x"]
            if session_labels:
                divider_x = converted[0]["x"]
                dividers.append(divider_x)
            session_labels.append({
                "color": color,
                "x": (band_x0 + band_x1) / 2,
                "label": segment["session"],
            })

    for divider_x in dividers:
        draw.line((divider_x, plot_y0, divider_x, plot_y1), fill="#cbd7e3", width=1)

    for item in session_labels:
        text_w, text_h = measure(FONT_AXIS, item["label"])
        px0 = item["x"] - (text_w + 16) / 2
        py0 = plot_y0 + 8
        px1 = px0 + text_w + 16
        py1 = py0 + text_h + 8
        rounded(draw, (px0, py0, px1, py1), 10, fill="#ffffff", outline="#d9e4ee")
        draw_text(draw, (px0 + 8, py0 + 4), item["label"], FONT_AXIS, item["color"])

    axis_marks = [
        ("08:00", "080000"),
        ("09:00", "090000"),
        ("15:30", "153000"),
        ("19:59", "195900"),
    ]
    for label, raw in axis_marks:
        minute = hhmmss_to_minutes(raw)
        if minute < min_minute or minute > max_minute:
            continue
        x = plot_x0 + (plot_width * (minute - min_minute) / minute_span)
        draw.line((x, plot_y0, x, plot_y1), fill="#eef3f8", width=1)
        text_w, _ = measure(FONT_AXIS, label)
        draw_text(draw, (x - text_w / 2, plot_y1 + 8), label, FONT_AXIS, "#7c8ea0")

    warnings = chart.get("warnings", [])
    if warnings:
        warning_y = cy1 + 12
        for warning in warnings[:2]:
            draw_text(draw, (cx0 + 2, warning_y), warning, FONT_TINY, "#c2410c")
            warning_y += 18


def draw_card(draw, box, card):
    x0, y0, x1, y1 = box
    rounded(draw, box, 26, fill="#ffffff", outline="#dbe6f0")

    draw_text(draw, (x0 + 20, y0 + 22), card.get("name", "-"), FONT_NAME, "#14202b")
    draw_text(draw, (x0 + 20, y0 + 72), card.get("price", "-"), FONT_PRICE, "#14202b")

    pct = str(card.get("pct", ""))
    meta_color = "#059669" if pct.startswith("+") else "#dc2626" if pct.startswith("-") else "#64748b"
    draw_text(draw, (x0 + 20, y0 + 128), f"Δ {card.get('diff', '-')} · {pct}", FONT_META, meta_color)

    draw_chart(draw, box, card.get("chart", {}))

    footer_y = y1 - 36
    draw_text(draw, (x0 + 20, footer_y), card.get("market", "-"), FONT_SMALL, "#7b8a9b")
    interval = card.get("chart", {}).get("interval_minutes")
    tag = f"KIS {interval}m candles" if interval else "KIS intraday"
    tag_width, _ = measure(FONT_SMALL, tag)
    draw_text(draw, (x1 - 20 - tag_width, footer_y), tag, FONT_SMALL, "#7b8a9b")


def main():
    data = json.loads(JSON_PATH.read_text())
    cards = data.get("cards", [])
    rows = max(1, math.ceil(len(cards) / COLS))
    height = PADDING + HEADER_HEIGHT + rows * CARD_HEIGHT + max(0, rows - 1) * GAP + BOTTOM_PADDING

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
    draw_text(draw, (PADDING, PADDING + 50), data.get("subtitle", "KIS intraday"), FONT_SUB, "#6f8295")

    for idx, card in enumerate(cards):
        draw_card(draw, card_box(idx), card)

    PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    image.save(PNG_PATH)
    print(str(PNG_PATH))


if __name__ == "__main__":
    main()
