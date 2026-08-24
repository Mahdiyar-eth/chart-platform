"""D1/D2 — single-source nav tests: state-aware items, no dupes, FAB only pre-chart."""
from app.nav import nav_for, NAV_ITEMS


def _labels(items):
    return [i.label_fa for i in items]


def test_guest_bottom_has_fab_not_dashboard():
    n = nav_for(has_chart=False)
    labs = _labels(n["bottom"])
    assert "چارت رایگان" in labs          # FAB primary CTA
    fab = [i for i in n["bottom"] if i.primary]
    assert len(fab) == 1 and fab[0].label_fa == "چارت رایگان"
    assert "چارت من" not in labs
    assert "کاوش" not in labs


def test_chart_owner_gets_dashboard_and_explore():
    n = nav_for(has_chart=True)
    labs = _labels(n["bottom"])
    assert "چارت من" in labs and "کاوش" in labs
    assert "چارت رایگان" not in labs      # no pointless CTA after conversion


def test_no_duplicate_urls_across_bottom():
    for hc in (False, True):
        urls = [i.url for i in nav_for(has_chart=hc)["bottom"]]
        assert len(urls) == len(set(urls))


def test_drawer_groups_all_have_icons():
    n = nav_for(has_chart=True)
    flat = [it for _, items in n["drawer"] for it in items]
    assert len(flat) >= 8                 # full menu preserved (11 hand-written before)
    assert all(it.icon and it.label_fa and it.url for it in flat)


def test_every_url_in_registry_is_unique():
    urls = [i.url for i in NAV_ITEMS]
    assert len(urls) == len(set(urls))


def test_top_nav_compact_five_to_six():
    for hc in (False, True):
        top = nav_for(has_chart=hc)["top"]
        assert 4 <= len(top) <= 6         # desktop pill must stay compact


def test_glossary_in_learning_drawer():
    """R.8 / S1 — the glossary must be reachable from nav, not an orphan page."""
    for hc in (False, True):
        drawer = nav_for(has_chart=hc)["drawer"]
        for group, items in drawer:
            if group == "یادگیری":
                urls = [it.url for it in items]
                assert "/glossary" in urls, f"glossary missing from یادگیری group: {urls}"
                return
        raise AssertionError("یادگیری drawer group not found")
