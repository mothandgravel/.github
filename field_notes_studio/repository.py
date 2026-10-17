"""SQLite job journal and user records; no media operations or UI dependencies."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from field_notes_studio.models import ACTIONS, TERMINAL, DraftConflict, Job


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Repository:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    identifier TEXT PRIMARY KEY, episode TEXT NOT NULL,
                    action TEXT NOT NULL, status TEXT NOT NULL,
                    stage TEXT NOT NULL, created TEXT NOT NULL,
                    error TEXT NOT NULL DEFAULT '', result TEXT NOT NULL DEFAULT '',
                    request TEXT NOT NULL, cancel_requested INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job TEXT NOT NULL, time TEXT NOT NULL, stage TEXT NOT NULL,
                    message TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS publications (
                    episode TEXT PRIMARY KEY, url TEXT NOT NULL, date TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workspace (
                    name TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS active_episode
                    ON jobs(episode) WHERE status IN ('queued', 'running');
                -- Make episode: one consented, resumable chain of ordinary jobs.
                CREATE TABLE IF NOT EXISTS runs (
                    identifier TEXT PRIMARY KEY, episode TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '', created TEXT NOT NULL,
                    consent TEXT NOT NULL, recipe TEXT NOT NULL,
                    stop_after INTEGER NOT NULL DEFAULT 0,
                    blocked TEXT NOT NULL DEFAULT '', closed TEXT NOT NULL DEFAULT ''
                );
                CREATE UNIQUE INDEX IF NOT EXISTS open_run ON runs(episode) WHERE closed='';
                CREATE TABLE IF NOT EXISTS run_steps (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, run TEXT NOT NULL,
                    step TEXT NOT NULL, job TEXT NOT NULL UNIQUE, added TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS durations (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, stage TEXT NOT NULL,
                    seconds REAL NOT NULL, job TEXT NOT NULL, at TEXT NOT NULL,
                    UNIQUE(stage, job)
                );
                CREATE TABLE IF NOT EXISTS readiness_cache (
                    episode TEXT PRIMARY KEY, key TEXT NOT NULL, value TEXT NOT NULL,
                    checked TEXT NOT NULL
                );
            """)

    @contextmanager
    def connection(self):
        # One connection per operation: never share SQLite handles across UI/worker threads.
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def submit(self, episode: str, action: str, request: dict) -> str:
        return self.submit_batch([(episode, action, request)])[0]

    def submit_batch(self, items: list[tuple[str, str, dict]]) -> list[str]:
        if not items or len(items) > 32 or len({item[0] for item in items}) != len(items):
            raise ValueError("Choose 1–32 different episodes for a batch")
        identifiers = []
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            self._capacity(db, len(items))
            for episode, action, request in items:
                identifiers.append(self._insert(db, episode, action, request))
        return identifiers

    @staticmethod
    def _capacity(db, count: int) -> None:
        if db.execute("SELECT COUNT(*) FROM jobs WHERE status='queued'").fetchone()[0] + count > 32:
            raise ValueError("The queue is full; wait for pending work to finish")

    @staticmethod
    def _insert(db, episode: str, action: str, request: dict) -> str:
        if action not in (*ACTIONS, "prepare"):
            raise ValueError("Unknown studio action")
        identifier = uuid.uuid4().hex
        # The caller owns the transaction; a late conflict rolls back the whole batch.
        if db.execute(
            "SELECT 1 FROM jobs WHERE episode=? AND status IN ('queued', 'running', 'waiting')",
            (episode,),
        ).fetchone():
            raise ValueError(f"This episode already has a queued or running job: {episode}")
        db.execute(
            "INSERT INTO jobs(identifier,episode,action,status,stage,created,request) "
            "VALUES(?,?,?,'queued','queued',?,?)",
            (identifier, episode, action, timestamp(), json.dumps(request, sort_keys=True)),
        )
        return identifier

    def jobs(self) -> list[Job]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT identifier,episode,action,status,stage,created,error,result,request,cancel_requested "
                "FROM jobs WHERE status IN ('queued','running','waiting') OR rowid IN "
                "(SELECT rowid FROM jobs ORDER BY rowid DESC LIMIT 100) ORDER BY rowid DESC"
            ).fetchall()
        return [Job(**dict(row)) for row in rows]

    def get(self, identifier: str) -> Job:
        with self.connection() as db:
            row = db.execute(
                "SELECT identifier,episode,action,status,stage,created,error,result,request,cancel_requested "
                "FROM jobs WHERE identifier=?",
                (identifier,),
            ).fetchone()
        if row is None:
            raise ValueError("Unknown job")
        return Job(**dict(row))

    def newer_jobs(self, episode: str, after: str) -> list[Job]:
        """Jobs for the episode queued after ``after``, oldest first."""
        with self.connection() as db:
            rows = db.execute(
                "SELECT identifier FROM jobs WHERE episode=? AND rowid > "
                "(SELECT rowid FROM jobs WHERE identifier=?) ORDER BY rowid",
                (episode, after),
            ).fetchall()
        return [self.get(row[0]) for row in rows]

    def latest_recipe(self, episode: str) -> dict | None:
        """Recipe recall is independent of the bounded queue display."""
        with self.connection() as db:
            row = db.execute(
                "SELECT request FROM jobs WHERE episode=? AND action IN ('audio','video','preview') "
                "ORDER BY rowid DESC LIMIT 1",
                (episode,),
            ).fetchone()
        return json.loads(row[0])["settings"] if row else None

    def claim(self) -> Job | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT identifier FROM jobs WHERE status='queued' ORDER BY rowid LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            db.execute("UPDATE jobs SET status='running' WHERE identifier=?", (row[0],))
        return self.get(row[0])

    def recover(self) -> None:
        """Call only while holding the exclusive worker lock; never infer success."""
        with self.connection() as db:
            db.execute(
                "UPDATE jobs SET status='interrupted', "
                "error='Worker stopped before recording a result. Inspect outputs or retry.' "
                "WHERE status='running'"
            )

    def cancel(self, identifier: str) -> None:
        with self.connection() as db:
            db.execute(
                "UPDATE jobs SET cancel_requested=1 WHERE identifier=? "
                "AND status IN ('queued','running')",
                (identifier,),
            )

    def stopped(self, identifier: str) -> bool:
        with self.connection() as db:
            row = db.execute(
                "SELECT cancel_requested FROM jobs WHERE identifier=?", (identifier,)
            ).fetchone()
        return bool(row and row[0])

    def event(self, identifier: str, stage: str, message: str) -> None:
        with self.connection() as db:
            db.execute("UPDATE jobs SET stage=? WHERE identifier=?", (stage, identifier))
            db.execute(
                "INSERT INTO events(job,time,stage,message) VALUES(?,?,?,?)",
                (identifier, timestamp(), stage, message),
            )

    def events(self, identifier: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT time,stage,message FROM events WHERE job=? ORDER BY sequence DESC LIMIT 200",
                (identifier,),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def finish(self, identifier: str, status: str, *, error: str = "", result: str = "") -> None:
        if status not in TERMINAL:
            raise ValueError("A job must finish in a terminal state")
        with self.connection() as db:
            db.execute(
                "UPDATE jobs SET status=?,stage=CASE WHEN ?='succeeded' THEN ? ELSE stage END,error=?,result=? WHERE identifier=?",
                (status, status, status, error, result, identifier),
            )
            db.execute(
                "INSERT INTO events(job,time,stage,message) VALUES(?,?,?,?)",
                (identifier, timestamp(), status, error or result or status),
            )

    def publications(self) -> dict[str, tuple[str, str]]:
        with self.connection() as db:
            return {
                row[0]: (row[1], row[2])
                for row in db.execute("SELECT episode,url,date FROM publications")
            }

    def publication(self, episode: str, url: str, date: str) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO publications VALUES(?,?,?) ON CONFLICT(episode) "
                "DO UPDATE SET url=excluded.url,date=excluded.date",
                (episode, url, date),
            )

    def state(self, name: str) -> dict:
        return self.state_snapshot(name)[0]

    def state_snapshot(self, name: str) -> tuple[dict, str]:
        with self.connection() as db:
            row = db.execute("SELECT value FROM workspace WHERE name=?", (name,)).fetchone()
        return (json.loads(row[0]), self.state_identity(row[0])) if row else ({}, "")

    @staticmethod
    def state_identity(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def checkpoint(
        self, values: dict[str, dict], *, expected: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Store raw unfinished text and navigation atomically, separate from approvals."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            encoded = {
                name: json.dumps(value, ensure_ascii=False) for name, value in values.items()
            }
            for name, identity in (expected or {}).items():
                row = db.execute("SELECT value FROM workspace WHERE name=?", (name,)).fetchone()
                actual = self.state_identity(row[0]) if row else ""
                if actual != identity and (not row or row[0] != encoded[name]):
                    raise DraftConflict(
                        "Another window saved a newer episode draft. Choose Load saved draft or Keep my draft; your edits stay open."
                    )
            db.executemany(
                "INSERT INTO workspace VALUES(?,?) ON CONFLICT(name) "
                "DO UPDATE SET value=excluded.value",
                list(encoded.items()),
            )
        return {name: self.state_identity(value) for name, value in encoded.items()}

    def recover_draft(self, episode: str, window: str, draft: dict) -> Path:
        """Keep a readable recovery copy without replacing the shared draft."""
        directory = self.path.parent / "draft-recovery"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{episode}-{window}.json"
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=directory, delete=False
            ) as handle:
                temporary = Path(handle.name)
                json.dump(
                    {"episode": episode, "saved_at": timestamp(), "draft": draft},
                    handle,
                    ensure_ascii=False,
                    indent=2,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return path

    def pause(self, identifier: str, message: str, receipt: dict | None = None) -> None:
        """Persist a recovery receipt without changing the captured source/Cloud plan."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT request FROM jobs WHERE identifier=? AND action='prepare' AND status='running'",
                (identifier,),
            ).fetchone()
            if row is None:
                raise ValueError("Only running preparation work can await captions")
            request = json.loads(row[0])
            if receipt is not None:
                used = request.pop("uncertain_chunks", None)
                if used:
                    db.execute(
                        "INSERT INTO events(job,time,stage,message) VALUES(?,?,?,?)",
                        (
                            identifier,
                            timestamp(),
                            "recovery-consumed",
                            "Narration recovery authorizations consumed: "
                            + json.dumps(used, sort_keys=True),
                        ),
                    )
                # A spend override covered the paid submission that just happened; resuming
                # only polls, so the override is not carried forward.
                request.pop("spend_override", None)
                request["resume"] = receipt
            db.execute(
                "UPDATE jobs SET status='waiting',stage='captions-waiting',error=?,request=? WHERE identifier=?",
                (message, json.dumps(request, sort_keys=True), identifier),
            )
            db.execute(
                "INSERT INTO events(job,time,stage,message) VALUES(?,?,?,?)",
                (identifier, timestamp(), "captions-waiting", message),
            )

    def resume_preparation(self, identifier: str) -> str:
        """Resume one saved remote operation; do not enqueue another preparation job."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT episode,status,action FROM jobs WHERE identifier=?", (identifier,)
            ).fetchone()
            if row is None or row[1] != "waiting" or row[2] != "prepare":
                raise ValueError("Only waiting preparation jobs can be resumed")
            if db.execute("SELECT COUNT(*) FROM jobs WHERE status='queued'").fetchone()[0] >= 32:
                raise ValueError("The queue is full; waiting caption work is unchanged")
            if db.execute(
                "SELECT 1 FROM jobs WHERE episode=? AND status IN ('queued','running')", (row[0],)
            ).fetchone():
                raise ValueError("This episode already has active work")
            db.execute(
                "UPDATE jobs SET status='queued',stage='resume',cancel_requested=0,error='' WHERE identifier=?",
                (identifier,),
            )
            db.execute(
                "INSERT INTO events(job,time,stage,message) VALUES(?,?,?,?)",
                (
                    identifier,
                    timestamp(),
                    "resume",
                    "Resume saved caption work; no uncertain retry or failed-operation restart",
                ),
            )
        return identifier

    # -- Make episode runs -------------------------------------------------------------
    # A run is a consent record plus an ordered list of ordinary jobs. It never holds
    # its own media state: what happened is always read back from the jobs.

    def start_run(
        self,
        episode: str,
        note: str,
        consent: dict,
        recipe: dict,
        first: tuple[str, str, dict],
    ) -> str:
        """Record the consent and queue the first job in one transaction."""
        step, action, request = first
        identifier = uuid.uuid4().hex
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM runs WHERE episode=? AND closed=''", (episode,)
            ).fetchone():
                raise ValueError(
                    "This episode already has a Make episode run. Open it from the work list."
                )
            self._capacity(db, 1)
            db.execute(
                "INSERT INTO runs(identifier,episode,note,created,consent,recipe) "
                "VALUES(?,?,?,?,?,?)",
                (
                    identifier,
                    episode,
                    note,
                    timestamp(),
                    json.dumps(consent, sort_keys=True),
                    json.dumps(recipe, sort_keys=True),
                ),
            )
            job = self._insert(db, episode, action, request)
            db.execute(
                "INSERT INTO run_steps(run,step,job,added) VALUES(?,?,?,?)",
                (identifier, step, job, timestamp()),
            )
        return identifier

    def add_step(
        self, run: str, step: str, action: str, request: dict, *, after: str
    ) -> str | None:
        """Queue the run's next job, only if ``after`` is still its latest job.

        Returns None, queueing nothing, when another process advanced the run first
        or the run was closed or stopped. This makes advancing idempotent.
        """
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT closed, stop_after, episode FROM runs WHERE identifier=?", (run,)
            ).fetchone()
            latest = db.execute(
                "SELECT job FROM run_steps WHERE run=? ORDER BY sequence DESC LIMIT 1", (run,)
            ).fetchone()
            if row is None or row[0] or row[1] or latest is None or latest[0] != after:
                return None
            self._capacity(db, 1)
            job = self._insert(db, row[2], action, request)
            db.execute(
                "INSERT INTO run_steps(run,step,job,added) VALUES(?,?,?,?)",
                (run, step, job, timestamp()),
            )
        return job

    def adopt_step(self, run: str, step: str, job: str, *, after: str) -> bool:
        """Follow a job someone queued for this episode on the expert path."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            latest = db.execute(
                "SELECT job FROM run_steps WHERE run=? ORDER BY sequence DESC LIMIT 1", (run,)
            ).fetchone()
            if latest is None or latest[0] != after:
                return False
            db.execute(
                "INSERT OR IGNORE INTO run_steps(run,step,job,added) VALUES(?,?,?,?)",
                (run, step, job, timestamp()),
            )
        return True

    def run(self, identifier: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT * FROM runs WHERE identifier=?", (identifier,)).fetchone()
        if row is None:
            raise ValueError("Unknown Make episode run")
        value = dict(row)
        value["consent"] = json.loads(value["consent"])
        value["recipe"] = json.loads(value["recipe"])
        return value

    def runs(self, *, include_closed: bool = False) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT identifier FROM runs "
                + ("" if include_closed else "WHERE closed='' ")
                + "ORDER BY rowid DESC LIMIT 200"
            ).fetchall()
        return [self.run(row[0]) for row in rows]

    def run_steps(self, run: str) -> list[dict]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT step, job, added FROM run_steps WHERE run=? ORDER BY sequence", (run,)
            ).fetchall()
        return [dict(row) for row in rows]

    def update_run(
        self, identifier: str, *, stop_after: bool | None = None, blocked: str | None = None
    ) -> None:
        with self.connection() as db:
            if stop_after is not None:
                db.execute(
                    "UPDATE runs SET stop_after=? WHERE identifier=?",
                    (int(stop_after), identifier),
                )
            if blocked is not None:
                db.execute(
                    "UPDATE runs SET blocked=? WHERE identifier=?", (blocked[:600], identifier)
                )

    def close_run(self, identifier: str) -> None:
        with self.connection() as db:
            db.execute(
                "UPDATE runs SET closed=? WHERE identifier=? AND closed=''",
                (timestamp(), identifier),
            )

    def record_duration(self, stage: str, seconds: float, job: str) -> None:
        if not 0 <= seconds <= 7 * 86400:
            return
        with self.connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO durations(stage,seconds,job,at) VALUES(?,?,?,?)",
                (stage, round(seconds, 1), job, timestamp()),
            )

    def durations(self, stage: str, limit: int = 5) -> list[float]:
        with self.connection() as db:
            rows = db.execute(
                "SELECT seconds FROM durations WHERE stage=? ORDER BY sequence DESC LIMIT ?",
                (stage, limit),
            ).fetchall()
        return [row[0] for row in rows]

    # -- Verified readiness cache ------------------------------------------------------

    def cached_readiness(self, episode: str) -> tuple[str, dict, str] | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT key, value, checked FROM readiness_cache WHERE episode=?", (episode,)
            ).fetchone()
        return (row[0], json.loads(row[1]), row[2]) if row else None

    def cache_readiness(self, episode: str, key: str, value: dict) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO readiness_cache VALUES(?,?,?,?) ON CONFLICT(episode) DO UPDATE "
                "SET key=excluded.key, value=excluded.value, checked=excluded.checked",
                (episode, key, json.dumps(value, sort_keys=True), timestamp()),
            )

    def forget_readiness(self, episode: str | None = None) -> None:
        with self.connection() as db:
            if episode is None:
                db.execute("DELETE FROM readiness_cache")
            else:
                db.execute("DELETE FROM readiness_cache WHERE episode=?", (episode,))
