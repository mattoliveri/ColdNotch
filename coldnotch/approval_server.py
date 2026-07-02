"""Serveur d'approbation minimal (FastAPI), auto-hébergeable.

Reçoit le clic Slack (POST /slack/actions) ou une décision directe (POST /decision)
et débloque le HOLD correspondant dans l'ApprovalStore. Aucune logique de risque ici.

Dépendance optionnelle : `pip install coldnotch[server]`. Le gate n'en dépend jamais.
Lancer : `uvicorn coldnotch.approval_server:app` (COLDNOTCH_APPROVALS = base partagée).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Optional
from urllib.parse import parse_qs

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from .approvals import ApprovalStore


class DecisionIn(BaseModel):
    approval_id: str
    decision: str  # "approve" | "deny"
    decided_by: str = "api"


def create_app(store: Optional[ApprovalStore] = None) -> FastAPI:
    store = store or ApprovalStore()
    app = FastAPI(title="coldnotch-approvals", version="0.1.0")

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/pending")
    def pending():
        return {"pending": store.list_pending()}

    @app.post("/decision")
    def decision(d: DecisionIn):
        """Décision directe (CLI / dashboard / test). Idempotent : 404 si déjà résolu."""
        if d.decision not in ("approve", "deny"):
            raise HTTPException(400, "decision doit valoir 'approve' ou 'deny'")
        res = store.resolve(d.approval_id, d.decision, d.decided_by)
        if not res["changed"]:
            raise HTTPException(404, "approbation inconnue ou deja resolue")
        return res

    @app.post("/slack/actions")
    async def slack_actions(request: Request):
        """Endpoint d'interactivité Slack (clic sur Approuver / Refuser)."""
        raw = await request.body()
        _verify_slack(raw, request.headers)
        form = {k: v[0] for k, v in parse_qs(raw.decode("utf-8")).items()}
        payload = json.loads(form.get("payload", "{}"))
        actions = payload.get("actions") or []
        if not actions:
            raise HTTPException(400, "payload Slack sans action")
        act = actions[0]
        approval_id = act.get("value")
        decision = "approve" if act.get("action_id") == "coldnotch_approve" else "deny"
        who = (payload.get("user") or {}).get("username", "slack")
        store.resolve(approval_id, decision, decided_by=who)
        verb = "approuvee" if decision == "approve" else "refusee"
        return {"replace_original": True, "text": f"Action {verb} par {who}."}

    return app


def _verify_slack(raw: bytes, headers) -> None:
    """Vérifie la signature Slack si SLACK_SIGNING_SECRET est défini (sinon dev : ignoré)."""
    secret = os.environ.get("SLACK_SIGNING_SECRET")
    if not secret:
        return
    ts = headers.get("x-slack-request-timestamp", "")
    sig = headers.get("x-slack-signature", "")
    try:
        if abs(time.time() - int(ts)) > 300:
            raise HTTPException(401, "horodatage Slack perime")
    except (TypeError, ValueError):
        raise HTTPException(401, "horodatage Slack manquant")
    base = b"v0:" + ts.encode() + b":" + raw
    expected = "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(401, "signature Slack invalide")


# Application par défaut pour `uvicorn coldnotch.approval_server:app`.
app = create_app()
