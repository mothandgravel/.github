"""Prepare private, pinned inputs locally; never copies them into docs/."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def linux_path(path):
    value = str(path.resolve()).replace("\\", "/")
    return "/mnt/" + value[0].lower() + value[2:] if len(value) > 1 and value[1] == ":" else value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ajo-root", type=Path, required=True)
    parser.add_argument("--rpc-root", type=Path, required=True)
    parser.add_argument("--install-host-tools", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "docs/design/maintenance-acceptance-provenance.json").read_text())
    for item in manifest["files"]:
        source_root = args.ajo_root if item["repo"] == "ajo" else args.rpc_root
        source = source_root / item["path"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Pinned source differs: {item['repo']}/{item['path']}")
        target = root / "artifacts/maintenance/vendor" / item["repo"] / item["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.resolve() != target.resolve():
            shutil.copyfile(source, target)
    command = ["sh", linux_path(root / "scripts/maintenance/prepare-host.sh"), linux_path(root / "artifacts/maintenance/vendor/ajo"), "1" if args.install_host_tools else "0"]
    if sys.platform == "win32":
        command = ["wsl.exe", "-d", "Ubuntu", "--", *command]
    subprocess.run(command, check=True)
    (root / "artifacts/maintenance/source-hashes.json").write_text(json.dumps(manifest["files"], indent=2) + "\n")
    print("Prepared pinned sources. Run: bun scripts/maintenance/server.ts")


if __name__ == "__main__":
    main()
