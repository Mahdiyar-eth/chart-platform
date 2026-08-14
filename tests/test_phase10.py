"""Tests for phase-10 additions: free preview, paid synastry gate, transit timeline, plans."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.astrology.engine import compute_from_fields
from app.models import PromptVersion
from app.report.preview import free_insights
from sqlmodel import delete

CHART = compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json


def test_preview_returns_insights():
    r = free_insights(CHART)
    assert 3 <= len(r["insights"]) <= 5
    for i in r["insights"]:
        assert i["domain_title"]
        assert len(i["insight"]) > 20


def test_preview_big_three_keys():
    r = free_insights(CHART)
    assert r["big_three"]["sun"] or r["big_three"]["asc"] or r["big_three"]["moon"]


def test_transit_timeline_svg():
    from app.astrology.svg_widgets import transit_timeline_svg
    svg = transit_timeline_svg(CHART)
    assert svg.strip().startswith("<svg")
    assert "نقشهی گذرهای سال آینده" in svg
    assert "<circle" in svg


def test_upcoming_transits_events():
    from app.astrology.transits import upcoming_transits
    ev = upcoming_transits(CHART, days=60)
    assert isinstance(ev, list)
    for e in ev:
        assert e["start"].count("-") == 2
        assert e["planet_fa"]
        assert e["aspect"]


def test_prompt_overrides_versioning():
    """Admin prompt overrides: version bump + active swap + worker merge (plan §8)."""
    from app.db import Session, engine as _eng
    from app.report.prompt_overrides import set_override, get_overrides
    from app.report.prompt_builder import build_prompts_for_plan

    with Session(_eng) as s:
        s.exec(delete(PromptVersion))
        s.commit()
        r1 = set_override(s, "career", "پرامپت آزمایشی حوزهی شغل [V1]")
        r2 = set_override(s, "career", "پرامپت آزمایشی حوزهی شغل [V2]")
        assert r1.version == 1 and r2.version == 2

    active = get_overrides()
    assert active.get("career") == "پرامپت آزمایشی حوزهی شغل [V2]"

    # worker-style merge: content swapped, meta preserved
    ch = compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json
    p = build_prompts_for_plan(ch, "full")
    assert "career" in p
    p["career"] = (active["career"], p["career"][1])
    assert p["career"][0].startswith("پرامپت آزمایشی")
    assert "domain" in p["career"][1]

    with Session(_eng) as s:
        s.exec(delete(PromptVersion))
        s.commit()
    assert get_overrides() == {}


def test_plans_include_new_keys():
    from sqlmodel import select
    from app.db import Session, engine
    from app.models import Plan
    with Session(engine) as s:
        keys = {p.key for p in s.exec(select(Plan)).all()}
    assert {"basic", "full", "gold", "synastry", "monthly"} <= keys
