"""Small real HTTP status relay used as the specimen's acceptance target.

The separate process reloads its configuration and serves the station request.
It is a laboratory service, not a deployed or simulated military system.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import uuid

parser = argparse.ArgumentParser()
parser.add_argument("--workspace", type=Path, required=True)
parser.add_argument("--metadata", type=Path, required=True)
args = parser.parse_args()
started = time.monotonic()
last_request = started
lock = threading.Lock()
loaded = {"digest": None, "mode": "unavailable", "loadedAt": None}


def reload_configuration():
    while True:
        try:
            raw = (args.workspace / "document.txt").read_bytes()
            config = dict(line.split(" = ", 1) for line in raw.decode().splitlines() if " = " in line)
            digest = hashlib.sha256(raw).hexdigest()
            with lock:
                if loaded["digest"] != digest:
                    loaded.update(digest=digest, mode=config.get("service_mode", "maintenance"), loadedAt=int(time.time() * 1000))
        except (OSError, UnicodeError, ValueError):
            with lock:
                loaded.update(digest=None, mode="unavailable")
        time.sleep(0.1)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        global last_request
        last_request = time.monotonic()
        if self.path != "/station-status":
            self.send_error(404)
            return
        with lock:
            observed = dict(loaded)
        ready = observed["mode"] == "active"
        body = json.dumps({"service": "site-status-relay", "site": "support-site-01", "status": "serving" if ready else "maintenance", "configurationSha256": observed["digest"], "configurationLoadedAt": observed["loadedAt"], "requestId": str(uuid.uuid4()), "uptimeSeconds": round(time.monotonic() - started, 3)}).encode()
        self.send_response(200 if ready else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
def expire_idle_relay():
    while time.monotonic() - last_request < 7200:
        time.sleep(30)
    server.shutdown()
threading.Thread(target=expire_idle_relay, daemon=True).start()
threading.Thread(target=reload_configuration, daemon=True).start()
args.metadata.write_text(json.dumps({"port": server.server_port, "service": "site-status-relay"}))
server.serve_forever()
