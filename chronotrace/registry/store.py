"""Incident persistence (SQLite locally, DynamoDB when credits land — spec 33).

Incidents are stored as whole JSON documents rather than shredded into columns:
the report *is* the record, and a schema migration for every new field would be
a maintenance tax with no reader.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path

from chronotrace.contracts import IncidentReport

__all__ = ["IncidentStore"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    incident_id TEXT PRIMARY KEY,
    test_id     TEXT NOT NULL,
    ui_state    TEXT NOT NULL,
    created_at  REAL NOT NULL DEFAULT (julianday('now')),
    report      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS incidents_by_test ON incidents (test_id);
"""


class IncidentStore:
    """A SQLite-backed store of incident reports."""

    def __init__(self, path: Path) -> None:
        """Open (and create if needed) the store at ``path``."""
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.executescript(_SCHEMA)
            connection.commit()

    def save(self, report: IncidentReport) -> None:
        """Insert or replace an incident report."""
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute(
                "INSERT OR REPLACE INTO incidents (incident_id, test_id, ui_state, report) "
                "VALUES (?, ?, ?, ?)",
                (
                    report.incident_id,
                    report.test_id,
                    report.ui_state,
                    report.model_dump_json(),
                ),
            )
            connection.commit()

    def get(self, incident_id: str) -> IncidentReport | None:
        """Return one incident report, or None when it is not stored."""
        with closing(sqlite3.connect(self.path)) as connection:
            row = connection.execute(
                "SELECT report FROM incidents WHERE incident_id = ?", (incident_id,)
            ).fetchone()
        return IncidentReport.model_validate_json(row[0]) if row else None

    def list(self) -> list[IncidentReport]:
        """Return every stored incident, newest first."""
        with closing(sqlite3.connect(self.path)) as connection:
            rows = connection.execute(
                "SELECT report FROM incidents ORDER BY created_at DESC"
            ).fetchall()
        return [IncidentReport.model_validate_json(row[0]) for row in rows]

    def export(self, path: Path) -> None:
        """Write every incident to a JSON file, for the UI and for audit export."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps([report.model_dump(mode="json") for report in self.list()], indent=2)
        )
