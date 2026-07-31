"""Local HTTP API for the LumaBot hardware daemon."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from daemon import LumaBotDaemon


DAEMON = LumaBotDaemon()


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/status":
            self.send_error(404)
            return

        body = json.dumps(DAEMON.get_status()).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8971), RequestHandler)
    print("LumaBot daemon: http://127.0.0.1:8971")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LumaBot daemon.")
    finally:
        server.server_close()


if __name__ == "__main__":
    serve()
