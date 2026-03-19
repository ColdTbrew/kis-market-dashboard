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

    dashboard = extract_block(content, ".dashboard")
    assert "min-width: 0;" in dashboard

    stack = extract_block(content, ".stack")
    assert "min-width: 0;" in stack

    panel = extract_block(content, ".panel")
    assert "overflow: hidden;" in panel

    field = extract_block(content, ".field")
    assert "min-width: 0;" in field

    field_controls = extract_block(content, ".field input,\n.field select")
    assert "max-width: 100%;" in field_controls


def test_web_ui_loads_lightweight_charts() -> None:
    html = (Path(__file__).resolve().parents[2] / "web_ui" / "index.html").read_text(encoding="utf-8")
    assert "lightweight-charts.standalone.production.js" in html
