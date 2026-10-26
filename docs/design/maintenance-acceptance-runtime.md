# Maintenance acceptance — local runtime

The public specimen replays captured runtime evidence. Local mode performs fresh,
isolated configuration changes with the same pinned Ajo evaluator/receiver and
Raivari RPC guard. A separate Python HTTP status-relay process loads that file.
It controls no equipment, operating-system services or browser-selected files.

## Prepare

Use authorised local checkouts of these private sources at the listed revisions:

- Ajo: `ec205b9925add515b2b7408cbc8ee73737fcec55`
- raivari-rpc: `80ca8c6cc28440e5eab7abccbece7282ecbb56ab`

The controller uses Python 3.14+ (the pinned receiver uses that syntax), Bun and a
Linux/POSIX filesystem. Windows uses an installed Ubuntu WSL distribution. The
tested isolated compiler is OCaml 5.4.0. No model API or cloud service is used.

From the site checkout, with Python 3 and Bun available:

```text
python scripts/maintenance/prepare.py --ajo-root /path/to/ajo --rpc-root /path/to/raivari-rpc --install-host-tools
bun scripts/maintenance/server.ts
```

On Windows, supply Windows checkout paths to `prepare.py`; it converts only its
own runtime paths for WSL. The opt-in host-tools flag downloads official Ubuntu
packages and extracts them under `/tmp/mg-maintenance-20261025/hosts`; it does not
install system packages. Preparation verifies each selected source file against
the public provenance hashes. Keep Git checkout line endings as LF for hash
verification. A changed source is refused, rather than relabelled as the pin.

Private source stays under ignored `artifacts/maintenance/vendor/`. Native build
and receiver state use `/tmp/mg-maintenance-20261025/`. This is laboratory storage,
not an archival retention promise. Export before removing it or restarting the
host. The static GitHub Pages deployment runs no backend. Stop the owned host and
bridge before preparing new native sources. Previous native build trees are
preserved separately; preparation copies only the named source files.

Open:

```text
http://127.0.0.1:8796/specimens/maintenance-acceptance/?mode=live
```

Start a new run, approve its exact input, dispatch with the injected interruption,
query the original operation, then make the station request. “Try a changed input” runs
the real RPC guard with an altered fingerprint and must produce a block receipt
without starting Ajo. The second scenario retains maintenance mode in the approved
configuration: the write succeeds but the actual HTTP request receives 503.

## Evidence and checks

`bun scripts/maintenance/server.ts` listens only on loopback. Mutations require a
same-origin custom-header POST. Browser input selects a fixed action and a run
identity, never an executable or filesystem path. All API actions are serialized.
The host starts one POSIX bridge on loopback port 8797. Its adapter-source digest
includes the bridge, runtime, relay and contracts. Its configured roots and actual
Ajo source hashes must match. It rebuilds the evaluator from those checked sources
and reports the observed compiler version and binary digest. Each action rechecks
the source and binary bytes; the host checks RPC source before import and guard
evaluation. These are local integrity checks, not independent attestation.
Restart both owned host and bridge when changing adapter source.
Each new run has a distinct file, journal and receiver ledger. Repeated dispatch
is refused when an execution journal exists; recovery resumes that journal.
Dispatch intent is saved before sending. Reopening a run reads the native snapshot
and reconciles the host phase from its journal, including a commit whose bridge
reply or host checkpoint was lost. If no native account establishes an outcome,
the dispatch stays unresolved rather than offering a blind repeat. The approved
plan digest is checked again by the native adapter before invoking Ajo.

The guard's allowed decision is preflight evidence, not a signature or atomic
authority lease. The local operator record is host-created. Ajo's actual receiver
records starts and queries separately and persists its result. A separate process
reads the resulting bytes and requests the separate relay's `/station-status`
endpoint. Acceptance requires HTTP 200, a serving response and the approved
configuration digest loaded by the running relay, as well as matching disk bytes.
The relay can take a moment to reload. A check waits up to 1.5 seconds for the
observed disk digest, retaining every actual response, and never retries away a
matching HTTP 503. Acceptance can be checked again; earlier observations remain
in history. Relays shut down after two idle hours. A request failure stays a
failure. This is a real laboratory service, not a deployed-site measurement.
Private adapter mappings are removed recursively from the public JSON projection.

```text
node scripts/maintenance/capture.mjs
node --test scripts/maintenance_acceptance.test.mjs
python scripts/maintenance/contracts_test.py
node scripts/maintenance/failure-probe.mjs
python scripts/check_site.py
```

Capture requires the local server. It checks the native plan result, an RPC
binding refusal, actual evaluator interruption, one receiver start and one file
replacement, original-operation query recovery, both acceptance outcomes and a
reopened account. Only successful captures replace the public recordings.
Provenance records the captured file's SHA-256 and selected original source hashes.
The optional failure probe uses fresh isolated runs: it restores an old host
checkpoint after a real native commit, verifies original-operation recovery, then
alters another run's native plan after approval and verifies refusal before any
execution. It does not change the bundled public captures or private source.

Opening a replay sends no action. Recorded exports include only the selected
step and preceding snapshots. Do not infer power-loss durability, independent
attestation, equipment safety or operational deployment from this laboratory run.
