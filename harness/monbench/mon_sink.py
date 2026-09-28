"""Alertmanager 웹훅 수신기(측정 도구). 받은 본문을 한 줄씩 SINK_OUT 에 붙인다."""
import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

OUT = os.environ.get("SINK_OUT", "/experiments/EXP-MON/raw/sink.jsonl")
os.makedirs(os.path.dirname(OUT), exist_ok=True)


class H(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps({"recv_epoch": time.time(), "body": json.loads(body or b"{}")}, ensure_ascii=False) + "\n")
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


HTTPServer(("0.0.0.0", 8080), H).serve_forever()
