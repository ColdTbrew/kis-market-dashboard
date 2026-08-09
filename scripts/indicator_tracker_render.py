#!/usr/bin/env python3
"""Render each daily indicator chart as a high-resolution PNG."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

LOGICAL_WIDTH = 1206
LOGICAL_HEIGHT = 1407
SUPERSAMPLE = 2
OUTPUT_WIDTH = LOGICAL_WIDTH
OUTPUT_HEIGHT = LOGICAL_HEIGHT
WIDTH = LOGICAL_WIDTH
MARGIN = 42
CARD_HEIGHT = LOGICAL_HEIGHT - MARGIN * 2
CANVAS_HEIGHT = LOGICAL_HEIGHT
BACKGROUND = "#f4f7fb"
CARD = "#ffffff"
TEXT = "#172033"
MUTED = "#667085"
GRID = "#e8edf4"
UP = "#ef4444"
DOWN = "#2563eb"
US_UP = "#16a34a"
US_DOWN = "#ef4444"
ICHIMOKU_SHIFT = 26
ICHIMOKU_TENKAN = "#c026d3"
ICHIMOKU_KIJUN = "#0891b2"
ICHIMOKU_SPAN_A = "#0f9f6e"
ICHIMOKU_SPAN_B = "#e11d48"


def load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/NotoSansKR-Regular.otf",
        "/System/Library/Fonts/AppleGothic.ttf",
    ]
    index = 1 if bold else 0
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size * SUPERSAMPLE, index=index)
        except (OSError, ValueError):
            continue
    return ImageFont.load_default()


FONT_TITLE = load_font(48, bold=True)
FONT_VALUE = load_font(36, bold=True)
FONT_META = load_font(27)
FONT_AXIS = load_font(24)
FONT_LEGEND = load_font(27, bold=True)


class ScaledDraw:
    """Draw in logical coordinates on a supersampled image."""

    def __init__(self, draw: ImageDraw.ImageDraw):
        self._draw = draw

    @staticmethod
    def _coords(values: Any) -> Any:
        if isinstance(values, (tuple, list)):
            if values and isinstance(values[0], (tuple, list)):
                return [ScaledDraw._coords(value) for value in values]
            return tuple(round(float(value) * SUPERSAMPLE) for value in values)
        return values

    def text(self, xy: tuple[float, float], text: str, **kwargs: Any) -> None:
        self._draw.text(self._coords(xy), text, **kwargs)

    def textbbox(self, xy: tuple[float, float], text: str, **kwargs: Any) -> tuple[int, int, int, int]:
        box = self._draw.textbbox(self._coords(xy), text, **kwargs)
        return tuple(round(value / SUPERSAMPLE) for value in box)

    def line(self, xy: Any, *, fill: str, width: int, **kwargs: Any) -> None:
        self._draw.line(
            self._coords(xy),
            fill=fill,
            width=max(1, round(width * SUPERSAMPLE)),
            **kwargs,
        )

    def rectangle(self, xy: Any, **kwargs: Any) -> None:
        if "width" in kwargs:
            kwargs["width"] = max(1, round(kwargs["width"] * SUPERSAMPLE))
        self._draw.rectangle(self._coords(xy), **kwargs)

    def polygon(self, xy: Any, **kwargs: Any) -> None:
        self._draw.polygon(self._coords(xy), **kwargs)

    def rounded_rectangle(self, xy: Any, *, radius: int, **kwargs: Any) -> None:
        if "width" in kwargs:
            kwargs["width"] = max(1, round(kwargs["width"] * SUPERSAMPLE))
        self._draw.rounded_rectangle(
            self._coords(xy),
            radius=round(radius * SUPERSAMPLE),
            **kwargs,
        )


def _rounded(draw: ScaledDraw, box: tuple[int, int, int, int], radius: int, **kwargs: Any) -> None:
    draw.rounded_rectangle(box, radius=radius, **kwargs)


def _text_size(draw: ScaledDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    return right - left, bottom - top


def _format_number(value: float, unit: str, precision: int) -> str:
    if unit == "$":
        return f"${value:,.{precision}f}"
    if unit == "%":
        return f"{value:,.{precision}f}%"
    suffix = unit if unit else ""
    return f"{value:,.{precision}f}{suffix}"


def _format_axis(value: float) -> str:
    absolute = abs(value)
    if absolute >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:.1f}조"
    if absolute >= 100_000_000:
        return f"{value / 100_000_000:.0f}억"
    if absolute >= 10_000:
        return f"{value:,.0f}"
    if absolute >= 100:
        return f"{value:,.1f}"
    return f"{value:,.2f}"


def _line_points(
    values: Iterable[float | None],
    *,
    x_for: Callable[[int], float],
    y_for: Callable[[float], float],
) -> list[list[tuple[float, float]]]:
    segments: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    for index, value in enumerate(values):
        if value is None:
            if current:
                segments.append(current)
                current = []
            continue
        current.append((x_for(index), y_for(float(value))))
    if current:
        segments.append(current)
    return segments


def _draw_series(
    draw: ScaledDraw,
    values: Iterable[float | None],
    *,
    x_for: Callable[[int], float],
    y_for: Callable[[float], float],
    color: str,
    width: int = 4,
) -> None:
    for segment in _line_points(values, x_for=x_for, y_for=y_for):
        if len(segment) >= 2:
            draw.line(segment, fill=color, width=width, joint="curve")


def _draw_ichimoku_cloud(
    draw: ScaledDraw,
    span_a: list[float | None],
    span_b: list[float | None],
    *,
    x_for: Callable[[int], float],
    y_for: Callable[[float], float],
) -> None:
    for index in range(1, min(len(span_a), len(span_b))):
        previous_a = span_a[index - 1]
        previous_b = span_b[index - 1]
        current_a = span_a[index]
        current_b = span_b[index]
        if None in (previous_a, previous_b, current_a, current_b):
            continue
        fill = (
            "#e8f7f0"
            if (float(current_a) + float(previous_a)) >= (float(current_b) + float(previous_b))
            else "#fdecef"
        )
        draw.polygon(
            [
                (x_for(index - 1), y_for(float(previous_a))),
                (x_for(index), y_for(float(current_a))),
                (x_for(index), y_for(float(current_b))),
                (x_for(index - 1), y_for(float(previous_b))),
            ],
            fill=fill,
        )


def _draw_axes(
    draw: ScaledDraw,
    plot: tuple[int, int, int, int],
    y_min: float,
    y_max: float,
) -> None:
    x0, y0, x1, y1 = plot
    for index in range(5):
        ratio = index / 4
        y = int(y0 + (y1 - y0) * ratio)
        value = y_max - (y_max - y_min) * ratio
        draw.line((x0, y, x1, y), fill=GRID, width=2)
        draw.text((x0 + 8, y + 4), _format_axis(value), fill=MUTED, font=FONT_AXIS)


def _date_label(raw: str) -> str:
    try:
        return datetime.fromisoformat(raw).strftime("%y-%m-%d")
    except ValueError:
        return raw


def _draw_x_labels(
    draw: ScaledDraw,
    plot: tuple[int, int, int, int],
    rows: list[dict[str, Any]],
    *,
    domain_points: int | None = None,
) -> None:
    x0, _, x1, y1 = plot
    if not rows:
        return
    indices = sorted({0, len(rows) // 3, (len(rows) * 2) // 3, len(rows) - 1})
    for index in indices:
        ratio = index / max(1, (domain_points or len(rows)) - 1)
        x = int(x0 + (x1 - x0) * ratio)
        label = _date_label(rows[index]["date"])
        width, _ = _text_size(draw, label, FONT_AXIS)
        label_x = max(x0 + 12, min(x - width // 2, x1 - width - 12))
        draw.text((label_x, y1 + 24), label, fill=MUTED, font=FONT_AXIS)


def _draw_value_box(
    draw: ScaledDraw,
    x: int,
    y: int,
    label: str,
    value: str,
    *,
    color: str,
    width: int,
    height: int,
) -> None:
    _rounded(
        draw,
        (x, y, x + width, y + height),
        18,
        fill="#f8fafc",
        outline="#d8e0eb",
        width=2,
    )
    draw.text((x + 20, y + 14), label, fill=MUTED, font=FONT_META)
    draw.text((x + 20, y + 54), value, fill=color, font=FONT_VALUE)


def _draw_legend_grid(
    draw: ScaledDraw,
    *,
    x: int,
    y: int,
    column_width: int,
    items: Iterable[tuple[str, str]],
    row_gap: int = 58,
) -> None:
    for index, (label, color) in enumerate(items):
        item_x = x + index % 2 * column_width
        item_y = y + index // 2 * row_gap
        draw.line((item_x, item_y + 15, item_x + 42, item_y + 15), fill=color, width=7)
        draw.text((item_x + 58, item_y), label, fill=MUTED, font=FONT_LEGEND)


def draw_market_chart(
    draw: ScaledDraw,
    box: tuple[int, int, int, int],
    chart: dict[str, Any],
) -> None:
    x0, y0, x1, y1 = box
    up_color, down_color = (
        (US_UP, US_DOWN) if chart.get("market") == "us" else (UP, DOWN)
    )
    _rounded(draw, box, 28, fill=CARD, outline="#e1e7ef", width=2)
    draw.text((x0 + 30, y0 + 24), chart["title"], fill=TEXT, font=FONT_TITLE)
    draw.text(
        (x0 + 30, y0 + 70),
        f"기준 {chart['updated_date']} · {chart['source']}",
        fill=MUTED,
        font=FONT_META,
    )

    rows = chart["data"]
    content_width = x1 - x0 - 60
    value_gap = 18
    value_width = (content_width - value_gap) // 2
    value_y = y0 + 130
    legend_y = y0 + 285
    show_ichimoku = bool(chart.get("ichimoku"))
    point_count = len(rows) + (ICHIMOKU_SHIFT if show_ichimoku else 0)
    plot_top = y0 + (510 if show_ichimoku else 430)
    plot = (x0 + 30, plot_top, x1 - 30, y1 - 90)
    values = [
        float(value)
        for row in rows
        for key in ("low", "high", "bb_lower", "bb_upper")
        if (value := row.get(key)) is not None
    ]
    y_min, y_max = min(values), max(values)
    padding = max((y_max - y_min) * 0.06, abs(y_max) * 0.002, 0.01)
    y_min -= padding
    y_max += padding

    px0, py0, px1, py1 = plot
    x_for = lambda index: px0 + (px1 - px0) * index / max(1, point_count - 1)
    y_for = lambda value: py1 - (value - y_min) * (py1 - py0) / max(1e-12, y_max - y_min)

    if show_ichimoku:
        span_a = [None] * ICHIMOKU_SHIFT + [
            row.get("ichimoku_span_a") for row in rows
        ]
        span_b = [None] * ICHIMOKU_SHIFT + [
            row.get("ichimoku_span_b") for row in rows
        ]
        _draw_ichimoku_cloud(draw, span_a, span_b, x_for=x_for, y_for=y_for)
    else:
        span_a = []
        span_b = []

    _draw_axes(draw, plot, y_min, y_max)

    _draw_series(draw, [row.get("bb_upper") for row in rows], x_for=x_for, y_for=y_for, color="#f3a6ad", width=2)
    _draw_series(draw, [row.get("bb_lower") for row in rows], x_for=x_for, y_for=y_for, color="#aac8f5", width=2)
    if show_ichimoku:
        _draw_series(draw, span_a, x_for=x_for, y_for=y_for, color=ICHIMOKU_SPAN_A, width=2)
        _draw_series(draw, span_b, x_for=x_for, y_for=y_for, color=ICHIMOKU_SPAN_B, width=2)

    if chart.get("kind") == "line":
        _draw_series(draw, [row["close"] for row in rows], x_for=x_for, y_for=y_for, color="#2459a9", width=5)
    else:
        candle_width = max(2, min(8, int((px1 - px0) / max(1, point_count) * 0.72)))
        for index, row in enumerate(rows):
            x = int(x_for(index))
            open_y = int(y_for(float(row["open"])))
            close_y = int(y_for(float(row["close"])))
            high_y = int(y_for(float(row["high"])))
            low_y = int(y_for(float(row["low"])))
            color = up_color if row["close"] >= row["open"] else down_color
            draw.line((x, high_y, x, low_y), fill=color, width=2)
            top, bottom = sorted((open_y, close_y))
            if bottom == top:
                bottom += 2
            draw.rectangle((x - candle_width // 2, top, x + candle_width // 2, bottom), fill=color)

    moving_averages = [("ma20", "#279645"), ("ma60", "#111827"), ("ma120", "#e8a04a")]
    for key, color in moving_averages:
        _draw_series(draw, [row.get(key) for row in rows], x_for=x_for, y_for=y_for, color=color, width=4)

    if show_ichimoku:
        _draw_series(
            draw,
            [row.get("ichimoku_tenkan") for row in rows],
            x_for=x_for,
            y_for=y_for,
            color=ICHIMOKU_TENKAN,
            width=3,
        )
        _draw_series(
            draw,
            [row.get("ichimoku_kijun") for row in rows],
            x_for=x_for,
            y_for=y_for,
            color=ICHIMOKU_KIJUN,
            width=3,
        )

    _draw_x_labels(draw, plot, rows, domain_points=point_count)
    latest = rows[-1]
    previous = rows[-2]
    unit = chart["unit"]
    precision = int(chart["precision"])
    current_color = up_color if latest["close"] >= previous["close"] else down_color
    _draw_value_box(
        draw,
        x0 + 30,
        value_y,
        "현재",
        _format_number(float(latest["close"]), unit, precision),
        color=current_color,
        width=value_width,
        height=112,
    )
    _draw_value_box(
        draw,
        x0 + 30 + value_width + value_gap,
        value_y,
        "직전",
        _format_number(float(previous["close"]), unit, precision),
        color=TEXT,
        width=value_width,
        height=112,
    )

    legend_items = [
        ("MA20", "#279645"),
        ("MA60", "#111827"),
        ("MA120", "#e8a04a"),
        ("BB20", "#8cb6ef"),
    ]
    if show_ichimoku:
        legend_items.extend(
            [
                ("전환선", ICHIMOKU_TENKAN),
                ("기준선", ICHIMOKU_KIJUN),
                ("구름", ICHIMOKU_SPAN_A),
            ]
        )
    _draw_legend_grid(
        draw,
        x=x0 + 30,
        y=legend_y,
        column_width=content_width // 2,
        items=legend_items,
        row_gap=48 if show_ichimoku else 58,
    )


def _flow_bounds(rows: list[dict[str, Any]], keys: list[str]) -> tuple[float, float]:
    values = [float(row[key]) for row in rows for key in keys if row.get(key) is not None]
    low, high = min(values), max(values)
    padding = max((high - low) * 0.08, 1.0)
    return low - padding, high + padding


def draw_flow_chart(
    draw: ScaledDraw,
    box: tuple[int, int, int, int],
    *,
    title: str,
    source: str,
    rows: list[dict[str, Any]],
    series: list[tuple[str, str, str]],
    summary_keys: list[tuple[str, str]],
) -> None:
    x0, y0, x1, y1 = box
    _rounded(draw, box, 28, fill=CARD, outline="#e1e7ef", width=2)
    draw.text((x0 + 30, y0 + 24), title, fill=TEXT, font=FONT_TITLE)
    draw.text((x0 + 30, y0 + 70), f"기준 {rows[-1]['date']} · {source}", fill=MUTED, font=FONT_META)

    content_width = x1 - x0 - 60
    value_gap = 18
    value_width = (content_width - value_gap) // 2
    value_y = y0 + 130
    legend_y = y0 + 285
    plot = (x0 + 30, y0 + 430, x1 - 30, y1 - 90)
    keys = [key for key, _, _ in series]
    y_min, y_max = _flow_bounds(rows, keys)
    _draw_axes(draw, plot, y_min, y_max)
    px0, py0, px1, py1 = plot
    x_for = lambda index: px0 + (px1 - px0) * index / max(1, len(rows) - 1)
    y_for = lambda value: py1 - (value - y_min) * (py1 - py0) / max(1e-12, y_max - y_min)
    if y_min <= 0 <= y_max:
        zero_y = int(y_for(0))
        draw.line((px0, zero_y, px1, zero_y), fill="#aeb8c6", width=3)
    for key, label, color in series:
        _draw_series(draw, [row.get(key) for row in rows], x_for=x_for, y_for=y_for, color=color, width=5)
    _draw_x_labels(draw, plot, rows)

    _draw_legend_grid(
        draw,
        x=x0 + 30,
        y=legend_y,
        column_width=content_width // 2,
        items=[(label, color) for _, label, color in series],
    )

    for index, (label, key) in enumerate(summary_keys):
        value = float(rows[-1][key])
        color = UP if value >= 0 else DOWN
        _draw_value_box(
            draw,
            x0 + 30 + index * (value_width + value_gap),
            value_y,
            label,
            _format_axis(value),
            color=color,
            width=value_width,
            height=112,
        )


def _new_canvas() -> tuple[Image.Image, ScaledDraw]:
    image = Image.new(
        "RGB",
        (WIDTH * SUPERSAMPLE, CANVAS_HEIGHT * SUPERSAMPLE),
        BACKGROUND,
    )
    return image, ScaledDraw(ImageDraw.Draw(image))


def _save_canvas(image: Image.Image, output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    image.resize((OUTPUT_WIDTH, OUTPUT_HEIGHT), Image.Resampling.LANCZOS).save(
        output,
        "PNG",
        optimize=True,
    )
    return output


def render_market_chart_image(chart: dict[str, Any], output: Path) -> Path:
    image, draw = _new_canvas()
    draw_market_chart(
        draw,
        (MARGIN, MARGIN, WIDTH - MARGIN, MARGIN + CARD_HEIGHT),
        chart,
    )
    return _save_canvas(image, output)


def render_flow_chart_image(
    flows: dict[str, Any],
    *,
    title: str,
    series: list[tuple[str, str, str]],
    summary_keys: list[tuple[str, str]],
    output: Path,
) -> Path:
    image, draw = _new_canvas()
    draw_flow_chart(
        draw,
        (MARGIN, MARGIN, WIDTH - MARGIN, MARGIN + CARD_HEIGHT),
        title=title,
        source=flows["source"],
        rows=flows["data"],
        series=series,
        summary_keys=summary_keys,
    )
    return _save_canvas(image, output)


def render_report(report: dict[str, Any], out_dir: Path) -> list[Path]:
    date_slug = datetime.fromisoformat(report["generated_at"]).strftime("%Y%m%d")
    flows = report["flows"]
    charts = [
        *report["kr_charts"],
        *report["us_charts"],
        *report["macro_charts"],
    ]
    output_specs = [
        (f"{index:02d}_{chart['id']}", chart)
        for index, chart in enumerate(charts, start=3)
    ]

    paths = [
        out_dir / f"indicator_tracker.{date_slug}.01_foreigner_flow.png",
        out_dir / f"indicator_tracker.{date_slug}.02_investor_flow.png",
    ]
    render_flow_chart_image(
        flows,
        title="외국인 순매수 누적 (주)",
        series=[
            ("foreigner_cumulative", "외국인 누적", "#ef4444"),
            ("foreigner_ma4", "4주 이동평균", "#2448d8"),
        ],
        summary_keys=[("누적", "foreigner_cumulative"), ("이번 주", "foreigner")],
        output=paths[0],
    )
    render_flow_chart_image(
        flows,
        title="주체별 순매수 누적 (주)",
        series=[
            ("pension_cumulative", "연기금", "#4b5563"),
            ("institution_cumulative", "기관", "#2344c5"),
            ("foreigner_cumulative", "외국인", "#ef4444"),
            ("individual_cumulative", "개인", "#22c55e"),
        ],
        summary_keys=[
            ("개인 누적", "individual_cumulative"),
            ("외국인 누적", "foreigner_cumulative"),
        ],
        output=paths[1],
    )
    for filename, chart in output_specs:
        path = out_dir / f"indicator_tracker.{date_slug}.{filename}.png"
        render_market_chart_image(chart, path)
        paths.append(path)
    return paths
