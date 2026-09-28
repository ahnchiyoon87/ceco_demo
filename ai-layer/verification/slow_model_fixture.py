"""No model output: hold one HTTP request past the production 90-second timeout."""
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):
        # Consume without recording the prompt or authentication header.
        self.rfile.read(int(self.headers.get('Content-Length', '0')))
        print('request_accepted', flush=True)
        time.sleep(180)
        self.close_connection = True


ThreadingHTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
