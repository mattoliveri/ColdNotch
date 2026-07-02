"""Tests du canal humain : ApprovalStore, SlackNotifier (dry-run) et gate HOLD.

Aucun réseau (pas de token Slack -> dry-run), aucune dépendance FastAPI.
Le clic humain est simulé en résolvant la file depuis un autre thread.
"""

from __future__ import annotations

import json
import threading
import time

from coldnotch import Action, Blocked, Policy, RiskResult, configure, gate
from coldnotch.approvals import ApprovalStore
from coldnotch.slack import SlackNotifier


def _store(tmp_path):
    return ApprovalStore(path=str(tmp_path / "approvals.db"))


def test_store_create_resolve(tmp_path):
    s = _store(tmp_path)
    aid = s.create(Action(type="send_email", summary="x", agent="a"), "raison", 0.7)
    assert s.get(aid)["status"] == "pending"
    assert len(s.list_pending()) == 1
    assert s.resolve(aid, "approve")["changed"] == 1
    assert s.get(aid)["decision"] == "approve"
    assert s.list_pending() == []
    # déjà résolu -> pas de changement
    assert s.resolve(aid, "deny")["changed"] == 0


def test_wait_returns_decision(tmp_path):
    s = _store(tmp_path)
    aid = s.create(Action(type="x", agent="a"), "r", 0.7)
    threading.Thread(target=lambda: (time.sleep(0.2), s.resolve(aid, "deny"))).start()
    assert s.wait(aid, timeout=3, poll=0.05) == "deny"


def test_wait_timeout(tmp_path):
    s = _store(tmp_path)
    aid = s.create(Action(type="x", agent="a"), "r", 0.7)
    assert s.wait(aid, timeout=0.3, poll=0.05) is None


def test_notifier_dry_run_approve(tmp_path, capsys):
    s = _store(tmp_path)
    n = SlackNotifier(store=s, poll_timeout=3)  # pas de token -> dry-run
    out = {}
    t = threading.Thread(target=lambda: out.__setitem__("ok", n.request_approval(
        Action(type="send_email", summary="remb", agent="bot"), "risque", 0.8)))
    t.start()
    time.sleep(0.2)
    pend = s.list_pending()
    assert len(pend) == 1
    s.resolve(pend[0]["id"], "approve")
    t.join(5)
    assert out["ok"] is True


def test_gate_hold_approved_then_denied(tmp_path, monkeypatch):
    monkeypatch.setenv("COLDNOTCH_AUDIT", str(tmp_path / "audit.jsonl"))
    s = _store(tmp_path)

    def always_risky(action, ctx=None):
        return RiskResult(0.9, "test hold")

    configure(policy=Policy(risk_fn=always_risky), notifier=SlackNotifier(store=s, poll_timeout=3))

    executed = {"n": 0}
    action = Action(type="send_email", summary="remboursement", agent="bot")

    # approuvé -> le corps s'exécute
    t = threading.Thread(target=lambda: _run_ok(action, executed))
    t.start(); time.sleep(0.2)
    s.resolve(s.list_pending()[0]["id"], "approve"); t.join(5)
    assert executed["n"] == 1

    # refusé -> Blocked, corps non exécuté
    blocked = {"v": False}
    t = threading.Thread(target=lambda: _run_deny(action, executed, blocked))
    t.start(); time.sleep(0.2)
    s.resolve(s.list_pending()[0]["id"], "deny"); t.join(5)
    assert blocked["v"] is True
    assert executed["n"] == 1  # inchangé

    # audit : 2 lignes, approved True puis False
    lines = [json.loads(l) for l in open(str(tmp_path / "audit.jsonl"), encoding="utf-8")]
    assert len(lines) == 2
    assert lines[0]["approved"] is True
    assert lines[1]["approved"] is False


def _run_ok(action, executed):
    with gate(action):
        executed["n"] += 1


def _run_deny(action, executed, blocked):
    try:
        with gate(action):
            executed["n"] += 1
    except Blocked:
        blocked["v"] = True
