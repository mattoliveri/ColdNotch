"""Simulateur Coldnotch : banc d'essai + corpus étiqueté.

Outil de dev/démo (hors package publié `coldnotch`). Rejoue des scénarios
d'actions d'agent dans le gate pour l'exercer sans utilisateurs réels et
produire un corpus étiqueté + un rapport de gap.

Lancement : `python -m simulator --report` (depuis core/).
"""

from __future__ import annotations

from .runner import run

__all__ = ["run"]
