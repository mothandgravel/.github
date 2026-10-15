"""SQLite job journal and user records; no media operations or UI dependencies."""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from field_notes_studio.models import ACTIONS, TERMINAL, Job


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
            if (
                db.execute("SELECT COUNT(*) FROM jobs WHERE status='queued'").fetchone()[0]
                + len(items)
                > 32
            ):
                raise ValueError("The queue is full; wait for pending work to finish")
            for episode, action, request in items:
                identifiers.append(self._insert(db, episode, action, request))
        return identifiers

    @staticmethod
    def _insert(db, episode: str, action: str, request: dict) -> str:
        if action not in ACTIONS:
            raise ValueError("Unknown studio action")
        identifier = uuid.uuid4().hex
        # The caller owns the transaction; a late conflict rolls back the whole batch.
        if db.execute(
            "SELECT 1 FROM jobs WHERE episode=? AND status IN ('queued', 'running')",
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
                "FROM jobs WHERE status IN ('queued','running') OR rowid IN "
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

    def latest_recipe(self, episode: str) -> dict | None:
        """Recipe recall is independent of the bounded queue display."""
        with self.connection() as db:
            row = db.execute(
                "SELECT request FROM jobs WHERE episode=? AND action!='export' "
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
                "UPDATE jobs SET status='interrupted', stage='interrupted', "
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
                "UPDATE jobs SET status=?,stage=?,error=?,result=? WHERE identifier=?",
                (status, status, error, result, identifier),
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
        with self.connection() as db:
            row = db.execute("SELECT value FROM workspace WHERE name=?", (name,)).fetchone()
        return json.loads(row[0]) if row else {}

    def checkpoint(self, values: dict[str, dict]) -> None:
        """Store raw unfinished text and navigation atomically, separate from approvals."""
        with self.connection() as db:
            db.executemany(
                "INSERT INTO workspace VALUES(?,?) ON CONFLICT(name) "
                "DO UPDATE SET value=excluded.value",
                [(name, json.dumps(value, ensure_ascii=False)) for name, value in values.items()],
            )
