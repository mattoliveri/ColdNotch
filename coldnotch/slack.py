"""SlackNotifier : le canal humain. Sur un HOLD, poste l'action dans Slack avec
deux boutons Approuver / Refuser, puis attend la décision et la renvoie au gate.

Stdlib uniquement (urllib). Générique : aucune logique de risque ici (elle reste
enfichable via risk_fn). Token Slack via SLACK_BOT_TOKEN, canal via SLACK_CHANNEL.
Sans token : mode dry-run (l'approbation passe par le serveur d'approbation, ce que
fait aussi le vrai bouton Slack).
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import List, Optional

from .approvals import ApprovalStore
from .channels import Notifier
from .core import Action

SLACK_API = "https://slack.com/api"


class SlackNotifier(Notifier):
    """Poste un HOLD dans Slack et bloque jusqu'au clic Approuver / Refuser."""

    def __init__(
        self,
        store: Optional[ApprovalStore] = None,
        token: Optional[str] = None,
        channel: Optional[str] = None,
        poll_timeout: float = 300.0,
        approve_on_timeout: bool = False,
        api_base: str = SLACK_API,
    ):
        self.store = store or ApprovalStore()
        self.token = token or os.environ.get("SLACK_BOT_TOKEN")
        self.channel = channel or os.environ.get("SLACK_CHANNEL")
        self.poll_timeout = poll_timeout
        self.approve_on_timeout = approve_on_timeout  # défaut sûr : refuser si pas de réponse
        self.api_base = api_base

    def request_approval(self, action: Action, reason: str, risk: float) -> bool:
        approval_id = self.store.create(action, reason, risk)
        if self.token and self.channel:
            try:
                self._post(approval_id, action, reason, risk)
            except Exception as exc:  # le HOLD reste dans la file, décidable autrement
                print(f"[SlackNotifier] echec post Slack ({exc}); attente via la file d'approbation")
        else:
            self._dry_run(approval_id, action, reason, risk)

        decision = self.store.wait(approval_id, timeout=self.poll_timeout)
        if decision is None:
            print(f"[SlackNotifier] delai depasse ({approval_id}) -> defaut : "
                  + ("approuve" if self.approve_on_timeout else "refuse"))
            return bool(self.approve_on_timeout)
        return decision == "approve"

    def _blocks(self, approval_id: str, action: Action, reason: str, risk: float) -> List[dict]:
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text":
                f":shield: *Action en attente* `{action.type}` par *{action.agent}*\n"
                f"> {action.summary or '(sans resume)'}\n"
                f"*Risque* {risk:.2f} · {reason or 'n/a'}"}},
            {"type": "actions", "block_id": f"coldnotch:{approval_id}", "elements": [
                {"type": "button", "action_id": "coldnotch_approve", "style": "primary",
                 "text": {"type": "plain_text", "text": "Approuver"}, "value": approval_id},
                {"type": "button", "action_id": "coldnotch_deny", "style": "danger",
                 "text": {"type": "plain_text", "text": "Refuser"}, "value": approval_id},
            ]},
        ]

    def _post(self, approval_id: str, action: Action, reason: str, risk: float) -> None:
        body = json.dumps({
            "channel": self.channel,
            "text": f"Action en attente : {action.type} par {action.agent}",
            "blocks": self._blocks(approval_id, action, reason, risk),
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{self.api_base}/chat.postMessage", data=body,
            headers={"Authorization": f"Bearer {self.token}",
                     "Content-Type": "application/json; charset=utf-8"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not data.get("ok"):
            raise RuntimeError(f"Slack API : {data.get('error')}")

    def _dry_run(self, approval_id: str, action: Action, reason: str, risk: float) -> None:
        print(
            "\n[HOLD -> Slack (dry-run : pas de SLACK_BOT_TOKEN)]\n"
            f"  action : {action.type} par {action.agent}\n"
            f"  {action.summary}\n"
            f"  risque {risk:.2f} · {reason}\n"
            f"  approval_id = {approval_id}\n"
            f"  decider : POST /decision {{\"approval_id\":\"{approval_id}\",\"decision\":\"approve|deny\"}}"
        )
