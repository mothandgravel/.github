"""Build an inspectable record from three pinned public TNT CSVs. Execute no upstream code."""
from collections import Counter
import csv
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REVISION = "e213681d00b9fd4ec8bd96da63209f017a898b65"
UPSTREAM = f"https://github.com/prettore/TNT/blob/{REVISION}/experiment_testbed/data/statistics/long/"
FILES = {
    "sender": ("tb_sender_pckts_ManhattanGrid_VHF_1000p1to50p_20t.csv", "107e034d0833037a25e6dda8e54dc7e0e6906158b26183316438bf9344771985"),
    "receiver": ("tb_receiver_pckts_ManhattanGrid_VHF_1000p1to50p_20t.csv", "387bb8a480df4863bf4dcec8a936e344392c89c44c5f1eb4c91125f17568d461"),
    "summary": ("tb_ip_statistics_ManhattanGrid_VHF_1000p1to50p_20t.csv", "90ce7f55a3ccbe11e3644b7f59eb3069852e1ea67b4125306bbed8302e7e8cfb"),
}


def microseconds(delta):
    return (delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds


def indexed(rows):
    counts = Counter()
    result = {}
    for row_number, row in sorted(enumerate(rows, 2), key=lambda pair: pair[1]["packet_timestamp"]):
        flow = tuple(row[key] for key in ("round", "source_ip", "destination_ip", "protocol", "packet_id"))
        counts[flow] += 1
        result[(*flow, counts[flow])] = (row_number, row)
    return result


def build():
    source, metadata = {}, {}
    for kind, (upstream_name, digest) in FILES.items():
        raw = (ROOT / f"docs/assets/tnt/source/{kind}.csv").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest, f"Changed source: {kind}"
        source[kind] = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        metadata[kind] = {"file": f"tnt/source/{kind}.csv", "sha256": digest, "upstream": UPSTREAM + upstream_name, "rows": len(source[kind])}
    sent, received = indexed(source["sender"]), indexed(source["receiver"])
    assert not set(received) - set(sent), "Unmatched receiver occurrence"
    origin = min(datetime.fromisoformat(row["packet_timestamp"]) for _, row in sent.values())
    records = []
    for ordinal, (key, (line, row)) in enumerate(sent.items(), 1):
        other = received.get(key)
        send_time = datetime.fromisoformat(row["packet_timestamp"])
        receive_time = datetime.fromisoformat(other[1]["packet_timestamp"]) if other else None
        delay = microseconds(receive_time - send_time) if receive_time else None
        assert delay is None or delay >= 0
        records.append({"ordinal": ordinal, "packetId": row["packet_id"], "occurrence": key[-1], "sentUs": microseconds(send_time - origin), "receivedUs": microseconds(receive_time - origin) if receive_time else None, "delayUs": delay, "sourceRows": {"sender": line, "receiver": other[0] if other else None}, "sender": row, "receiver": other[1] if other else None})
    delays = [r["delayUs"] / 1000000 for r in records if r["delayUs"] is not None]
    summary = {"sent": len(sent), "received": len(received), "notObserved": len(sent) - len(received), "lossPercent": (len(sent) - len(received)) * 100 / len(sent), "meanDelaySeconds": sum(delays) / len(delays), "minDelaySeconds": min(delays), "maxDelaySeconds": max(delays)}
    reported = source["summary"][0]
    for our_key, source_key in [("sent", "packet_sent"), ("received", "packet_received"), ("notObserved", "packet_dropped"), ("lossPercent", "packet_dropped_pct"), ("meanDelaySeconds", "avg_latency_s"), ("minDelaySeconds", "min_latency_s"), ("maxDelaySeconds", "max_latency_s")]:
        assert math.isclose(summary[our_key], float(reported[source_key]), rel_tol=0, abs_tol=1e-6), our_key
    groups = {}
    for key, (_, row) in sent.items():
        groups.setdefault(key[:-1], []).append(datetime.fromisoformat(row["packet_timestamp"]))
    longest_delay_us = max(r["delayUs"] or 0 for r in records)
    reuse_gaps = [microseconds(times[i] - times[i - 1]) for times in groups.values() for i in range(1, len(times))]
    assert min(reuse_gaps) > longest_delay_us
    for key, (_, row) in received.items():
        receive_time = datetime.fromisoformat(row["packet_timestamp"])
        candidates = [time for time in groups[key[:-1]] if 0 <= microseconds(receive_time - time) <= longest_delay_us]
        assert len(candidates) == 1 and candidates[0] == datetime.fromisoformat(sent[key][1]["packet_timestamp"])
    receiver_times = [datetime.fromisoformat(row["packet_timestamp"]) for _, row in received.values()]
    receiver_span_us = microseconds(max(receiver_times) - min(receiver_times))
    assert math.isclose(receiver_span_us / 1e6, float(reported["total_time_s"]), rel_tol=0, abs_tol=1e-6)
    naive = {tuple(r[k] for k in ("round", "source_ip", "destination_ip", "protocol", "packet_id")): r for r in source["sender"]}
    negative = sum(datetime.fromisoformat(r["packet_timestamp"]) < datetime.fromisoformat(naive[tuple(r[k] for k in ("round", "source_ip", "destination_ip", "protocol", "packet_id"))]["packet_timestamp"]) for r in source["receiver"])
    dataset = {"format": "mg.maintenance-tnt.v1", "source": {"name": "TNT / ManhattanGrid VHF / 1000 packets / round 1", "repository": "https://github.com/prettore/TNT", "revision": REVISION, "captureDateAsRecorded": origin.date().isoformat(), "clock": "Source capture-local time strings have no timezone. Relative times and recorded one-way delays retain the source clock relationship; no independent clock calibration was verified.", "matching": "Per-flow IPv4 ID plus chronological occurrence; reproduces this run's published counts and delays. Each receiver has exactly one send candidate within the published maximum-delay bound. That bound and the source clock relationship remain assumptions, not independent packet identity.", "matchingCheck": {"maximumDelayUs": longest_delay_us, "shortestReuseGapUs": min(reuse_gaps), "candidatesWithinBoundPerReceiver": 1}, "interval": {"replay": "First recorded send through last recorded event; not an independently recorded capture-stop time.", "publishedDuration": "First recorded receive through last recorded receive.", "publishedReceiveSpanUs": receiver_span_us}, "files": metadata, "license": "GPL-3.0; upstream license and unchanged source CSVs accompany this derived dataset."}, "summary": summary, "publishedSummary": reported, "originAsRecorded": origin.isoformat(sep=" "), "endUs": max(max(r["sentUs"], r["receivedUs"] or 0) for r in records), "failedControl": {"name": "Naive IPv4 ID lookup (last occurrence wins)", "uniqueSenderKeys": len(naive), "senderRows": len(source["sender"]), "negativeDelayCount": negative}, "limits": ["Published historical radio-bench data; no live radio or operational traffic is connected.", "No application acknowledgement, approved configuration or military handback decision is recorded in these inputs.", "A missing receive row means not observed in the published record, not independently proven permanent loss.", "Replay ends at the last source event, not a separately verified capture-stop timestamp.", "Replay sends no traffic; display speed changes only how quickly the recorded clock advances."], "records": records}
    raw = (json.dumps(dataset, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
    provenance = {"format": "mg.maintenance-tnt.provenance.v1", "revision": REVISION, "datasetSha256": hashlib.sha256(raw).hexdigest(), "sourceFiles": metadata, "generatedBy": "scripts/build_maintenance_tnt.py", "summary": summary, "records": len(records), "scope": "Deterministic transformation of published CSVs. No upstream experiment code or radio hardware executed."}
    return {ROOT / "docs/assets/maintenance-tnt.json": raw, ROOT / "docs/design/maintenance-tnt-provenance.json": (json.dumps(provenance, indent=2) + "\n").encode()}


if __name__ == "__main__":
    check = "--check" in sys.argv
    for path, raw in build().items():
        if check:
            assert path.read_bytes() == raw, f"Stale TNT data: {path}"
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
    print("PASS: pinned TNT sources, measured summary and deterministic dataset")
