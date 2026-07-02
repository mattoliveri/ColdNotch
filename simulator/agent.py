"""Agent fictif : transforme un scénario (dict JSON) en actions coldnotch.

Substitue les placeholders ({client}, {email}, {amount}, {token}) dans les
résumés et payloads à partir des valeurs générées par data_gen.
"""

from __future__ import annotations

from typing import Dict, List

from coldnotch import Action


def _fill(value, values: Dict[str, str]):
    return value.format(**values) if isinstance(value, str) else value


def emit_actions(scenario: dict, agent_name: str, values: Dict[str, str]) -> List[Action]:
    """Construit la liste d'Action d'un scénario pour un agent donné."""
    actions: List[Action] = []
    for spec in scenario["actions"]:
        summary = _fill(spec.get("summary", ""), values)
        payload = {k: _fill(v, values) for k, v in spec.get("payload", {}).items()}
        actions.append(
            Action(type=spec["type"], summary=summary, payload=payload, agent=agent_name)
        )
    return actions
