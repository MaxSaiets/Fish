"""
Локальний HTTP-сервер що віддає public/ для:
  - Horoshop ← http://<host>:8080/horoshop.xml
  - Rozetka  ← http://<host>:8080/rozetka.xml
  - Facebook ← http://<host>:8080/facebook.xml
  - photos   ← http://<host>:8080/photos/<kod>/<n>.jpg

Запуск:
  python src/serve.py                  # http://0.0.0.0:8080
  python src/serve.py --port 9000

Для production-доступу ззовні (Horoshop тягне URL):
  - тимчасово: ngrok http 8080 → отримати https-URL → вставити в Horoshop admin
  - постійно: запустити на VPS, прописати домен / Cloudflare Tunnel
"""
from __future__ import annotations

import argparse
import http.server
import socketserver
from pathlib import Path

PUBLIC = Path(r"D:\FISH\fish-sync\public")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def end_headers(self):
        # Дозволяємо CDN/Horoshop тягнути файли крос-домен
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "public, max-age=300")
        super().end_headers()

    def log_message(self, fmt, *args):
        # Тихий лог
        print(f"[serve] {self.address_string()} {fmt % args}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    PUBLIC.mkdir(parents=True, exist_ok=True)
    print(f"Serving {PUBLIC} on http://{args.host}:{args.port}")
    print("Endpoints:")
    print(f"  http://localhost:{args.port}/horoshop.xml")
    print(f"  http://localhost:{args.port}/rozetka.xml")
    print(f"  http://localhost:{args.port}/facebook.xml")
    print(f"  http://localhost:{args.port}/photos/...")
    with socketserver.ThreadingTCPServer((args.host, args.port), Handler) as srv:
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nstopping")


if __name__ == "__main__":
    main()
