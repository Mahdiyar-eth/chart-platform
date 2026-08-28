"""Retry antigravity image gen with tight retry loop (quota resets in ~2-3s)."""
import requests, os, base64, time, sys
from dotenv import load_dotenv
load_dotenv("/root/.hermes/.env")
KEY = os.getenv("HERMES_CUSTOM_LOCALHOST_20128_API_KEY")
model = sys.argv[1] if len(sys.argv) > 1 else "antigravity/gemini-3.1-flash-image"
out = sys.argv[2] if len(sys.argv) > 2 else "docs/qa/sketch-ai-glass-390.png"
prompt_file = sys.argv[3] if len(sys.argv) > 3 else "docs/qa/prompt-glass-short.txt"
prompt = open(prompt_file).read()

for attempt in range(40):
    r = requests.post(
        "http://127.0.0.1:20128/v1/images/generations",
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        json={"model": model, "prompt": prompt, "n": 1, "size": "1024x1536"},
        timeout=(10, 240),
    )
    if r.status_code == 200:
        item = (r.json().get("data") or [{}])[0]
        url, b64 = item.get("url"), item.get("b64_json")
        if url:
            img = requests.get(url, timeout=60)
            open(out, "wb").write(img.content)
            print("saved-url", len(img.content))
        elif b64:
            raw = base64.b64decode(b64)
            open(out, "wb").write(raw)
            print("saved-b64", len(raw))
        else:
            print("200 but no image:", str(r.json())[:200])
        break
    # quota resets every few seconds per the 429 message — hammer politely
    time.sleep(4)
else:
    print("exhausted all 40 attempts; last:", r.status_code, r.text[:150])
