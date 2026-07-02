"""Tests du gate : ALLOW, HOLD approuvé, HOLD refusé, BLOCK, écriture d'audit,
et remontée de la reason d'un risk_fn custom."""

from __future__ import annotations

import json

import pytest

from coldnotch import Action, AutoNotifier, Blocked, Policy, configure, gate
from coldnotch.policy import RiskResult


def read_audit(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


@pytest.fixture
def audit(tmp_path, monkeypatch):
    p = tmp_path / "audit.jsonl"
    monkeypatch.setenv("COLDNOTCH_AUDIT", str(p))
    return p


def test_allow_executes(audit):
    configure(policy=Policy(), notifier=AutoNotifier(approve=True))
    ran = False
    with gate(Action(type="ping", summary="hello", agent="t")):
        ran = True
    assert ran is True
    last = read_audit(audit)[-1]
    assert last["decision"] == "allow"
    assert last["approved"] is True


def test_hold_approved_executes(audit):
    configure(policy=Policy(hold_types={"send_email"}), notifier=AutoNotifier(approve=True))
    ran = False
    with gate(Action(type="send_email", summary="routine", agent="t")):
        ran = True
    assert ran is True
    last = read_audit(audit)[-1]
    assert last["decision"] == "hold" and last["approved"] is True


def test_hold_refused_blocks(audit):
    configure(policy=Policy(hold_types={"send_email"}), notifier=AutoNotifier(approve=False))
    ran = False
    with pytest.raises(Blocked):
        with gate(Action(type="send_email", summary="routine", agent="t")):
            ran = True
    assert ran is False
    last = read_audit(audit)[-1]
    assert last["decision"] == "hold" and last["approved"] is False


def test_block_never_executes(audit):
    configure(policy=Policy(block_types={"wire_transfer"}), notifier=AutoNotifier(approve=True))
    ran = False
    with pytest.raises(Blocked):
        with gate(Action(type="wire_transfer", summary="1M", agent="t")):
            ran = True
    assert ran is False
    last = read_audit(audit)[-1]
    assert last["decision"] == "block" and last["approved"] is False


def test_default_risk_stub_triggers_hold(audit):
    # STUB mots-clés : "remboursement" -> risque > 0.5 -> HOLD.
    configure(policy=Policy(), notifier=AutoNotifier(approve=False))
    with pytest.raises(Blocked):
        with gate(Action(type="send_email", summary="promesse de remboursement", agent="t")):
            pass
    assert read_audit(audit)[-1]["decision"] == "hold"


def test_audit_file_written(audit):
    configure(policy=Policy(), notifier=AutoNotifier(approve=True))
    with gate(Action(type="ping", summary="x", agent="t")):
        pass
    assert audit.exists()
    rows = read_audit(audit)
    assert len(rows) >= 1
    assert set(rows[-1]) >= {"ts", "agent", "type", "decision", "reason", "risk", "approved"}


def test_custom_risk_fn_reason_surfaces(audit):
    # Un risk_fn custom renvoie une RiskResult avec une reason : elle doit
    # remonter dans le verdict HOLD (et dans l'audit), pas la raison générique.
    def my_risk(action, ctx):
        return RiskResult(score=0.9, reason="montant élevé détecté", labels=("amount",))

    configure(policy=Policy(risk_fn=my_risk), notifier=AutoNotifier(approve=False))
    with pytest.raises(Blocked) as exc:
        with gate(Action(type="charge_card", summary="débit", agent="t")):
            pass

    assert exc.value.decision.value == "hold"
    assert exc.value.reason == "montant élevé détecté"

    last = read_audit(audit)[-1]
    assert last["decision"] == "hold"
    assert last["reason"] == "montant élevé détecté"
    assert last["risk"] == 0.9
