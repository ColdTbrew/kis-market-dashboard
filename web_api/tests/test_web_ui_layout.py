from pathlib import Path


def extract_block(css: str, selector: str) -> str:
    start = css.index(selector)
    brace = css.index("{", start)
    depth = 0
    for index in range(brace, len(css)):
        char = css[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return css[brace + 1 : index]
    raise AssertionError(f"could not extract block for {selector}")


def test_generate_panel_has_overflow_guards() -> None:
    css = Path(__file__).resolve().parents[2] / "web_ui" / "styles.css"
    content = css.read_text(encoding="utf-8")

    terminal_shell = extract_block(content, ".terminal-shell")
    assert "min-width: 0;" in terminal_shell

    stack = extract_block(content, ".stack")
    assert "min-width: 0;" in stack

    panel = extract_block(content, ".chart-frame")
    assert "overflow: hidden;" in panel

    field = extract_block(content, ".field")
    assert "min-width: 0;" in field

    field_controls = extract_block(content, ".field input,\n.field select")
    assert "max-width: 100%;" in field_controls


def test_web_ui_loads_lightweight_charts() -> None:
    html = (Path(__file__).resolve().parents[2] / "web_ui" / "index.html").read_text(encoding="utf-8")
    assert "echarts.min.js" in html
    assert "lightweight-charts" not in html


def test_web_ui_has_terminal_chart_layout_hooks() -> None:
    css = (Path(__file__).resolve().parents[2] / "web_ui" / "styles.css").read_text(encoding="utf-8")
    html = (Path(__file__).resolve().parents[2] / "web_ui" / "index.html").read_text(encoding="utf-8")

    assert ".terminal-shell" in css
    assert ".hero-chart-panel" in css
    assert ".control-rail" in css
    assert ".market-strip" in css
    assert 'id="app"' in html


def test_web_ui_uses_flat_terminal_surfaces() -> None:
    css = (Path(__file__).resolve().parents[2] / "web_ui" / "styles.css").read_text(encoding="utf-8")

    body = extract_block(css, "body")
    assert "radial-gradient" not in body
    assert "linear-gradient" not in body

    hero_panel = extract_block(css, ".hero-chart-panel")
    assert "gradient" not in hero_panel

    chart_frame = extract_block(css, ".chart-frame")
    assert "gradient" not in chart_frame

    button_primary = extract_block(css, ".button.primary")
    assert "gradient" not in button_primary


def test_web_ui_uses_app_like_system_font_stack() -> None:
    html = (Path(__file__).resolve().parents[2] / "web_ui" / "index.html").read_text(encoding="utf-8")
    css = (Path(__file__).resolve().parents[2] / "web_ui" / "styles.css").read_text(encoding="utf-8")

    assert "fonts.googleapis.com" not in html
    assert '-apple-system' in css
    assert '"SF Pro Display"' in css
    assert '"SF Mono"' in css
