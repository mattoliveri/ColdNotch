"""Journal d'audit append-only au format JSONL.

Une ligne par verdict du gate. Chemin lu depuis la variable d'environnement
COLDNOTCH_AUDIT (défaut : coldnotch_audit.jsonl).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .core import Action, Decision

DEFAULT_PATH = "coldnotch_audit.jsonl"


def audit_path() -> str:
    """Chemin du journal (env COLDNOTCH_AUDIT, sinon défaut)."""
    return os.environ.get("COLDNOTCH_AUDIT", DEFAULT_PATH)


def record(
    action: Action,
    decision: Decision,
    reason: str,
    risk: float,
    approved: bool,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """Ajoute une entrée JSONL et retourne le dict écrit."""
    entry: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent": action.agent,
        "type": action.type,
        "summary": action.summary,
        "decision": decision.value,
        "reason": reason,
        "risk": risk,
        "approved": approved,
    }
    with open(path or audit_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry
