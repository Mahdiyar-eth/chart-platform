"""Report engine tests — use a FAKE router (no quota spend, deterministic)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from app.astrology.engine import compute_from_fields
from app.report.prompt_builder import build_all_prompts
from app.report.qa import parse_section, qa_section, qa_repetition
from app.report.rules import DOMAINS, evaluate

CHART = compute_from_fields(35.6889, 51.3897, 1994, 8, 23, 6, 10).chart_json

GOOD_SECTION = {
    "section": "relationships",
    "title_fa": "روابط و ازدواج",
    "intro": "نقشهی روابط شما با زحل در خانهی هفتم شکل گرفته است. زحل در این جایگاه، روابط را جدی و متعهدانه میسازد و به آنها عمق و پایداری میبخشد. این چیدمان نشان میدهد که پیوندهای عاطفی شما با گذر زمان قویتر و معنادارتر میشوند.",
    "insights": [
        {"insight": "زحل در خانهی هفتم به روابطی متعهد و پایدار اشاره دارد که با آزمون زمان ساخته میشوند. شما در دوستیها و پیوندهای عاطفی به دنبال معنای عمیق و پایداری هستید و معمولاً قبل از ورود به هر رابطهای، آن را به دقت میسنجید. این ویژگی باعث میشود روابط شما کم اما عمیق و ماندگار باشند. با گذر زمان، اعتماد شما به دیگران بیشتر میشود و پیوندهایی که میسازید، ریشهدار و استوار خواهند بود.",
         "evidence": [{"factor": "Saturn", "sign": "Pisces", "house": 7}],
         "strengths": ["وفاداری و مسئولیتپذیری", "صبر در ساختن رابطه"],
         "challenges": ["احتیاط بیش از حد در آغاز رابطه", "ترس از آسیبپذیری"],
         "practical_advice": "به خود زمان بدهید تا اعتماد بسازید و به تدریج احساسات خود را ابراز کنید."},
        {"insight": "ونوس در میزان، زیباییشناسی، تعادل و هماهنگی را به روابط شما میآورد. شما به ظرافت، ادب و برخورد منصفانه در تعاملات اهمیت میدهید و در روابط خود به دنبال برابری و احترام متقابل هستید. این جایگاه نشان میدهد که عشق شما با گفتوگو، همفکری و همکاری رشد میکند. زیبایی محیط و لحن ملایم گفتار برای شما اهمیت زیادی دارد و در فضایی آرام، بهترین نسخهی خود را نشان میدهید. همراهی با کسی که به احساسات شما ارزش بگذارد، باعث شکوفایی بیشتر شما در زندگی مشترک میشود.",
         "evidence": [{"factor": "Venus", "sign": "Libra", "house": 2}],
         "strengths": ["دیپلماسی و جذابیت", "توانایی ایجاد تعادل"],
         "challenges": ["میل به راضی نگه داشتن همه"],
         "practical_advice": "در انتخابهای خود صادق باشید و به خواستههای واقعیتان احترام بگذارید."},
    ],
}


class FakeRouter:
    def __init__(self, text_by_domain: dict[str, str] | None = None):
        self.text_by_domain = text_by_domain or {}
        self.calls = 0

    async def complete(self, prompt, system=None, max_tokens=2048, temperature=0.7, json_mode=False):
        self.calls += 1
        domain = self._guess_domain(prompt)
        if domain in self.text_by_domain:
            return _res(self.text_by_domain[domain])
        return _res(json.dumps(GOOD_SECTION, ensure_ascii=False))

    @staticmethod
    def _guess_domain(prompt: str) -> str:
        for d in DOMAINS:
            if d in prompt:
                return d
        return "identity"


def _res(text: str):
    from app.core.llm import LLMResult, LLMUsage
    return LLMResult(text=text, provider="fake", model="fake",
                     usage=LLMUsage(prompt_tokens=100, completion_tokens=50))


# ─────────────────────────── rules ───────────────────────────

def test_evaluate_rules_covers_all_domains():
    active = evaluate(CHART)
    assert set(active) == set(DOMAINS)  # every domain has ≥1 active rule
    for d in DOMAINS:
        assert active[d], f"{d} has no rules"


def test_evaluate_rules_saturn_house7_active():
    active = evaluate(CHART)["relationships"]
    assert any(r["factor"] == "Saturn" and (r.get("detail") or {}).get("house") == 7 for r in active)


# ─────────────────────────── prompts ───────────────────────────

def test_build_all_prompts_13_domains():
    prompts = build_all_prompts(CHART)
    assert set(prompts) == set(DOMAINS)
    for d, (p, ctx) in prompts.items():
        assert "فارسی" in p
        assert ctx["domain_title"]


def test_prompt_contains_only_relevant_factors():
    _, ctx = build_all_prompts(CHART)["relationships"]
    assert "Saturn" in ctx["factors"] or "Venus" in ctx["factors"]


# ─────────────────────────── QA ───────────────────────────

def test_parse_section_strips_fences():
    raw = '```json\n' + json.dumps(GOOD_SECTION) + '\n```'
    assert parse_section(raw) == GOOD_SECTION


def test_parse_section_tolerant_prefix():
    raw = "اینجا توضیح اضافه است\n" + json.dumps(GOOD_SECTION)
    assert parse_section(raw) == GOOD_SECTION


def test_qa_section_passes_good():
    assert qa_section(GOOD_SECTION, CHART, "relationships") == []


def test_qa_section_rejects_invented_planet():
    bad = dict(GOOD_SECTION)
    bad["insights"] = [dict(i, evidence=[{"factor": "Zargon"}]) for i in bad["insights"]]
    assert qa_section(bad, CHART, "relationships")


def test_qa_section_rejects_medical_claim():
    bad = dict(GOOD_SECTION)
    bad["insights"] = [dict(i, insight="این بیماری را باید درمان کنید") for i in bad["insights"]]
    assert qa_section(bad, CHART, "relationships")


def test_qa_repetition_detects_duplicates():
    dup = {d: {"insights": [{"insight": "متن تکراری مشترک در همه بخشها"}]} for d in DOMAINS}
    assert qa_repetition(dup)


# ─────────────────────────── generation ───────────────────────────

def test_generate_sections_uses_fake_router():
    from app.report.generator import generate_sections
    sections, metrics = generate_sections(CHART, router=FakeRouter())
    assert len([d for d in sections if sections[d].get("insights")]) == 13
    assert metrics["calls"] == 13
    assert metrics["qa_failures"] == 0
