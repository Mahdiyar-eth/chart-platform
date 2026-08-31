"""Purchase and load states must be visible, and errors must reach the user.

solar.html had three defects that all end in the same place — the user staring
at a screen that will never change:

  * `err` was assigned in the failure branch and rendered nowhere, so any
    failure of /api/solar/{id} (402, 500, ephemeris error) left loaded=false
    and the x-show="!loaded" skeleton spinning forever.
  * buy() destructured the response to {ok, d} and then read `r.status`, which
    is out of scope. The ReferenceError was swallowed by .catch(), so a user
    with insufficient credits was told "could not reach the server" instead of
    being sent to /credits. relocation.html carries `status` through correctly.
  * neither buy() had a busy flag, so the button stayed live and re-clickable
    during the request — a double-click is a double purchase attempt.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

TPL = Path(__file__).resolve().parent.parent / "app" / "templates"
PRODUCT_PAGES = ["solar.html", "relocation.html"]


def _src(name: str) -> str:
    return (TPL / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", PRODUCT_PAGES)
def test_error_state_is_rendered(name):
    """Assigning err is pointless if nothing displays it."""
    src = _src(name)
    assert re.search(r'x-(?:text|show)="[^"]*\berr\b', src), (
        f"{name}: err is assigned but never rendered — a failed load leaves "
        "the user on an endless skeleton"
    )


@pytest.mark.parametrize("name", PRODUCT_PAGES)
def test_purchase_is_not_reentrant(name):
    """A double click must not become a double purchase attempt.

    Checks for the guard itself rather than a specific flag name — relocation
    already uses `busy` for its compare action, so its purchase guard is
    necessarily called something else.
    """
    src = _src(name)
    # anchor on the function definition, not the first `@click="buy()"` in the
    # markup — the button appears earlier in the file than the handler
    m = re.search(r"\n\s*buy\(\)\s*\{", src)
    assert m, f"{name}: no buy() definition found"
    body = src[m.start():m.start() + 1400]
    guard = re.search(r"if\s*\(\s*this\.(\w+)\s*\)\s*return", body)
    assert guard, (
        f"{name}: buy() has no re-entrancy guard, so the button stays live "
        "during the request and a second click fires a second purchase"
    )
    flag = guard.group(1)
    assert f"this.{flag} = true" in body, f"{name}: guard {flag} is never set"
    assert re.search(rf"finally\s*\(\s*\(\)\s*=>\s*{{[^}}]*this\.{flag}\s*=\s*false",
                     body), (
        f"{name}: guard {flag} is never cleared, so a failed purchase locks "
        "the button forever"
    )


@pytest.mark.parametrize("name", PRODUCT_PAGES)
def test_no_out_of_scope_response_status(name):
    """`r.status` inside a handler whose parameter is a destructured object.

    `.then(r => ({ok: r.ok, d, status: r.status}))` is fine — r is that arrow's
    own parameter. The bug is the *next* link in the chain:
    `.then(({ok, d}) => { ... r.status ... })`, where r no longer exists.
    """
    src = _src(name)
    # each `.then(({...}) => {` handler, up to the start of the following
    # .then/.catch/.finally link
    for m in re.finditer(r"\.then\(\(\{(?P<params>[^}]*)\}\)\s*=>\s*\{"
                         r"(?P<body>.*?)(?=\n\s*\.(?:then|catch|finally)\()",
                         src, re.S):
        body, params = m.group("body"), m.group("params")
        bad = re.findall(r"\br\.\w+", body)
        assert not bad, (
            f"{name}: handler destructures to ({{{params.strip()}}}) and then "
            f"reads {bad[:2]} — r is out of scope, the ReferenceError is "
            "swallowed by .catch(), and the user sees the wrong error"
        )


@pytest.mark.parametrize("name", PRODUCT_PAGES)
def test_insufficient_credits_routes_to_credits(name):
    src = _src(name)
    assert "/credits" in src, (
        f"{name}: a 402 must send the user somewhere they can top up"
    )
