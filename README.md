# Coldnotch

> Le plan de contrôle des actions d'agent. Autorise, met en attente ou bloque
> chaque action d'un agent IA avant exécution, avec preuve auditable.

Premiers résultats, benchmark interne de 35 cas adversariaux :

- Approche naïve (mots-clés) : précision **0** / rappel **0** sur des actions adversariales inédites.
- Moteur de conséquence : précision **1.00** / rappel **0.95**.
- Gate **< 1 ms** (p95 0,7 ms), **~0,0001 EUR** par action.

Ce ne sont pas des garanties : premiers chiffres mesurés sur un banc interne, trafic synthétique.

## Le problème

Les agents IA agissent : ils envoient, paient, suppriment. Une permission dit
"peut envoyer un email" ; elle ne voit pas que CE mail promet un remboursement de
240 EUR. Coldnotch décide sur la **conséquence** de l'action, avant exécution.

## Installation

```bash
pip install coldnotch
# Disponible dès la publication PyPI. En local, depuis ce dépôt :
pip install -e .
```

## Quickstart

```python
from coldnotch import Action, Policy, configure, gate, Blocked

# Politique : scoring de risque par mots-clés (stub par défaut) + types interdits.
configure(policy=Policy(block_types={"exec_shell"}))

def send_email(to: str, body: str) -> None:
    ...  # votre code

# 1) Action de routine -> ALLOW : le corps du "with" s'exécute.
with gate(Action(type="send_email", summary="Confirmation de rendez-vous", agent="support-bot")):
    send_email("client@example.com", "Votre rendez-vous est confirme.")

# 2) Promesse de remboursement -> HOLD : validation humaine requise avant exécution.
try:
    with gate(Action(type="send_email",
                     summary="Nous vous promettons un remboursement de 240 EUR",
                     agent="support-bot")):
        send_email("client@example.com", "Remboursement en cours.")
except Blocked as blocked:
    print(blocked)  # send_email [hold] : mots-clés à risque : rembours

# 3) Commande shell -> BLOCK : jamais exécutée.
try:
    with gate(Action(type="exec_shell", summary="rm -rf /data", agent="ops-bot")):
        run_shell("rm -rf /data")
except Blocked as blocked:
    print(blocked)  # exec_shell [block] : type 'exec_shell' interdit par la politique
```

Trois verdicts, un seul point de contrôle : **ALLOW** (exécuté, tracé), **HOLD**
(mis en attente d'un humain), **BLOCK** (stoppé avant tout effet). Par défaut, un
HOLD demande une validation en console ; branchez Slack (ci-dessous) pour une vraie
boucle humaine. Le scoring est enfichable : `Policy(risk_fn=votre_fonction)`.

## Validation humaine (Slack)

```python
from coldnotch import Policy, configure, SlackNotifier, ApprovalStore

store = ApprovalStore()  # file d'approbations SQLite, partagée avec le serveur
configure(
    policy=Policy(block_types={"exec_shell"}),
    notifier=SlackNotifier(store=store),  # SLACK_BOT_TOKEN + SLACK_CHANNEL via l'env
)
```

Sur un HOLD, une carte **Approuver / Refuser** est postée dans Slack ; `gate()`
attend le clic, puis exécute l'action ou lève `Blocked`. Le clic est reçu par un
serveur d'approbation minimal (extra optionnel, FastAPI, auto-hébergeable) :

```bash
pip install "coldnotch[server]"
uvicorn coldnotch.approval_server:app
# Pointez l'URL d'interactivité de votre app Slack vers .../slack/actions
```

## Journal d'audit

Chaque décision est journalisée en JSONL append-only (chemin via `COLDNOTCH_AUDIT`,
défaut `coldnotch_audit.jsonl`) :

```json
{"ts":"2026-07-02T09:41:03.187000+00:00","agent":"support-bot","type":"send_email","summary":"Nous vous promettons un remboursement de 240 EUR","decision":"hold","reason":"mots-clés à risque : rembours","risk":0.6,"approved":true}
```

Qui (`agent`), quoi (`type`, `summary`), le verdict (`decision`), pourquoi
(`reason`, `risk`) et s'il a été approuvé (`approved`). Une ligne par action,
exportable vers votre SIEM.

## Open-core

Le cœur (ce dépôt, Apache-2.0) est gratuit et complet : gate ALLOW/HOLD/BLOCK,
règles, validation humaine Slack, journal d'audit, avec un scoring de risque de
base (stub mots-clés, enfichable via `risk_fn`).

Le **moteur de conséquence** (qui comprend le risque même sans mot-clé et attrape
les enchaînements, par exemple une lecture de secret suivie d'un envoi externe) est
le composant commercial : c'est lui qui produit le before/after ci-dessus. Il se
branche sur le même seam, `Policy(risk_fn=...)`, sans changer votre code. Contact :
hello@coldnotch.com.

## Statut

Accès anticipé. L'API peut encore évoluer.

## Licence

Apache-2.0.
