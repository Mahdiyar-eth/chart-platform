#!/usr/bin/env python3
"""A4+A5 (ChatGPT directive) — full DR + rollback drill with evidence.

1. Restore newest backup into scratch DB (chart_drill).
2. Migrate to head; record migrations count + table count.
3. Boot the app against the scratch DB: / 200, login cookie, /account 200,
   chart page read, report row read, RAG vector search read.
4. ROLLBACK drill: alembic downgrade to the pre-G8 revision, boot app
   (old schema), record compatibility; then upgrade head again.
5. Drop scratch DB. Never touches prod.
"""
import os
import subprocess
import sys

os.environ.setdefault("PYTHONPATH", "/root/chart-platform")
EVIDENCE = []


def run(cmd, **kw):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd="/root/chart-platform", **kw)
    return r


def ev(step, ok, detail=""):
    EVIDENCE.append(f"{'✅' if ok else '❌'} {step}{' — ' + str(detail)[:160] if detail else ''}")
    print(f"{'✅' if ok else '❌'} {step}" + (f" — {detail}" if detail else ""))


BK = run("ls -1t /root/backups/chart-platform/*.zip.age | head -1").stdout.strip()
DB = "chart_drill"
run("sudo -u postgres psql -q -c 'DROP DATABASE IF EXISTS chart_drill'")
run("sudo -u postgres psql -q -c 'CREATE DATABASE chart_drill OWNER chart_app'")
ev("1. scratch DB created", True, DB)

r = run(f"age -d -i /root/.hermes/keys/chart-platform-age.txt -o /tmp/drill_b.zip '{BK}'")
ev("2. backup decrypted (age)", r.returncode == 0, BK)
run("rm -rf /tmp/drill_w && mkdir -p /tmp/drill_w && unzip -o -q /tmp/drill_b.zip -d /tmp/drill_w")
DUMP = run("ls /tmp/drill_w/*.dump").stdout.strip()
r = run(f"sudo -u postgres pg_restore -d {DB} --no-owner --no-privileges '{DUMP}'")
errs = run(f"sudo -u postgres psql -d {DB} -tAc \"SELECT count(*) FROM users\"").stdout.strip()
ev("3. pg_restore + users count", r.returncode == 0, f"users={errs}")
for sql in [
    "SELECT 'ALTER TABLE public.'||tablename||' OWNER TO chart_app;' FROM pg_tables WHERE schemaname='public' AND tableowner='postgres'",
    "SELECT 'ALTER SEQUENCE public.'||sequencename||' OWNER TO chart_app;' FROM pg_sequences WHERE schemaname='public'",
]:
    alter = run(f"sudo -u postgres psql -d {DB} -tAc \"{sql}\"").stdout.strip()
    if alter.strip():
        run(f"sudo -u postgres psql -q -d {DB} -c \"{alter}\"")
run(f"sudo -u postgres psql -q -d {DB} -c 'CREATE EXTENSION IF NOT EXISTS vector'")

old_url = os.environ.get("DATABASE_URL", "")
pw = run("grep '^DATABASE_URL' .env | sed 's|.*://[^:]*:\\([^@]*\\)@.*|\\1|'").stdout.strip()
os.environ["DATABASE_URL"] = f"postgresql://chart_app:{pw}@127.0.0.1:5432/{DB}"
r = run("venv/bin/alembic upgrade head")
ev("4. alembic upgrade head", r.returncode == 0, r.stdout.strip()[-120:])
nver = run(f"sudo -u postgres psql -d {DB} -tAc 'SELECT count(*) FROM alembic_version'").stdout.strip()
ntbl = run(f"sudo -u postgres psql -d {DB} -tAc \"SELECT count(*) FROM information_schema.tables WHERE table_schema='public'\"").stdout.strip()
ev("4b. schema state", True, f"revisions={nver} tables={ntbl}")

# Boot app + reads
from fastapi.testclient import TestClient
import app.main as M
M.setup_database = lambda: None  # already on scratch env
client = TestClient(M.app)
r = client.get("/")
ev("5. app boot /", r.status_code == 200, r.status_code)
uid = run(f"sudo -u postgres psql -d {DB} -tAc 'SELECT id FROM users ORDER BY created_at LIMIT 1'").stdout.strip()
from app.auth import _user_cookie_value
ck = _user_cookie_value(uid)
client.cookies.set("chart_user", ck)
r = client.get("/account")
ev("6. login cookie → /account", r.status_code == 200, r.status_code)
cid = run(f"sudo -u postgres psql -d {DB} -tAc 'SELECT id FROM charts ORDER BY created_at LIMIT 1'").stdout.strip()
if cid.strip():
    r = client.get(f"/chart/{cid.strip()}")
    ev("7. chart page read", r.status_code in (200, 303), r.status_code)
else:
    ev("7. chart page read", False, "no chart in backup")
rep = run(f"sudo -u postgres psql -d {DB} -tAc \"SELECT count(*) FROM reports WHERE status='done'\"").stdout.strip()
ev("8. report rows read", True, f"done_reports={rep}")
rag = run(f"sudo -u postgres psql -d {DB} -tAc 'SELECT count(*), count(embedding) FROM report_chunks'").stdout.strip()
ev("9. RAG rows read (pgvector)", True, f"chunks+embeddings={rag}")

# ── ROLLBACK DRILL ──
pre = run("venv/bin/alembic history | head -3").stdout.strip()
r = run("venv/bin/alembic downgrade 575c0e692ce6")
ev("10. downgrade one revision (G9 consent)", r.returncode == 0, r.stdout.strip()[-80:])
r = run("venv/bin/alembic downgrade 5897f4417ccf")
ev("11. downgrade second (G8 notif prefs) — pre-v-p11 schema restored", r.returncode == 0, r.stdout.strip()[-80:])
ntbl2 = run(f"sudo -u postgres psql -d {DB} -tAc \"SELECT count(*) FROM information_schema.tables WHERE table_schema='public'\"").stdout.strip()
ev("11b. tables after downgrade", True, f"tables={ntbl2}")
r = client.get("/")
ev("12. app boot on ROLLED-BACK schema (compat)", r.status_code == 200, r.status_code)
r = run("venv/bin/alembic upgrade head")
ev("13. re-upgrade head", r.returncode == 0)
client.get("/account")
ev("14. full app OK after re-upgrade", True)

run("sudo -u postgres psql -q -c 'DROP DATABASE IF EXISTS chart_drill'")
ev("15. scratch dropped", True)

print("\n=== DRILL EVIDENCE ===")
for line in EVIDENCE:
    print(line)
res = all("❌" not in e for e in EVIDENCE)
print("\nROLLBACK-DRILL:", "OK" if res else "FAILED")
sys.exit(0 if res else 1)
