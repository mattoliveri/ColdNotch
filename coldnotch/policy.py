"""Politique d'évaluation + STUB de scoring de risque.

IMPORTANT (frontière open-core) : `default_risk` est un STUB trivial à base de
mots-clés, volontairement naïf. Le vrai moteur de risque (le "moat") vit dans
cloud/ et s'injecte via `risk_fn`. Ne jamais mettre de logique propriétaire ici.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Tuple

from .core import Action, Decision


@dataclass(frozen=True)
class RiskResult:
    """Résultat structuré d'un scoring de risque (immuable)."""

    score: float
    reason: str = ""
    labels: tuple = ()


@dataclass
class EvalContext:
    """Contexte optionnel passé au risk_fn : seam pour les enchaînements d'actions."""

    history: tuple = ()  # actions récentes, pour détecter les enchaînements


# Contrat public d'un scoring de risque : (action, contexte) -> RiskResult.
RiskFn = Callable[[Action, EvalContext], RiskResult]


# STUB : mots-clés considérés "à conséquence". À REMPLACER par un vrai risk_fn.
_RISKY_KEYWORDS: Tuple[str, ...] = (
    "rembours", "refund", "paiement", "payment", "virement", "transfer",
    "wire", "password", "mot de passe", "secret", "delete", "supprim",
)


def default_risk(action: Action, ctx: EvalContext) -> RiskResult:
    """STUB trivial : score selon le nombre de mots-clés à risque.

    Ignore `ctx.history` (le vrai moteur, dans cloud/, exploitera le contexte).
    Naïf exprès (repo public). Remplacer via `Policy(risk_fn=...)`.
    """
    text = f"{action.summary} {action.payload}".lower()
    matched = tuple(kw for kw in _RISKY_KEYWORDS if kw in text)
    if not matched:
        return RiskResult(score=0.0)
    score = min(1.0, 0.4 + 0.2 * len(matched))
    reason = f"mots-clés à risque : {', '.join(matched)}"
    return RiskResult(score=score, reason=reason, labels=matched)


@dataclass
class Policy:
    """Règles simples : listes de types + seuil de risque, avec risk_fn enfichable."""

    block_types: Iterable[str] = field(default_factory=frozenset)
    hold_types: Iterable[str] = field(default_factory=frozenset)
    hold_if_risk_over: float = 0.5
    risk_fn: RiskFn = default_risk

    def __post_init__(self) -> None:
        # Normalise en frozenset (accepte list/set/tuple en entrée).
        self.block_types = frozenset(self.block_types)
        self.hold_types = frozenset(self.hold_types)

    def evaluate(
        self, action: Action, context: Optional[EvalContext] = None
    ) -> Tuple[Decision, str, float]:
        """Retourne (Decision, raison lisible, score de risque float).

        Compat 100% : la signature de retour est inchangée et `context` est
        optionnel (un EvalContext vide est créé si absent).
        """
        ctx = context if context is not None else EvalContext()
        risk = self.risk_fn(action, ctx)
        score = float(risk.score)

        if action.type in self.block_types:
            return Decision.BLOCK, f"type '{action.type}' interdit par la politique", score
        if action.type in self.hold_types:
            return Decision.HOLD, f"type '{action.type}' requiert une validation", score
        if score > self.hold_if_risk_over:
            # HOLD déclenché par le RISQUE : préférer la raison du RiskResult.
            reason = risk.reason or (
                f"risque {score:.2f} au-dessus du seuil {self.hold_if_risk_over:.2f}"
            )
            return Decision.HOLD, reason, score
        return Decision.ALLOW, "conforme à la politique", score
