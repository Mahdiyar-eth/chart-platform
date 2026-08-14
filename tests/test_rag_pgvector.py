"""D2 (audit r4): pgvector RAG — chunking, indexing (idempotent), and
cosine retrieval over report chunks. The embedding model is MOCKED here
(no 100MB+ download in tests); a real-model smoke lives in scripts/rag_smoke.py.
"""
import sys

from sqlmodel import Session, select

sys.path.insert(0, "/root/chart-platform")
from app.db import engine
from app.models import Chart, Report, ReportChunk
import app.rag as rag


def _seed_done_report() -> str:
    with Session(engine) as s:
        ch = Chart(profile_id=None, chart_json={"planets": {}})
        s.add(ch)
        s.commit()
        s.refresh(ch)
        rep = Report(chart_id=ch.id, status="done", plan_key="full", sections={
            "love": {"summary": "ماه در خانه هشتم، پیوندهای عاطفی عمیق و محرمانه.",
                     "insights": [{"insight": "ناهید در مقارنه با کیوان: عشق مسئولانه."}]},
            "career": {"summary": "خورشید در خانه دهم، مسیر حرفهای روشن.",
                       "insights": [{"insight": "تیر در سهگانه با مشتری: ارتباطات مؤثر."}]},
        })
        s.add(rep)
        s.commit()
        return rep.id


def test_chunking_splits_long_sections():
    long_text = "جمله " * 300  # 900+ chars
    chunks = rag.chunk_report_text({"career": {"summary": long_text}})
    assert chunks, "long section must produce chunks"
    assert all(len(t) <= rag.CHUNK_SIZE + rag.CHUNK_OVERLAP for _, t in chunks)
    # chunk boundaries must not exceed the source text length
    joined = " ".join(t for _, t in chunks)
    assert "جمله" in joined


def test_index_report_idempotent(monkeypatch):
    calls = {"n": 0}

    class FakeModel:
        def encode(self, texts, **kw):
            calls["n"] += 1
            return [[0.1] * 384 for _ in texts]

    monkeypatch.setattr(rag, "_model_instance", lambda: FakeModel())
    rid = _seed_done_report()
    n1 = rag.index_report(rid)
    assert n1 >= 2
    n2 = rag.index_report(rid)  # idempotent — already indexed
    assert n2 == 0
    with Session(engine) as s:
        stored = s.exec(select(ReportChunk).where(
            ReportChunk.report_id == rid)).all()
        assert len(stored) == n1
        assert stored[0].embedding and len(stored[0].embedding) == 384
    _cleanup(rid)


def test_search_returns_ranked_chunks(monkeypatch):
    vec = [0.0] * 384
    vec[0] = 1.0  # question vector
    monkeypatch.setattr(rag, "_model_instance",
                        lambda: type("M", (), {"encode": lambda self, t, **k: [vec]})())
    rid = _seed_done_report()
    # seed chunks with distinct embeddings via direct rows (model mocked above)
    with Session(engine) as s:
        s.add(ReportChunk(report_id=rid, chunk_index=0, section_key="love",
                          text="عشق و محبت", embedding=[0.9] + [0.0] * 383))
        s.add(ReportChunk(report_id=rid, chunk_index=1, section_key="career",
                          text="کار و شغل", embedding=[-0.9] + [0.0] * 383))
        s.commit()
    hits = rag.search_relevant(rid, "درباره عشق بگو", top_k=1)
    assert hits == ["عشق و محبت"], "cosine similarity must rank the love chunk first"
    _cleanup(rid)


def _cleanup(rid: str) -> None:
    with Session(engine) as s:
        for rc in s.exec(select(ReportChunk).where(
                ReportChunk.report_id == rid)).all():
            s.delete(rc)
        rep = s.get(Report, rid)
        ch = s.get(Chart, rep.chart_id) if rep else None
        if rep:
            s.delete(rep)
            s.flush()  # C6 lesson: unitofwork doesn't order FK deletes
        if ch:
            s.delete(ch)
        s.commit()
