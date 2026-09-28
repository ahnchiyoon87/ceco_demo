"""Isolated HTTP Flux-CSV fixture; never connected to the production stack.

High values have BAD quality, or GOOD quality with stale timestamps. This is synthetic integration input,
not a SCADA measurement or a replacement model response. No request headers or
credentials are logged. The caller uses a dummy verification token.
"""
import csv
import io
import json
import os
import re
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

MODE = os.environ.get('OBSERVATION_FIXTURE_MODE', 'bad-quality')
assert MODE in {'bad-quality', 'stale'}, 'Unknown fixture mode'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        bounds = re.search(r'range\(start:time\(v:(\d+)\), stop:time\(v:(\d+)\)\)', body['query'])
        if not bounds:
            self.send_error(400, 'Expected bounded Flux query')
            return
        start, stop = map(int, bounds.groups())
        # A query's future upper bound must not create future measurements.
        age_ns = 20_000_000_000 if MODE == 'stale' else 0
        stop = min(stop, time.time_ns() - age_ns)
        text = io.StringIO()
        writer = csv.writer(text)
        writer.writerow(['_time', 'tag', '_value', 'quality'])
        for ns in range(max(start, stop - 10_000_000_000), stop, 1_000_000_000):
            timestamp = datetime.fromtimestamp(ns / 1e9, timezone.utc).isoformat()
            for tag, value in [('IT-102', 10.4), ('VT-101', 8.3), ('LT-102', 54.0)]:
                writer.writerow([timestamp, tag, value, 'GOOD' if MODE == 'stale' else 'BAD'])
        raw = text.getvalue().encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/csv')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


HTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
