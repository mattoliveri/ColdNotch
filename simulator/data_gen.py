"""Génération de données de test. Stdlib `random` uniquement, aucune dépendance.

Produit de faux clients, montants, emails et faux tokens (clairement factices)
pour donner de la variété aux scénarios. Rien de tout cela n'est réel.
"""

from __future__ import annotations

import random
from typing import Dict

_CLIENTS = ["Acme Corp", "Globex", "Initech", "Umbrella", "Soylent", "Hooli"]
_DOMAINS = ["example.com", "client.test", "acme.test"]
_FIRST = ["marie", "jean", "sofia", "liam", "chen", "amina"]
_HEX = "0123456789abcdef"


def make_rng(seed=None) -> random.Random:
    """RNG local (reproductible si `seed` est fourni)."""
    return random.Random(seed)


def fake_client(rng: random.Random) -> str:
    return rng.choice(_CLIENTS)


def fake_email(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST)}.{rng.randint(1, 99)}@{rng.choice(_DOMAINS)}"


def fake_amount(rng: random.Random, lo: int = 50, hi: int = 9000) -> int:
    return rng.randrange(lo, hi, 10)


def fake_token(rng: random.Random) -> str:
    """Faux token factice (sans les mots 'secret'/'password', pour ne pas biaiser le stub)."""
    return "sk_test_" + "".join(rng.choice(_HEX) for _ in range(16))


def sample_values(rng: random.Random) -> Dict[str, str]:
    """Un jeu de valeurs pour instancier un scénario (placeholders)."""
    return {
        "client": fake_client(rng),
        "email": fake_email(rng),
        "amount": str(fake_amount(rng)),
        "token": fake_token(rng),
    }
