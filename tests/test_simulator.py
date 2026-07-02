"""Test P2 : un petit run du simulateur produit un corpus non vide + un rapport.
Test P2.1 : les scénarios subtils exposent les vrais trous du stub mots-clés."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]  # racine du repo core/


def _run_corpus(tmp_path, bots=2, seed=1):
    out = tmp_path / "corpus.jsonl"
    res = subprocess.run(
        [sys.executable, "-m", "simulator", "--out", str(out), "--bots", str(bots), "--seed", str(seed)],
        cwd=str(CORE),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows, res


def test_simulator_produces_corpus(tmp_path):
    rows, res = _run_corpus(tmp_path)
    assert len(rows) > 0

    expected_keys = {
        "action", "agent", "scenario", "category",
        "ground_truth_label", "decision", "risk", "reason",
    }
    assert expected_keys <= set(rows[0])
    assert "RAPPORT" in res.stdout

    # Les enchaînements ne sont pas attrapés par le stub (ils restent ALLOW).
    chain_rows = [r for r in rows if r["category"] == "risky_chain"]
    assert chain_rows
    assert all(r["decision"] == "allow" for r in chain_rows)


def test_subtle_missed_and_traps_flagged(tmp_path):
    rows, _ = _run_corpus(tmp_path)

    # risque paraphrasé (aucun mot-clé) : le stub le RATE -> ALLOW.
    subtle = [r for r in rows if r["category"] == "risky_subtle"]
    assert subtle
    assert all(r["decision"] == "allow" for r in subtle)

    # pièges bénins (mot-clé présent, aucune conséquence) : le stub FLAGUE a tort -> HOLD.
    traps = [r for r in rows if r["category"] == "benign_trap"]
    assert traps
    assert all(r["decision"] == "hold" for r in traps)
