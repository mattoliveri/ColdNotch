"""Notifiers : comment un HOLD obtient (ou non) une validation humaine."""

from __future__ import annotations

from .core import Action


class Notifier:
    """Interface : décide si un HOLD est approuvé. À sous-classer."""

    def request_approval(self, action: Action, reason: str, risk: float) -> bool:
        raise NotImplementedError


class ConsoleNotifier(Notifier):
    """Validation interactive en console (y/N). Refuse par défaut / si non-TTY."""

    def request_approval(self, action: Action, reason: str, risk: float) -> bool:
        prompt = (
            f"\n[HOLD] {action.type} par {action.agent}\n"
            f"  {action.summary}\n"
            f"  raison : {reason} (risque {risk:.2f})\n"
            f"  Approuver ? [y/N] "
        )
        try:
            answer = input(prompt)
        except EOFError:
            return False
        return answer.strip().lower() in ("y", "yes", "o", "oui")


class AutoNotifier(Notifier):
    """Notifier non interactif : approuve ou refuse tout selon `approve`.

    Pour les tests, démos et exécutions non interactives (`--auto`).
    """

    def __init__(self, approve: bool):
        self.approve = approve

    def request_approval(self, action: Action, reason: str, risk: float) -> bool:
        return self.approve
