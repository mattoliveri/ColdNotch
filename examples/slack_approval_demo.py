"""Exemple : le canal humain Slack de bout en bout (core seul, sans moteur de risque).

Un HOLD est posté (dry-run, sans token Slack) puis tranché depuis un "reviewer" qui
simule le clic. Montre : Approuver -> exécution, Refuser -> blocage, tout dans l'audit.

Avec un vrai Slack : exporter SLACK_BOT_TOKEN + SLACK_CHANNEL, lancer le serveur
    uvicorn coldnotch.approval_server:app
et pointer l'URL d'interactivité de l'app Slack vers .../slack/actions.

Usage : python examples/slack_approval_demo.py
"""

from __future__ import annotations

import os
import threading
import time

os.environ.setdefault("COLDNOTCH_AUDIT", "slack_demo_audit.jsonl")

from coldnotch import Action, Blocked, Policy, RiskResult, configure, gate
from coldnotch.approvals import ApprovalStore
from coldnotch.slack import SlackNotifier

STORE = ApprovalStore(path="slack_demo_approvals.db")


def reviewer(decision: str, delay: float = 0.6) -> None:
    """Simule le clic humain : attend le HOLD puis le tranche."""
    def worker():
        time.sleep(delay)
        for _ in range(50):
            pend = STORE.list_pending()
            if pend:
                STORE.resolve(pend[0]["id"], decision, decided_by="demo-reviewer")
                return
            time.sleep(0.1)
    threading.Thread(target=worker, daemon=True).start()


def hold_always(action, ctx=None):
    return RiskResult(0.8, "demo : validation humaine requise")


def main() -> None:
    configure(policy=Policy(risk_fn=hold_always), notifier=SlackNotifier(store=STORE, poll_timeout=30))

    print("== 1) HOLD approuve ==")
    reviewer("approve")
    try:
        with gate(Action(type="send_email", summary="Promesse de remboursement", agent="demo-bot")):
            print("  -> email envoye (HOLD approuve)")
    except Blocked as b:
        print("  -> bloque :", b)

    print("== 2) HOLD refuse ==")
    reviewer("deny")
    try:
        with gate(Action(type="send_email", summary="Autre promesse de remboursement", agent="demo-bot")):
            print("  -> [BUG] execute")
    except Blocked as b:
        print("  -> bloque (HOLD refuse) :", b)

    print("\n== audit ==")
    with open(os.environ["COLDNOTCH_AUDIT"], encoding="utf-8") as fh:
        for line in fh:
            print("  ", line.strip())


if __name__ == "__main__":
    main()
