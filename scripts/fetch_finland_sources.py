#!/usr/bin/env python3
"""Retrieve only the public, hash-pinned inputs of the Finnish account.

Usage: python scripts/fetch_finland_sources.py artifacts/research/finland-energy
No credentials. Source updates fail closed; inspect them before changing pinned hashes.
"""
import argparse
import hashlib
import json
import os
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT/'docs/design/finland-provenance.json').read_bytes())
    data = json.loads((ROOT/'docs/assets/data-center/finland.json').read_bytes())
    query = json.dumps(data['prices']['query'], indent=2).encode() + b'\n'
    for name, source in manifest['inputs'].items():
        dest = args.destination/name
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == source['sha256']:
            print(f'Already pinned: {name}')
            continue
        if source['url'] is None:
            content = query
        elif name == 'statfin-13rb.json':
            request = urllib.request.Request(source['url'], data=json.dumps(data['prices']['query']).encode(), headers={'Content-Type': 'application/json'})
            content = urllib.request.urlopen(request, timeout=60).read()
        elif os.name == 'nt':
            # Use Windows certificate validation; never disable HTTPS verification.
            result = subprocess.run(['curl.exe', '--fail', '--silent', '--show-error', '--location', source['url']], check=True, capture_output=True)
            content = result.stdout
        else:
            content = urllib.request.urlopen(source['url'], timeout=120).read()
        actual = hashlib.sha256(content).hexdigest()
        if actual != source['sha256']:
            raise SystemExit(f'Publisher input changed: {name}; received SHA-256 {actual}. No pinned file replaced.')
        dest.write_bytes(content)
        print(f'Pinned: {name}')


if __name__ == '__main__':
    main()
