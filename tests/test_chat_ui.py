"""The chat UI must distinguish speakers and move its own counter.

Two defects from the mechanical st- -> u- class rename:

  * The Alpine :class expression on the message bubble was swept into
    utilities.css as a rule body — `.u-34b6e1f7{m.me ? '...' : '...';}` — which
    is a JavaScript ternary sitting where declarations should be. The browser
    drops every declaration in it, and chat.html was left with a dangling `:`
    attribute holding nothing. Result: the user's messages and the assistant's
    render identically, with no alignment, colour or tail to tell them apart.
  * The SSE quota frame was received into an empty `else if` block, so the
    "questions left today" counter never moved no matter how many were asked.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHAT = (ROOT / "app" / "templates" / "chat.html").read_text(encoding="utf-8")
CSS = "\n".join(p.read_text(encoding="utf-8")
                for p in (ROOT / "app" / "static" / "css").glob("*.css"))


def test_message_bubbles_are_visually_distinct():
    assert re.search(r"is-me|chat-me|bubble-me", CHAT), (
        "no per-speaker class on the message bubble — both sides render "
        "identically"
    )
    for cls in ("is-me", "is-them"):
        assert cls in CSS, f"{cls} has no styling"


def test_no_dangling_binding_on_the_bubble():
    """`:>` and `:=""` are bindings whose expression went missing."""
    assert not re.search(r'\s:\s*>', CHAT), "dangling `:` attribute on an element"
    assert not re.search(r'\s:\s*=\s*""', CHAT), "empty `:` binding"


def test_no_javascript_expressions_in_stylesheets():
    """A JS ternary in a rule body means an Alpine expression was swept into
    the stylesheet and the element lost its binding."""
    offenders = []
    for path in sorted((ROOT / "app" / "static" / "css").glob("*.css")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            body = line.split("{", 1)[1] if "{" in line else ""
            if re.search(r"\?\s*'", body) or re.search(r"\bm\.\w+\s*\?", body):
                offenders.append(f"{path.name}:{n}: {line.strip()[:110]}")
    assert not offenders, "JavaScript found inside CSS rules:\n" + "\n".join(offenders)


def test_quota_frame_is_handled():
    """The server emits it on every successful answer; the UI must use it."""
    m = re.search(r"evType\s*===\s*'quota'\s*\)\s*\{(?P<body>[^}]*)\}", CHAT)
    assert m, "no quota event handler in the chat page"
    assert m.group("body").strip(), (
        "the quota frame is received into an empty block, so the "
        "questions-left counter never decrements"
    )
    assert "remaining" in m.group("body"), "the handler does not update `remaining`"


def test_tojson_is_never_inside_a_double_quoted_attribute():
    """|tojson emits double quotes, which close a double-quoted attribute.

    chat.html rendered x-on:click="q = {{ p|tojson }}; send()". The browser
    ended the attribute at the first quote tojson produced, so the handler was
    literally `q = ` — an incomplete assignment. Alpine compiles every binding
    with new AsyncFunction, so all seven suggested-question buttons threw
    "Unexpected token '}'" on page load and none of them worked.

    Jinja's tojson escapes ' (and < > &) but not ", so a single-quoted
    attribute is the safe form.
    """
    import re
    from pathlib import Path
    bad = []
    for tpl in sorted((Path(__file__).resolve().parent.parent
                       / "app" / "templates").rglob("*.html")):
        for m in re.finditer(r'=\s*"[^"]*\|\s*tojson[^"]*"', tpl.read_text(encoding="utf-8")):
            bad.append(f"{tpl.name}: {m.group(0)[:80]}")
    assert not bad, (
        "|tojson inside a double-quoted attribute truncates it:\n" + "\n".join(bad)
    )
