#!/usr/bin/env python3
import sys, os
from http.server import HTTPServer, BaseHTTPRequestHandler

class CORSHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.lstrip('/')
        base = os.path.join(os.path.dirname(__file__), 'public')
        fpath = os.path.join(base, path)
        if not os.path.exists(fpath):
            self.send_response(404); self.end_headers(); return
        with open(fpath, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', 'application/javascript; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def log_message(self, fmt, *args):
        print(fmt % args)

port = 8765
print(f'Serving D:/FISH/fish-sync/public/ on http://localhost:{port}/')
HTTPServer(('', port), CORSHandler).serve_forever()
