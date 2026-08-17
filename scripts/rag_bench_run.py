"""Phase 5 — RAG benchmark runner v2: e5-small vs e5-large (fixed dim mismatch).

Each model embeds the SAME chunk texts into its own temp table (small=384,
large=1024) so the SQL comparison is dimension-correct. psql failures now
surface stderr instead of being swallowed (root cause of the all-zero run).
Metrics: Recall@5/10, MRR, nDCG@10 — ground truth = section_key == category.
"""
import json, math, re, subprocess, sys, time
sys.path.insert(0, "/root/chart-platform")
from rag_bench_data import CATEGORY_QUERIES

URL = re.search(r'^DATABASE_URL=(.+)$', open("/root/chart-platform/.env").read(), re.M).group(1).strip()

def psql(sql):
    r = subprocess.run(["psql", URL, "-t", "-A", "-c", sql], capture_output=True, text=True)
    if r.stderr.strip() and "NOTICE" not in r.stderr:
        raise RuntimeError(f"psql: {r.stderr.strip()[:200]}")
    return r.stdout.strip()

def load_model(name):
    from sentence_transformers import SentenceTransformer
    t0 = time.monotonic()
    m = SentenceTransformer(name)
    return m, time.monotonic() - t0

def ndcg(rel, k):
    dcg = sum(rel[i] / math.log2(i + 2) for i in range(min(k, len(rel))))
    ideal = sum(1 / math.log2(i + 2) for i in range(min(sum(rel), k)))
    return dcg / ideal if ideal else 0.0

def eval_model(name, model, queries):
    """Embed all chunk texts into a temp table once, then run 1000 queries."""
    psql("DROP TABLE IF EXISTS _rag_bench_vec")
    psql("CREATE TABLE _rag_bench_vec (report_id text, section_key text, embedding vector(384))"
         if name.endswith("small") else
         "CREATE TABLE _rag_bench_vec (report_id text, section_key text, embedding vector(1024))")
    rows = psql("SELECT report_id, section_key, text FROM report_chunks WHERE embedding IS NOT NULL ORDER BY report_id, id")
    texts, meta = [], []
    for line in rows.splitlines():
        rid, sk, text = line.split("|", 2)
        meta.append((rid, sk))
        texts.append(text)
    print(f"  {name}: encoding {len(texts)} chunks", flush=True)
    vecs = model.encode(texts, normalize_embeddings=True, batch_size=64)
    # batch-insert via one big INSERT (chunked to stay under psql arg limits)
    CH = 25 if name.endswith("small") else 12  # 1024-dim * 25 rows > 128KB arg cap
    for i in range(0, len(meta), CH):
        vals = []
        for j in range(i, min(i + CH, len(meta))):
            rid, sk = meta[j]
            v = "[" + ",".join(f"{x:.6f}" for x in vecs[j]) + "]"
            vals.append(f"('{rid}','{sk}','{v}'::vector)")
        psql("INSERT INTO _rag_bench_vec (report_id, section_key, embedding) VALUES " + ",".join(vals))
    results = {c: {"recall5": [], "recall10": [], "mrr": [], "ndcg": []} for c in CATEGORY_QUERIES}
    n = len(queries)
    t0 = time.monotonic()
    for idx, (rid, cat, text) in enumerate(queries, 1):
        vec = model.encode([text], normalize_embeddings=True)[0]
        v = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
        hits = psql(
            f"SELECT section_key FROM _rag_bench_vec WHERE report_id='{rid}' "
            f"ORDER BY embedding <=> '{v}'::vector LIMIT 10")
        if not hits:
            print(f"  WARN: no rows for {rid} at {idx}")
            continue
        ranked = hits.splitlines()
        rel = [1 if sk == cat else 0 for sk in ranked]
        total_rel = sum(rel)
        if total_rel == 0:
            continue
        k5, k10 = sum(rel[:5]), sum(rel[:10])
        results[cat]["recall5"].append(k5 / total_rel)
        results[cat]["recall10"].append(k10 / total_rel)
        results[cat]["mrr"].append(1 / next(i for i, x in enumerate(rel, 1) if x))
        results[cat]["ndcg"].append(ndcg(rel, 10))
        if idx % 250 == 0:
            print(f"  {idx}/{n} done ({time.monotonic()-t0:.0f}s)", flush=True)
    agg = {}
    for c, m in results.items():
        agg[c] = {k: round(sum(v) / len(v), 4) if v else 0 for k, v in m.items()}
    agg["__overall"] = {}
    for k in ("recall5", "recall10", "mrr", "ndcg"):
        vals_all = [x for c in CATEGORY_QUERIES for x in results[c][k]]
        agg["__overall"][k] = round(sum(vals_all) / len(vals_all), 4) if vals_all else 0
    return agg

def main():
    rep = psql("SELECT report_id FROM report_chunks GROUP BY report_id HAVING COUNT(*)=40 ORDER BY report_id LIMIT 5").splitlines()
    queries = [(rid, cat, q) for rid in rep for cat, qs in CATEGORY_QUERIES.items() for q in qs]
    print(f"reports={len(rep)} queries={len(queries)}", flush=True)
    out = {}
    try:
        out = json.load(open("/tmp/rag_bench_cache.json"))
    except Exception:
        pass
    for name in ("intfloat/multilingual-e5-small", "intfloat/multilingual-e5-large"):
        if name in out:
            print(f"{name}: cached", flush=True)
            continue
        print(f"loading {name} ...", flush=True)
        model, t_load = load_model(name)
        t0 = time.monotonic()
        agg = eval_model(name, model, queries)
        out[name] = {"load_s": round(t_load, 1), "eval_s": round(time.monotonic() - t0, 1), "categories": agg}
        json.dump(out, open("/tmp/rag_bench_cache.json", "w"), ensure_ascii=False, indent=1)
        print(f"  {name} done: overall={agg['__overall']}", flush=True)
    json.dump(out, open("/tmp/rag_bench_results.json", "w"), ensure_ascii=False, indent=1)
    print("SAVED /tmp/rag_bench_results.json", flush=True)

if __name__ == "__main__":
    main()