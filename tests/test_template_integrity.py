"""Structural gates on Jinja templates.

These exist because of a real outage: commit 670a99a deleted the opening
``<script>`` from account.html and left the body and closing tag behind, so
~35 lines of JavaScript rendered as visible text on the page and two Alpine
components never mounted.  Every other gate in the suite (axe, page_gate, the
interaction sweep) reported green throughout, because none of them asked the
cheapest possible question: does this template still parse as HTML?

The same class of bug took out utilities.css for three rounds.  Cheap
structural checks catch it; behavioural checks do not.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
ALL = sorted(TEMPLATES.rglob("*.html"))

# Jinja block tags that open a scope and must be closed by {% end<tag> %}.
PAIRED = ("block", "for", "if", "macro", "call", "filter", "with", "set")


def _ids(paths):
    return [p.relative_to(TEMPLATES).as_posix() for p in paths]


def test_templates_found():
    assert len(ALL) > 30, "template discovery is broken"


@pytest.mark.parametrize("tpl", ALL, ids=_ids(ALL))
def test_script_tags_balanced(tpl: Path):
    """An orphan </script> silently dumps the whole script body onto the page."""
    src = tpl.read_text(encoding="utf-8")
    opens = len(re.findall(r"<script\b", src, re.I))
    closes = len(re.findall(r"</script\s*>", src, re.I))
    assert opens == closes, (
        f"{tpl.name}: {opens} <script> vs {closes} </script>. "
        "An unmatched tag renders JavaScript as visible text."
    )


@pytest.mark.parametrize("tpl", ALL, ids=_ids(ALL))
def test_style_tags_balanced(tpl: Path):
    src = tpl.read_text(encoding="utf-8")
    opens = len(re.findall(r"<style\b", src, re.I))
    closes = len(re.findall(r"</style\s*>", src, re.I))
    assert opens == closes, f"{tpl.name}: {opens} <style> vs {closes} </style>"


@pytest.mark.parametrize("tpl", ALL, ids=_ids(ALL))
def test_jinja_blocks_balanced(tpl: Path):
    """{% block %} without {% endblock %} fails at render time, not import time."""
    src = tpl.read_text(encoding="utf-8")
    for tag in PAIRED:
        # {% set x = 1 %} is an assignment, not a scope; only {% set x %}...{% endset %}
        # opens one.  Count only the scope-opening form.
        if tag == "set":
            opens = len(re.findall(r"{%-?\s*set\s+[^=%]+?-?%}", src))
        else:
            opens = len(re.findall(r"{%-?\s*" + tag + r"\b", src))
        closes = len(re.findall(r"{%-?\s*end" + tag + r"\b", src))
        assert opens == closes, (
            f"{tpl.name}: {opens} {{% {tag} %}} vs {closes} {{% end{tag} %}}"
        )


@pytest.mark.parametrize("tpl", ALL, ids=_ids(ALL))
def test_no_alpine_directive_with_empty_value(tpl: Path):
    """A dangling ``:`` or ``x-bind:`` with no value is a silently dead binding.

    chat.html carried ``:`` with an empty value after its Alpine expression was
    moved out; the result was user and assistant bubbles rendering identically.
    """
    src = tpl.read_text(encoding="utf-8")
    bad = re.findall(r'\s(?::|x-bind:|@)\s*=\s*""', src)
    assert not bad, f"{tpl.name}: empty Alpine binding(s): {bad}"
