"""Exemple : un agent email encadré par le gate.

- un email de routine           -> ALLOW (exécuté)
- une promesse de remboursement -> HOLD  (validation requise)

Usage :
    python examples/email_agent.py          # HOLD interactif (console y/N)
    python examples/email_agent.py --auto   # approuve les HOLD sans interaction
"""

from __future__ import annotations

import sys

from coldnotch import Action, AutoNotifier, Blocked, Policy, configure, gate


def send_email(to: str, body: str) -> None:
    print(f"  -> email envoyé à {to} : {body}")


def run(auto: bool) -> None:
    configure(policy=Policy())
    if auto:
        configure(notifier=AutoNotifier(approve=True))
    # sinon : ConsoleNotifier interactif par défaut.

    # 1) Email de routine -> ALLOW
    routine = Action(
        type="send_email",
        summary="Confirmation de rendez-vous",
        payload={"to": "client@example.com"},
        agent="email-bot",
    )
    try:
        with gate(routine) as act:
            send_email(act.payload["to"], "Votre rendez-vous est confirmé.")
        print("[ALLOW] email de routine envoyé.")
    except Blocked as blocked:
        print(f"[BLOCKED] {blocked}")

    # 2) Promesse de remboursement -> HOLD
    refund = Action(
        type="send_email",
        summary="Nous vous promettons un remboursement de 240 euros",
        payload={"to": "client@example.com", "amount": 240},
        agent="email-bot",
    )
    try:
        with gate(refund) as act:
            send_email(act.payload["to"], "Nous vous remboursons 240 euros.")
        print("[HOLD approuvé] email de remboursement envoyé.")
    except Blocked as blocked:
        print(f"[HOLD refusé] action bloquée : {blocked}")


if __name__ == "__main__":
    run(auto="--auto" in sys.argv)
