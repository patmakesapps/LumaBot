"""Local HTTP API for the LumaBot hardware daemon."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from daemon import LumaBotDaemon
from motors import MotorsNotReady


DAEMON = LumaBotDaemon()


class RequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 4096:
            raise ValueError("request body is too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self) -> None:
        if self.path != "/status":
            self.send_error(404)
            return

        self._send_json(200, DAEMON.get_status())

    def do_POST(self) -> None:
        if self.path == "/stop":
            self._send_json(200, {"stopped": True, "status": DAEMON.stop()})
            return
        if self.path == "/indicator/activity":
            try:
                data = self._read_json()
                if not isinstance(data, dict):
                    raise ValueError("request body must be a JSON object")
                result = DAEMON.set_indicator_activity(
                    data.get("lease_id"),
                    data.get("active"),
                    data.get("ttl_s", 10.0),
                )
            except (TypeError, ValueError) as error:
                self._send_json(400, {"error": str(error)})
                return
            self._send_json(200, result)
            return
        if self.path != "/drive":
            self._send_json(404, {"error": "not found"})
            return

        try:
            data = self._read_json()
            result = DAEMON.drive(
                data.get("direction"),
                data.get("speed"),
                data.get("duration_s"),
            )
        except (TypeError, ValueError) as error:
            self._send_json(400, {"error": str(error)})
            return
        except MotorsNotReady as error:
            self._send_json(409, {"error": str(error)})
            return
        self._send_json(202, {"accepted": True, **result})


def serve() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8971), RequestHandler)
    print("LumaBot daemon: http://127.0.0.1:8971")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LumaBot daemon.")
    finally:
        DAEMON.close()
        server.server_close()


if __name__ == "__main__":
    serve()
