"""Bot message formatting — audit P1 (round 3): raw <b> tags must never be
sent as literal text. _fmt_html escapes everything first, then converts
**bold** into <b>. Message sources must not contain raw tags."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.bots.handler import _fmt_html


def test_fmt_html_escapes_raw_tags():
    out = _fmt_html("یک <b>تگ</b> خام")
    assert "&lt;b&gt;" in out      # escaped, never sent as HTML tag
    assert "<b>" not in out
    assert "**" not in out


def test_fmt_html_converts_asterisks_to_bold():
    out = _fmt_html("سلام **دنیا**")
    assert "<b>دنیا</b>" in out


def test_fmt_html_escapes_script():
    out = _fmt_html("<script>alert(1)</script>")
    assert "<script>" not in out


def test_no_raw_b_tags_in_bot_message_sources():
    root = Path(__file__).resolve().parent.parent
    for p in (root / "app/bots/handler.py", root / "app/report/weekly.py"):
        src = p.read_text(encoding="utf-8")
        lines = [ln for ln in src.splitlines() if 'r"<b>' not in ln]  # converter emits <b> by design
        assert "<b>" not in "\n".join(lines), f"raw <b> left in {p}"
