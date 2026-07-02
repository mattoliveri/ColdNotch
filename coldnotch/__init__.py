"""coldnotch : le gate des actions d'agent (open source).

Enveloppez une action dans `gate(...)` : elle est autorisée, mise en attente
d'une validation humaine, ou bloquée avant exécution, avec une preuve auditable.
"""

from __future__ import annotations

from .approvals import ApprovalStore
from .channels import AutoNotifier, ConsoleNotifier, Notifier
from .core import Action, Blocked, Decision, configure, gate
from .policy import EvalContext, Policy, RiskFn, RiskResult, default_risk
from .slack import SlackNotifier

__all__ = [
    "Action",
    "Decision",
    "Blocked",
    "Policy",
    "gate",
    "configure",
    "Notifier",
    "ConsoleNotifier",
    "AutoNotifier",
    "SlackNotifier",
    "ApprovalStore",
    "default_risk",
    "RiskResult",
    "EvalContext",
    "RiskFn",
]

__version__ = "0.0.1"
