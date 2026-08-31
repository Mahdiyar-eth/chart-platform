"""Regression: canonical section counts (plan canon, 2026-08-17).

The multi-audit found inconsistent section counts across docs (14 vs 15).
Canon: basic=5, full=13, gold=14. A future plan change MUST update this test.
"""
from app.report.prompt_builder import PLAN_SECTIONS, DOMAINS, CORE_DOMAINS


def test_canon_section_counts():
    assert len(CORE_DOMAINS) == 5
    assert len(DOMAINS) == 13
    assert len(PLAN_SECTIONS["basic"]) == 5
    assert len(PLAN_SECTIONS["full"]) == 13
    assert len(PLAN_SECTIONS["gold"]) == 14  # 13 + islamic
    assert set(PLAN_SECTIONS["basic"]) == set(CORE_DOMAINS)
    assert set(PLAN_SECTIONS["gold"]) - set(PLAN_SECTIONS["full"]) == {"islamic"}


def test_core_domains_present_in_full():
    for d in CORE_DOMAINS:
        assert d in DOMAINS