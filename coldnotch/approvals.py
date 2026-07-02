"""File d'approbations (SQLite) : le pont entre un HOLD et la décision humaine.

Stdlib uniquement (sqlite3). Partageable entre processus (l'agent qui attend et le
serveur qui reçoit le clic Slack lisent/écrivent le même fichier). Aucune logique de
risque ici : juste "en attente" -> "approuvé/refusé".
"""

from __future__ import annotations

import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DEFAULT_DB = "coldnotch_approvals.db"


def approvals_path() -> str:
    """Chemin de la base d'approbations (env COLDNOTCH_APPROVALS, sinon défaut)."""
    return os.environ.get("COLDNOTCH_APPROVALS", DEFAULT_DB)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ApprovalStore:
    """File d'approbations persistante. Une connexion courte par opération."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or approvals_path()
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS approvals(
                    id TEXT PRIMARY KEY, agent TEXT, type TEXT, summary TEXT,
                    reason TEXT, risk REAL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    decision TEXT, decided_by TEXT,
                    created_at TEXT, decided_at TEXT)"""
            )

    def create(self, action, reason: str, risk: float, approval_id: Optional[str] = None) -> str:
        """Enregistre un HOLD en attente et retourne son identifiant."""
        approval_id = approval_id or uuid.uuid4().hex
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO approvals(id,agent,type,summary,reason,risk,status,created_at)"
                " VALUES(?,?,?,?,?,?, 'pending', ?)",
                (approval_id, action.agent, action.type, action.summary, reason, float(risk), _now()),
            )
        return approval_id

    def resolve(self, approval_id: str, decision, decided_by: str = "human") -> Dict[str, Any]:
        """Tranche un HOLD. `decision` accepte bool ou 'approve'/'deny' (et variantes)."""
        norm = "approve" if decision in (True, "approve", "approved", "allow", "y", "yes", "oui") else "deny"
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE approvals SET status='resolved', decision=?, decided_by=?, decided_at=?"
                " WHERE id=? AND status='pending'",
                (norm, decided_by, _now(), approval_id),
            )
            changed = cur.rowcount
        return {"approval_id": approval_id, "decision": norm, "changed": changed}

    def get(self, approval_id: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        return dict(row) if row else None

    def list_pending(self) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE status='pending' ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def wait(self, approval_id: str, timeout: float = 300.0, poll: float = 0.5) -> Optional[str]:
        """Bloque (polling) jusqu'à résolution. Retourne 'approve'/'deny', ou None si délai dépassé."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            row = self.get(approval_id)
            if row and row["status"] == "resolved":
                return row["decision"]
            time.sleep(poll)
        return None
