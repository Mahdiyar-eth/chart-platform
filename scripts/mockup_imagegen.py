"""Generate UI mockup images via OmniRoute (chat/completions image modality)."""
import requests, os, base64, time, sys
from dotenv import load_dotenv
load_dotenv("/root/.hermes/.env")
KEY = os.getenv("HERMES_CUSTOM_LOCALHOST_20128_API_KEY", "")
BASE = "http://127.0.0.1:20128/v1"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini/gemini-3.1-flash-image"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/root/chart-platform/docs/qa/sketch-ai.png"
PROMPT_FILE = sys.argv[3]

prompt = open(PROMPT_FILE, encoding="utf-8").read()
t0 = time.time()
r = requests.post(
    f"{BASE}/chat/completions",
    headers={"Accept": "application/json", "Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    json={"model": MODEL, "modalities": ["image", "text"],
          "messages": [{"role": "user", "content": prompt}]},
    timeout=(10, 240),
)
print("status:", r.status_code, f"{time.time()-t0:.0f}s")
d = r.json()
choices = d.get("choices") or [{}]
parts = (choices[0].get("message") or {}).get("images") or []
if parts:
    url = parts[0].get("image_url", {}).get("url", "")
    print("image data prefix:", url[:40], "len:", len(url))
    if url.startswith("data:"):
        b64 = url.split(",", 1)[1]
        open(OUT, "wb").write(base64.b64decode(b64))
        print("saved:", OUT)
else:
    msg = choices[0].get("message", {})
    print("no images; content head:", str(msg.get("content"))[:200])
