"""pgvector RAG (D2): chunk finished reports, embed with multilingual-e5,
store in report_chunks (HNSW index), and retrieve the most relevant chunks
for grounded chat answers.

The embedding model is loaded lazily and only inside the ARQ worker path —
the web process never pays the model memory cost.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.db import engine
from app.models import Report, ReportChunk

log = logging.getLogger("rag")

CHUNK_SIZE = 512          # characters per chunk
CHUNK_OVERLAP = 64        # overlap between consecutive chunks
MAX_CHUNKS_PER_REPORT = 40

_model = None

# D2: multilingual-e5-small (~118MB RSS) is the safe default for the web
# process (2 uvicorn workers × 2GB free RAM); e5-large (1.2GB/worker) would
# OOM — override with RAG_MODEL=... if the server is ever upgraded.
RAG_MODEL_NAME = os.getenv("RAG_MODEL", "intfloat/multilingual-e5-small")
RAG_EMBEDDING_DIM = int(os.getenv("RAG_EMBEDDING_DIM", "384"))


def _model_instance():
    """Lazy singleton — CPU inference on the worker."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(RAG_MODEL_NAME)
    return _model


def chunk_report_text(sections: dict) -> list[tuple[str, str]]:
    """Split report sections into (section_key, text) chunks (deterministic)."""
    chunks: list[tuple[str, str]] = []
    for key, sec in (sections or {}).items():
        parts = []
        if isinstance(sec, dict):
            for k in ("summary", "insights", "challenges", "recommendations"):
                v = sec.get(k)
                if isinstance(v, str) and v.strip():
                    parts.append(v.strip())
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, dict):
                            parts.append(item.get("insight") or item.get("text") or "")
                        elif isinstance(item, str):
                            parts.append(item)
        text = "\n".join(p for p in parts if p)
        if not text:
            continue
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        if len(text) <= CHUNK_SIZE:
            chunks.append((key, text))
            continue
        start = 0
        while start < len(text) and len(chunks) < MAX_CHUNKS_PER_REPORT:
            end = min(start + CHUNK_SIZE, len(text))
            if end < len(text):
                # break at the last whitespace inside the window
                cut = text.rfind(" ", start, end)
                if cut > start + CHUNK_SIZE // 2:
                    end = cut
            chunks.append((key, text[start:end].strip()))
            start = end - CHUNK_OVERLAP
    return chunks[:MAX_CHUNKS_PER_REPORT]


def index_report(report_id: str) -> int:
    """Embed + persist chunks for a finished report. Idempotent per report."""
    with Session(engine) as s:
        rep = s.get(Report, report_id)
        if not rep or rep.status != "done":
            return 0
        existing = s.exec(select(ReportChunk).where(
            ReportChunk.report_id == report_id)).first()
        if existing:
            return 0  # already indexed
        chunks = chunk_report_text(rep.sections)
        if not chunks:
            return 0
        texts = [t for _, t in chunks]
        vectors = _model_instance().encode(texts, normalize_embeddings=True,
                                           show_progress_bar=False)
        for i, ((sec_key, _), vec) in enumerate(zip(chunks, vectors)):
            emb = vec.tolist() if hasattr(vec, "tolist") else list(vec)
            s.add(ReportChunk(report_id=report_id, chunk_index=i,
                              section_key=sec_key, text=texts[i],
                              embedding=emb))
        s.commit()
        log.info("indexed report %s: %d chunks", report_id[:8], len(chunks))
        return len(chunks)


def search_relevant(report_id: str, question: str, top_k: int = 3) -> list[str]:
    """Cosine-similarity retrieval over the report's chunks (HNSW)."""
    with Session(engine) as s:
        if not s.exec(select(ReportChunk).where(
                ReportChunk.report_id == report_id)).first():
            return []
        raw = _model_instance().encode(
            [question], normalize_embeddings=True)[0]
        vec = raw.tolist() if hasattr(raw, "tolist") else list(raw)
        rows = s.exec(
            select(ReportChunk)
            .where(ReportChunk.report_id == report_id,
                   ReportChunk.embedding.is_not(None))
            .order_by(ReportChunk.embedding.cosine_distance(vec))
            .limit(top_k)
        ).all()
        return [r.text for r in rows]


def prune_old_chunks(days: int = 180) -> int:
    """Retention (C6): drop chunks whose report was created more than N days ago."""
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    deleted = 0
    with Session(engine) as s:
        for rc in s.exec(select(ReportChunk)).all():
            rep = s.get(Report, rc.report_id)
            if not rep or rep.created_at.timestamp() < cutoff:
                s.delete(rc)
                deleted += 1
        s.commit()
    return deleted


if __name__ == "__main__":  # pragma: no cover — manual maintenance
    import sys
    print("pruned:", prune_old_chunks())
    if len(sys.argv) > 1:
        print("indexed:", index_report(sys.argv[1]))
