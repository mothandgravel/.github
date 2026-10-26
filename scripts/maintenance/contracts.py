"""Small host contracts; independent of private Ajo source."""
import hashlib
import json
import time


def public_evidence(value):
    if isinstance(value, dict):
        return {key: public_evidence(item) for key, item in value.items() if key != "adapter_context"}
    if isinstance(value, list):
        return [public_evidence(item) for item in value]
    return value


def plan_digest(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def require_approved_plan(record, approved_digest):
    if not approved_digest or plan_digest(record["plan"]) != approved_digest:
        raise ValueError("execution plan differs from the approved plan")
    calls = record["plan"]["tree"]["children"]
    if calls[0].get("payload") != {"literal": record["payload"]}:
        raise ValueError("execution payload differs from the reviewed input")


def observe_loaded_configuration(request, target_digest, timeout=1.5):
    """Retain every actual response; wait only for the asynchronous config reload."""
    deadline = time.monotonic() + timeout
    attempts = []
    while True:
        status, body, elapsed = request()
        attempts.append({"at": int(time.time() * 1000), "httpStatus": status,
                         "elapsedMs": elapsed, "response": body})
        if body.get("configurationSha256") == target_digest or time.monotonic() >= deadline:
            return status, body, attempts
        time.sleep(0.05)
