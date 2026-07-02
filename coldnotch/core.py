"""Cœur du gate : Decision, Action, Blocked, gate(), configure().

Aucune logique propriétaire ici (repo public). Le scoring de risque est délégué
à une Policy enfichable (voir policy.py) ; le vrai moteur vit dans cloud/.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterator, Optional


class Decision(Enum):
    """Verdict du gate pour une action."""

    ALLOW = "allow"
    HOLD = "hold"
    BLOCK = "block"


@dataclass
class Action:
    """Une action qu'un agent veut exécuter, soumise au gate avant exécution."""

    type: str
    summary: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    agent: str = "unknown"


class Blocked(Exception):
    """Levée quand une action est BLOCK, ou un HOLD refusé : jamais exécutée."""

    def __init__(self, action: "Action", decision: "Decision", reason: str, risk: float):
        self.action = action
        self.decision = decision
        self.reason = reason
        self.risk = risk
        super().__init__(f"{action.type} [{decision.value}] : {reason}")


# Configuration au niveau du module (surchargée via configure()).
_policy: Optional[Any] = None
_notifier: Optional[Any] = None


def configure(policy: Optional[Any] = None, notifier: Optional[Any] = None) -> None:
    """Installe la politique et/ou le notifier par défaut du processus."""
    global _policy, _notifier
    if policy is not None:
        _policy = policy
    if notifier is not None:
        _notifier = notifier


def _active_policy() -> Any:
    global _policy
    if _policy is None:
        from .policy import Policy

        _policy = Policy()
    return _policy


def _active_notifier() -> Any:
    global _notifier
    if _notifier is None:
        from .channels import ConsoleNotifier

        _notifier = ConsoleNotifier()
    return _notifier


@contextmanager
def gate(action: "Action") -> Iterator["Action"]:
    """Point de contrôle : évalue l'action, journalise, puis autorise ou bloque.

    ALLOW              -> exécute le corps du `with`, audit approved=True.
    HOLD approuvé      -> exécute, audit approved=True.
    HOLD refusé / BLOCK-> lève Blocked avant exécution, audit approved=False.
    """
    policy = _active_policy()
    notifier = _active_notifier()

    decision, reason, risk = policy.evaluate(action)

    if decision is Decision.ALLOW:
        approved = True
    elif decision is Decision.HOLD:
        approved = bool(notifier.request_approval(action, reason, risk))
    else:  # Decision.BLOCK
        approved = False

    # Preuve auditable : une ligne, quel que soit le verdict.
    from .audit import record

    record(action, decision, reason, risk, approved)

    if not approved:
        raise Blocked(action, decision, reason, risk)

    yield action
