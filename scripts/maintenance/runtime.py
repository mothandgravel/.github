"""Local specimen adapter. Ajo's unchanged native evaluator owns plan execution.

Only a newly created bench directory and its document.txt can be changed.
This controller is not a substitute evaluator or a physical service controller.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import subprocess
import shutil
import urllib.error
import urllib.request
from contracts import public_evidence, require_approved_plan, observe_loaded_configuration

PARSER = argparse.ArgumentParser()
PARSER.add_argument("--ajo-root", type=Path, required=True)
PARSER.add_argument("--data-root", type=Path, required=True)
PARSER.add_argument("--hosts", type=Path, required=True)
PARSER.add_argument("--run", required=True)
PARSER.add_argument("--command", choices=["create", "check", "dispatch", "recover", "verify", "snapshot"], required=True)
PARSER.add_argument("--scenario", choices=["lost-reply", "acceptance-held"], default="lost-reply")
PARSER.add_argument("--approved-plan-sha256")


def main():
    args = PARSER.parse_args()
    if not re.fullmatch(r"[a-f0-9]{32}", args.run):
        raise ValueError("invalid bench identity")
    os.environ["AJO_WORKSPACE"] = str(args.ajo_root.resolve())
    os.environ["AJO_HOST_TOOLS_ROOT"] = str(args.hosts.resolve() / "usr")
    standard_library = next((args.hosts.resolve() / "usr/lib").rglob("stdlib.cmi")).parent
    os.environ["OCAMLLIB"] = str(standard_library)
    os.environ["CAML_LD_LIBRARY_PATH"] = str(standard_library / "stublibs")
    sys.path.insert(0, str(args.ajo_root / "src"))
    os.environ["PYTHONPATH"] = str(args.ajo_root / "src")
    from ajo.evaluation.runner import decode, invoke
    from ajo.filesystem.receiver import durable_json
    from ajo.filesystem.supervisor import await_result, call, literal, request, sequence
    from ajo.filesystem.tools import context

    root = args.data_root.resolve() / args.run
    record_file = root / "bench.json"
    if args.command == "create":
        root.mkdir(parents=True, exist_ok=False)
        (root / "workspace").mkdir()
        (root / "receiver").mkdir(mode=0o700)
        baseline = "station = support-site-01\nconfiguration = baseline\nservice_mode = maintenance\n"
        target = "station = support-site-01\nconfiguration = reviewed-02\nservice_mode = " + ("maintenance" if args.scenario == "acceptance-held" else "active") + "\n"
        (root / "workspace/document.txt").write_text(baseline)
        payload = {"path": "document.txt", "expected_sha256": hashlib.sha256(baseline.encode()).hexdigest(), "content": target}
        plan = {"language": 1, "revision": 1, "inputs": [], "limits": {"dispatches": 6, "attempts": 1}, "tree": sequence("maintenance", call("replace", "apply", "apply-h", literal(payload)), await_result("apply-h", "await-apply", "apply-o"))}
        record = {"runId": args.run, "session": "m" + args.run, "scenario": args.scenario, "payload": payload, "targetSha256": hashlib.sha256(target.encode()).hexdigest(), "plan": plan, "actions": [], "verification": None}
        durable_json(record_file, record)
        # Native filesystem avoids Windows-mount import latency at process start.
        relay_source = root / "relay.py"
        shutil.copyfile(Path(__file__).with_name("relay.py"), relay_source)
        with (root / "relay.log").open("ab") as log:
            relay_process = subprocess.Popen([sys.executable, str(relay_source), "--workspace", str(root / "workspace"), "--metadata", str(root / "relay.json")], stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        deadline = time.monotonic() + 20
        while not (root / "relay.json").exists():
            if relay_process.poll() is not None:
                raise RuntimeError("local status relay exited: " + (root / "relay.log").read_text()[-800:])
            if time.monotonic() > deadline:
                relay_process.terminate()
                raise RuntimeError("local status relay did not start")
            time.sleep(0.05)
    record = json.loads(record_file.read_text())
    adapter = {"workspace": root / "workspace", "state": root / "receiver"}
    journal_file = root / "execution/journal.sexp"
    if args.command in {"check", "dispatch", "recover"}:
        if args.command == "dispatch" and journal_file.exists():
            raise ValueError("original operation already dispatched; query recovery instead")
        if args.command == "dispatch":
            try:
                require_approved_plan(record, args.approved_plan_sha256)
            except ValueError as error:
                record["actions"].append({"action": "dispatch-refused", "at": int(time.time() * 1000), "result": {"notInvoked": True, "reason": str(error)}})
                durable_json(record_file, record)
                raise
        if args.command == "recover" and not journal_file.exists():
            raise ValueError("no interrupted operation")
        cmd = {"check": "check", "dispatch": "run", "recover": "resume"}[args.command]
        req = request(record["plan"], context(), record["session"], cmd)
        if args.command == "dispatch":
            req["faults"] = {"apply": {"crash_after_commit": True}}
        result = invoke("ocaml", req, root / "execution", allow_crash=True, trusted_adapter=adapter)
        record["actions"].append({"action": args.command, "at": int(time.time() * 1000), "result": result})
        durable_json(record_file, record)
    if args.command == "verify":
        if not journal_file.exists():
            raise ValueError("operation has not run")
        journal = decode(journal_file.read_text())
        if journal.get("status") != "SUCCEEDED":
            raise ValueError("recover the original receipt before acceptance")
        # Separate invocation: file readback AND a real request to the relay process.
        content = (root / "workspace/document.txt").read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        relay = json.loads((root / "relay.json").read_text())
        def station_request():
            before = time.monotonic()
            try:
                response = urllib.request.urlopen(f"http://127.0.0.1:{relay['port']}/station-status", timeout=3)
            except urllib.error.HTTPError as error:
                response = error
            except urllib.error.URLError:
                return None, {"status": "relay-unavailable", "configurationSha256": None}, round((time.monotonic() - before) * 1000, 3)
            with response:
                status = response.status
                body = json.loads(response.read(65536))
            return status, body, round((time.monotonic() - before) * 1000, 3)
        status, body, attempts = observe_loaded_configuration(station_request, digest)
        loaded = body.get("configurationSha256") == record["targetSha256"]
        record["verification"] = {"at": int(time.time() * 1000), "method": "separate-process-http-station-request-and-file-readback", "sha256": digest, "matchesApprovedBytes": digest == record["targetSha256"], "httpStatus": status, "elapsedMs": attempts[-1]["elapsedMs"], "attempts": attempts, "loadedApprovedConfiguration": loaded, "response": body, "accepted": digest == record["targetSha256"] and loaded and status == 200 and body.get("status") == "serving", "criterion": "Station request receives HTTP 200 from the separate running relay, which reports the approved configuration digest; disk bytes also match."}
        record["actions"].append({"action": "verify", "at": record["verification"]["at"], "result": record["verification"]})
        durable_json(record_file, record)
    journal = decode(journal_file.read_text()) if journal_file.exists() else None
    ledger_file = root / "receiver/ledger.json"
    ledger = json.loads(ledger_file.read_text()) if ledger_file.exists() else {"operations": {}, "events": []}
    writes_file = root / "receiver/physical-writes.jsonl"
    writes = [json.loads(line) for line in writes_file.read_text().splitlines()] if writes_file.exists() else []
    document = (root / "workspace/document.txt").read_text()
    # Absolute adapter paths are private local metadata, not public replay evidence.
    print(json.dumps(public_evidence({**record, "journal": journal, "receiver": ledger, "physicalWrites": writes, "document": document, "observedSha256": hashlib.sha256(document.encode()).hexdigest()}), separators=(",", ":")))


if __name__ == "__main__":
    main()
