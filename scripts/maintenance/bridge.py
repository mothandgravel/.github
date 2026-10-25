"""Persistent POSIX adapter bridge; avoids per-action Windows/WSL startup."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import os
import threading

parser = argparse.ArgumentParser()
parser.add_argument("--ajo-root", required=True)
parser.add_argument("--hosts", required=True)
parser.add_argument("--data-root", required=True)
parser.add_argument("--port", type=int, default=8797)
parser.add_argument("--manifest", required=True)
args = parser.parse_args()
adapter = Path(args.data_root).parent / "adapter"
adapter.mkdir(parents=True, exist_ok=True)
for filename in ("runtime.py", "relay.py", "contracts.py"):
    shutil.copyfile(Path(__file__).with_name(filename), adapter / filename)
adapter_digest = hashlib.sha256(b"".join(Path(__file__).with_name(name).read_bytes() for name in ("bridge.py", "runtime.py", "relay.py", "contracts.py"))).hexdigest()
manifest = json.loads(Path(args.manifest).read_text())
expected_files = [item for item in manifest["files"] if item["repo"] == "ajo"]
def checked_sources():
    observed = [{**item, "sha256": hashlib.sha256((Path(args.ajo_root) / item["path"]).read_bytes()).hexdigest()} for item in expected_files]
    if observed != expected_files:
        raise ValueError("Ajo runtime source differs from the pinned file hashes")
    return observed

observed_files = checked_sources()
# Build from the verified native source at bridge startup, then bind its bytes.
standard_library = next((Path(args.hosts) / "usr/lib").rglob("stdlib.cmi")).parent
build_env = {**os.environ, "AJO_WORKSPACE": args.ajo_root, "AJO_HOST_TOOLS_ROOT": str(Path(args.hosts) / "usr"), "PYTHONPATH": str(Path(args.ajo_root) / "src"), "OCAMLLIB": str(standard_library), "CAML_LD_LIBRARY_PATH": str(standard_library / "stublibs")}
build = subprocess.run([sys.executable, "-c", "from ajo.evaluation.runner import build_ocaml, host_executable; import subprocess; build_ocaml(); print(subprocess.check_output([host_executable('ocamlc', override='AJO_OCAMLC'), '-version'], text=True).strip())"], env=build_env, capture_output=True, text=True, check=True)
compiler_version = build.stdout.strip().splitlines()[-1]
binary = Path(args.ajo_root) / "build/native/engine-ocaml-bytecode"
binary_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
configuration_hash = hashlib.sha256(json.dumps([args.ajo_root, args.hosts, args.data_root], separators=(",", ":")).encode()).hexdigest()
action_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def reply(self, value, status=200):
        raw = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        self.reply({"service": "mg-maintenance-bridge", "version": 1, "adapterSha256": adapter_digest, "configurationSha256": configuration_hash, "files": checked_sources(), "binarySha256": binary_hash, "ocamlVersion": compiler_version}, 200 if self.path == "/health" else 404)

    def do_POST(self):
        if self.path != "/action" or self.headers.get("X-MG-Bridge") != "1" or self.headers.get("Origin"):
            return self.reply({"error": "host bridge requests only"}, 403)
        if not action_lock.acquire(blocking=False):
            return self.reply({"error": "another native action is in progress; reconcile after it settles"}, 409)
        try:
            checked_sources()
            if hashlib.sha256(binary.read_bytes()).hexdigest() != binary_hash:
                raise ValueError("native evaluator bytes changed since bridge startup")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 1024:
                raise ValueError("invalid request size")
            body = json.loads(self.rfile.read(length))
            if body.get("command") not in {"create", "check", "dispatch", "recover", "verify", "snapshot"}:
                raise ValueError("invalid command")
            command = [sys.executable, str(adapter / "runtime.py"), "--ajo-root", args.ajo_root, "--hosts", args.hosts, "--data-root", args.data_root, "--run", body["run"], "--command", body["command"], "--scenario", body.get("scenario", "lost-reply")]
            if body["command"] == "dispatch":
                command += ["--approved-plan-sha256", body.get("approvedPlanSha256", "")]
            result = subprocess.run(command, text=True, capture_output=True, timeout=40)
            if result.returncode:
                raise RuntimeError(result.stderr[-1200:])
            self.reply(json.loads(result.stdout))
        except (KeyError, ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            self.reply({"error": str(error)}, 400)
        finally:
            action_lock.release()

    def log_message(self, *_):
        pass


ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
