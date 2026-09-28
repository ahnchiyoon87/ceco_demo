"""Publish a reviewed batch through the V1 review path: preview (digest) → publish. Measurement tool, not a product part."""
import json, sys, urllib.request

base = "http://127.0.0.1:38000/api/knowledge"
batch = json.load(open(sys.argv[1], encoding="utf-8"))
note = sys.argv[2]


def post(path, body):
    req = urllib.request.Request(base + path, json.dumps(body, ensure_ascii=False).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{path} {e.code}: {e.read().decode()[:800]}")


preview = post("/preview", batch)
result = post("/publish", {"batch": preview["batch"], "expected_sha256": preview["sha256"], "review_note": note})
print(json.dumps(result, ensure_ascii=False))
