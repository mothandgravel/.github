#!/bin/sh
set -eu
maintenance_root=/tmp/mg-maintenance-20261025
if [ "${2:-0}" = 1 ]; then
  mkdir -p "$maintenance_root/hosts/packages"
  cd "$maintenance_root/hosts/packages"
  apt-get download ocaml ocaml-base ocaml-interp libstdlib-ocaml libstdlib-ocaml-dev libcompiler-libs-ocaml-dev
  for package in ./*.deb; do dpkg-deb -x "$package" "$maintenance_root/hosts"; done
fi
mkdir -p "$maintenance_root"
maintenance_staging=$(mktemp -d "$maintenance_root/ajo-staging.XXXXXX")
python3 - "$1" "$maintenance_staging" "$(dirname "$0")/../../docs/design/maintenance-acceptance-provenance.json" <<'PY'
import json, shutil, sys
from pathlib import Path
source, target, manifest = map(Path, sys.argv[1:])
for item in json.loads(manifest.read_text())["files"]:
    if item["repo"] != "ajo":
        continue
    destination = target / item["path"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / item["path"], destination)
PY
# Preserve a previous native tree; never mix old modules into a fresh build.
if [ -e "$maintenance_root/ajo" ]; then
  mv "$maintenance_root/ajo" "$maintenance_root/ajo-previous.$(date +%s)"
fi
mv "$maintenance_staging" "$maintenance_root/ajo"
export AJO_WORKSPACE="$maintenance_root/ajo"
export AJO_HOST_TOOLS_ROOT="$maintenance_root/hosts/usr"
maintenance_stdlib=$(find "$AJO_HOST_TOOLS_ROOT/lib" -name stdlib.cmi -print -quit)
test -n "$maintenance_stdlib" || { echo 'Prepare isolated host tools with --install-host-tools first.' >&2; exit 1; }
export OCAMLLIB=$(dirname "$maintenance_stdlib")
export CAML_LD_LIBRARY_PATH="$OCAMLLIB/stublibs"
export PYTHONPATH="$AJO_WORKSPACE/src"
python3 -c 'from ajo.evaluation.runner import build_ocaml; build_ocaml()'
echo 'Pinned Ajo evaluator ready; shared toolchains unchanged.'
