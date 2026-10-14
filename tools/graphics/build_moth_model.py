#!/usr/bin/env python3
"""Sample the studio's SVG contours for its sculptural 3D rig (standard library only)."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/assets/moth-rig.svg"
OUTPUT = ROOT / "docs/assets/moth-model.json"
NS = "{http://www.w3.org/2000/svg}"


def sample_path(path):
    tokens = re.findall(r"[MCQLZ]|-?\d+(?:\.\d+)?", path)
    points, current, start = [], None, None
    i = 0
    while i < len(tokens):
        command = tokens[i]
        i += 1
        count = {"M": 2, "L": 2, "Q": 4, "C": 6, "Z": 0}[command]
        values = [float(v) for v in tokens[i:i + count]]
        i += count
        if command == "Z":
            current = start
        elif command in ("M", "L"):
            current = tuple(values)
            points.append(current)
            if command == "M":
                start = current
        else:
            controls = [current] + list(zip(values[::2], values[1::2]))
            for step in range(1, 13):
                t = step / 12
                curve = controls[:]
                while len(curve) > 1:
                    curve = [tuple(a * (1-t) + b * t for a, b in zip(p, q))
                             for p, q in zip(curve, curve[1:])]
                points.append(curve[0])
            current = controls[-1]
    return [[round(x, 3), round(y, 3)] for x, y in points]


def build():
    raw = SOURCE.read_bytes()
    root = ET.fromstring(raw)
    wings = []
    for group in root.findall(f"{NS}g"):
        name = group.attrib["id"]
        if not name.startswith("wing-"):
            continue
        wing = {"name": name, "pivot": [float(n) for n in group.attrib["data-pivot"].split()]}
        if "soft" in name:
            paths = group.findall(f"{NS}path")
            wing["outline"] = sample_path(paths[0].attrib["d"])
            wing["veins"] = [sample_path(p.attrib["d"]) for p in paths[1:]]
        else:
            wing["stones"] = [[[float(n) for n in pair.split(",")]
                               for pair in p.attrib["points"].split()]
                              for p in group.findall(f"{NS}polygon")]
        wings.append(wing)
    antenna = root.find(f"{NS}g[@id='moth-antennae']/{NS}path")
    # Two independent branches; M starts a new tube rather than joining across the head.
    branches = [sample_path("M" + part) for part in antenna.attrib["d"].split("M")[1:]]
    model = {"version": 1, "source": "moth-rig.svg", "sourceSha256": hashlib.sha256(raw).hexdigest(),
             "viewBox": [120, 305, 750, 430], "wings": wings, "antennae": branches}
    return json.dumps(model, separators=(",", ":")) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text() != result:
            raise SystemExit("Stale moth model: run tools/graphics/build_moth_model.py")
    else:
        OUTPUT.write_text(result)
