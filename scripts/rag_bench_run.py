"""Phase 5 — RAG benchmark runner: e5-small vs e5-large.
Metrics per category + overall: Recall@5, Recall@10, MRR, nDCG@10.
Ground truth = chunks whose section_key == query category, within the SAME report.
"""
import json, math, re, subprocess, sys, time
sys.path.insert(0, "/root/chart-platform")
from rag_bench_data import CATEGORY_QUERIES

URL = re.search(r'^DATABASE_URL=(.+)$', open("/root/chart-platform/.env").read(), re.M).group(1).strip()

def psql(sql):
    r = subprocess.run(["psql", URL, "-t", "-A", "-c", sql], capture_output=True, text=True)
    return r.stdout.strip()

def load_model(name):
    from sentence_transformers import SentenceTransformer
    t0 = time.monotonic()
    m = SentenceTransformer(name)
    return m, time.monotonic() - t0

def embed(model, texts):
    return model.encode(texts, normalize_embeddings=True).tolist()

def ndcg(rel, k):
    dcg = sum(rel[i] / math.log2(i + 2) for i in range(min(k, len(rel))))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(sum(rel), k)))
    return dcg / ideal if ideal else 0.0

def eval_model(model, reports, queries):
    """queries: list of (report_id, category, text) — 100 x 5 reports = 500 evals/model"""
    results = {c: {"recall5": [], "recall10": [], "mrr": [], "ndcg": []} for c in CATEGORY_QUERIES}
    # load all chunk rows once
    rows = psql("SELECT report_id, section_key, id FROM report_chunks WHERE embedding IS NOT NULL ORDER BY report_id, id")
    chunks = {}
    for line in rows.splitlines():
        rid, sk, cid = line.split("|")
        chunks.setdefault(rid, []).append((sk, cid))
    n = len(queries)
    for idx, (rid, cat, text) in enumerate(queries, 1):
        vec = embed(model, [text])[0]
        vec_str = "[" + ",".join(f"{v:.6f}" for v in vec) + "]"
        sql = (f"SELECT id, section_key, embedding <=> '{vec_str}'::vector AS d "
               f"FROM report_chunks WHERE report_id='{rid}' ORDER BY d LIMIT 10")
        hits = psql(sql)
        ranked = [ln.split("|") for ln in hits.splitlines()]  # id, section_key, dist
        # cosine_distance asc == similarity desc; relevance = section matches category
        rel = [1 if sk == cat else 0 for _, sk, _ in ranked]
        total_rel = sum(rel)
        if total_rel == 0:
            continue
        k5, k10 = sum(rel[:5]), sum(rel[:10])
        results[cat]["recall5"].append(k5 / total_rel)
        results[cat]["recall10"].append(k10 / total_rel)
        results[cat]["mrr"].append(1 / next(i for i, x in enumerate(rel, 1) if x))
        results[cat]["ndcg"].append(ndcg(rel, 10))
        if idx % 100 == 0:
            print(f"  {idx}/{n} done", flush=True)
    agg = {}
    for c, m in results.items():
        agg[c] = {k: round(sum(v) / len(v), 4) if v else 0 for k, v in m.items()}
    return agg

def main():
    # 5 reports with full 40 chunks, deterministic order
    rep = psql("SELECT report_id FROM report_chunks GROUP BY report_id HAVING COUNT(*)=40 ORDER BY report_id LIMIT 5").splitlines()
    queries = []
    for rid in rep:
        for cat, qs in CATEGORY_QUERIES.items():
            for q in qs:
                queries.append((rid, cat, q))
    print(f"reports={len(rep)} queries={len(queries)}", flush=True)
    out = {}
    cache = "/tmp/rag_bench_cache.json"
    try:
        out = json.load(open(cache))
    except Exception:
        pass
    for name in ("intfloat/multilingual-e5-small", "intfloat/multilingual-e5-large"):
        if name in out:
            print(f"{name}: cached", flush=True)
            continue
        print(f"loading {name} ...", flush=True)
        model, t_load = load_model(name)
        t0 = time.monotonic()
        agg = eval_model(model, rep, queries)
        out[name] = {"load_s": round(t_load, 1), "eval_s": round(time.monotonic() - t0, 1), "categories": agg}
        json.dump(out, open(cache, "w"))
        print(f"{name} done in {agg['eval_s']}s", flush=True)
    print(json.dumps(out, ensure_ascii=False, indent=1))

if __name__ == "__main__":
    main()