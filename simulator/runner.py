"""Banc d'essai : rejoue les scénarios dans le gate, écrit un corpus étiqueté
et un rapport de gap (ce que le stub mots-clés attrape vs rate).

Le corpus est une DONNÉE SENSIBLE (carburant du futur moteur de risque) : il est
écrit dans .artifacts/ (gitignoré) et ne doit JAMAIS être committé.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from coldnotch import Action, AutoNotifier, Blocked, Policy, configure, gate

from . import agent, data_gen

SCENARIOS_DIR = Path(__file__).parent / "scenarios"
DEFAULT_OUT = Path(".artifacts") / "corpus.jsonl"


def load_scenarios() -> List[dict]:
    scenarios = []
    for path in sorted(SCENARIOS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["name"] = path.stem
        scenarios.append(data)
    return scenarios


def _action_dict(a: Action) -> dict:
    return {"type": a.type, "summary": a.summary, "payload": a.payload, "agent": a.agent}


def run(bots: int = 3, seed: int = 0, out: Path = DEFAULT_OUT) -> Tuple[List[dict], str]:
    """Lance `bots` agents rejouant tous les scénarios. Écrit le corpus, renvoie (corpus, rapport)."""
    scenarios = load_scenarios()
    rng = data_gen.make_rng(seed)

    # Le gate écrit un journal d'audit : on l'utilise comme source des verdicts.
    art = Path(".artifacts")
    art.mkdir(exist_ok=True)
    gate_audit = art / "_gate_audit.jsonl"
    if gate_audit.exists():
        gate_audit.unlink()
    os.environ["COLDNOTCH_AUDIT"] = str(gate_audit)

    # Le "stub actuel" : politique P1 (default_risk mots-clés), notifier non interactif.
    configure(policy=Policy(), notifier=AutoNotifier(approve=False))

    meta: List[dict] = []  # une entrée par action, dans l'ordre d'exécution
    for bot in range(bots):
        agent_name = f"bot-{bot}"
        for scn in scenarios:
            values = data_gen.sample_values(rng)
            history: List[Action] = []  # historique par agent (seam EvalContext.history)
            for act in agent.emit_actions(scn, agent_name, values):
                try:
                    with gate(act):
                        pass  # ALLOW / HOLD approuvé : exécuté (no-op ici)
                except Blocked:
                    pass  # HOLD refusé / BLOCK : non exécuté
                history.append(act)  # non lu par le stub mono-action (volontaire)
                meta.append(
                    {
                        "action": _action_dict(act),
                        "agent": agent_name,
                        "scenario": scn["name"],
                        "category": scn["category"],
                        "ground_truth_label": scn["expected_label"],
                    }
                )

    # Relire l'audit du gate : une ligne par action, même ordre que meta.
    audit_lines = [
        json.loads(line)
        for line in gate_audit.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(audit_lines) != len(meta):
        raise RuntimeError(f"audit ({len(audit_lines)}) != actions ({len(meta)})")

    corpus: List[dict] = []
    for m, a in zip(meta, audit_lines):
        corpus.append(
            {
                "action": m["action"],
                "agent": m["agent"],
                "scenario": m["scenario"],
                "category": m["category"],
                "ground_truth_label": m["ground_truth_label"],
                "decision": a["decision"],
                "risk": a["risk"],
                "reason": a["reason"],
            }
        )

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for row in corpus:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    return corpus, build_report(corpus, out, bots)


def build_report(corpus: List[dict], out: Path, bots: int) -> str:
    """Rapport de gap : attrapé vs raté par catégorie + précision/rappel vs ground truth."""
    # Verdict au niveau scénario : "attrapé" = au moins une action HOLD/BLOCK.
    insts: Dict[Tuple[str, str], dict] = {}
    for row in corpus:
        inst = insts.setdefault(
            (row["scenario"], row["agent"]),
            {"category": row["category"], "gt": row["ground_truth_label"], "flagged": False},
        )
        if row["decision"] in ("hold", "block"):
            inst["flagged"] = True

    cat = defaultdict(lambda: {"total": 0, "flagged": 0})
    tp = fn = fp = tn = 0
    for inst in insts.values():
        c = cat[inst["category"]]
        c["total"] += 1
        if inst["flagged"]:
            c["flagged"] += 1
        risky = inst["gt"] == "risky"
        if risky and inst["flagged"]:
            tp += 1
        elif risky and not inst["flagged"]:
            fn += 1
        elif not risky and inst["flagged"]:
            fp += 1
        else:
            tn += 1

    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0

    lines = [
        "=== RAPPORT DE GAP - stub mots-cles (P1) ===",
        f"corpus : {len(corpus)} actions, {len(insts)} instances de scenario ({bots} bots)",
        f"ecrit dans : {out} (gitignore, donnee sensible)",
        "",
        "Par categorie (instances ; attrape = au moins un HOLD/BLOCK) :",
    ]
    for name in sorted(cat):
        c = cat[name]
        note = ""
        if name.startswith("benign") and c["flagged"]:
            note = "   <- FAUX POSITIFS (vocabulaire a risque sans consequence)"
        if name == "risky_subtle":
            note = "   <- RATES : risque paraphrase (aucun mot-cle)"
        if name == "risky_chain":
            note = "   <- RATES : necessite le contexte (EvalContext.history), cf. moteur cloud"
        lines.append(f"  {name:<14} attrapes {c['flagged']}/{c['total']}{note}")

    chain = cat.get("risky_chain", {"flagged": 0, "total": 0})
    subtle = cat.get("risky_subtle", {"flagged": 0, "total": 0})
    trap = cat.get("benign_trap", {"flagged": 0, "total": 0})
    trap_ok = trap["total"] - trap["flagged"]
    lines += [
        "",
        "Ground truth (niveau scenario) :",
        f"  TP={tp}  FN={fn}  FP={fp}  TN={tn}",
        f"  precision = {prec:.2f}   rappel = {rec:.2f}",
        "",
        "GAPS du stub mots-cles (ce que le moteur de consequence, cloud/, comblera) :",
        f"  1. risque paraphrase : {subtle['flagged']}/{subtle['total']} attrapes -> rate la",
        "     consequence quand aucun mot-cle n'apparait (fait CHUTER LE RAPPEL).",
        f"  2. pieges benins     : {trap_ok}/{trap['total']} corrects -> flague a tort le",
        "     vocabulaire a risque sans consequence reelle (fait CHUTER LA PRECISION).",
        f"  3. enchainements     : {chain['flagged']}/{chain['total']} attrapes -> ne voit",
        "     pas la sequence (cf. EvalContext.history).",
    ]
    return "\n".join(lines)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="simulator", description="Banc d'essai du gate Coldnotch.")
    p.add_argument("--out", default=str(DEFAULT_OUT), help="chemin du corpus JSONL (gitignore)")
    p.add_argument("--report", default=None, help="chemin du rapport (defaut : stdout)")
    p.add_argument("--bots", type=int, default=3, help="nombre d'agents")
    p.add_argument("--seed", type=int, default=0, help="graine RNG (reproductibilite)")
    args = p.parse_args(argv)

    _corpus, report = run(bots=args.bots, seed=args.seed, out=Path(args.out))
    if args.report:
        Path(args.report).write_text(report + "\n", encoding="utf-8")
        print(f"rapport ecrit dans {args.report}")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
