from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import sys
import webbrowser
from pathlib import Path

from planner import Model, demo
from export import xlsx

WEB = Path(__file__).resolve().parents[1] / "web"
class Handler(BaseHTTPRequestHandler):
    def send_data(self, payload, kind, status=200, filename=None):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Robots-Tag", "noindex")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(payload)

    def send_json(self, data, status=200):
        self.send_data(json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8", status)

    def do_GET(self):
        if self.path == "/v1/demo":
            return self.send_json(demo())
        static = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
                  "/style.css": ("style.css", "text/css")}
        if self.path not in static:
            return self.send_json({"error": "Página indisponível."}, 404)
        file, kind = static[self.path]
        self.send_data((WEB / file).read_bytes(), kind + "; charset=utf-8")

    def do_POST(self):
        if self.path not in ("/v1/solve", "/v1/validate", "/v1/export"):
            return self.send_json({"error": "Ação indisponível."}, 404)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if self.headers.get_content_type() != "application/json" or not 0 < length <= 200000:
                return self.send_json({"error": "Envie uma configuração JSON de até 200 KB."}, 400)
            body = json.loads(self.rfile.read(length))
            model = Model(body["config"])
            if self.path == "/v1/solve":
                return self.send_json(model.solve())
            assignments = body["assignments"]
            if len(assignments) > 2800:
                raise ValueError("Há alocações demais para o ciclo.")
            report = model.report(assignments)
            if self.path == "/v1/validate":
                return self.send_json(report)
            self.send_data(xlsx(model, report), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           filename="escala-certa-simulacao.xlsx")
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
            message = str(error) if type(error) is ValueError else "Confira os campos da configuração."
            self.send_json({"error": message}, 422)

if __name__ == "__main__":
    port = int(os.environ.get("ESCALA_PORT", "8765"))
    host = os.environ.get("ESCALA_BIND", "127.0.0.1")
    with ThreadingHTTPServer((host, port), Handler) as server:
        url = f"http://{host}:{port}"
        print(f"Escala Certa em {url}", flush=True)
        if "--open" in sys.argv:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


