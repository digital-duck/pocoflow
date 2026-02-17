# PocoFlow

> Orchestration légère de workflows LLM.
> Une évolution renforcée de [PocketFlow](https://github.com/The-Pocket/PocketFlow).

Construit avec amour par **Claude & digital-duck** 🦆

---

## Ce que c'est

PocoFlow est un framework minimal pour construire des pipelines LLM sous forme de **graphes orientés de
nœuds nano-ETL** communiquant via un Store partagé et typé.

Il conserve la meilleure idée de PocketFlow — l'abstraction `prep | exec | post` — et corrige
les faiblesses qui apparaissent en production :

| Faiblesse | Correction PocoFlow |
|----------|-------------|
| Store dict brut — pas de sécurité de type | `Store` avec schéma optionnel + `TypeError` sur les écritures invalides |
| API d'arêtes `>>` ambiguë | API unique claire : `.then("action", next_node)` |
| Pas de support async intégré | `AsyncNode.exec_async()` — le framework gère `asyncio.run()` |
| Pas d'observabilité | Système de hooks : `node_start / node_end / node_error / flow_end` |
| Pas de point de contrôle | Snapshots JSON + **backend SQLite** avec journal d'événements complet |
| Pas de support long-running | `run_background()` → `RunHandle` avec status, wait, cancel |
| Logging incohérent | Intégration **dd-logging** — structuré, sauvegardé en fichier, avec namespace |
| Pas de visibilité de workflow | **UI de monitoring Streamlit** — table des exécutions en direct, timeline, inspecteur de store |

**Dépendances :** [pocketflow](https://github.com/The-Pocket/PocketFlow) + [dd-logging](https://github.com/digital-duck/dd-logging)

---

## Installation

```bash
# Core
pip install pocoflow

# Avec UI de monitoring Streamlit
pip install "pocoflow[ui]"

# Développement local (depuis le monorepo digital-duck)
pip install -e ~/projects/digital-duck/dd-logging
pip install -e ~/projects/digital-duck/pocoflow"[ui,dev]"
```

---

## Démarrage rapide

```python
from pocoflow import Node, Flow, Store

class SummariseNode(Node):
    def prep(self, store):
        return store["document"]

    def exec(self, text):
        return llm.summarise(text)          # votre appel LLM ici

    def post(self, store, prep, summary):
        store["summary"] = summary
        return "done"

store = Store({"document": "...", "summary": ""})
Flow(start=SummariseNode(), db_path="pocoflow.db", flow_name="summarise").run(store)
print(store["summary"])
```

Puis ouvrez le moniteur :

```bash
streamlit run pocoflow/ui/monitor.py -- pocoflow.db
```

---

## Concepts de base

### Node — nano-ETL

Chaque nœud est une unité de traitement en trois phases qui correspond directement à **Extract → Transform → Load** :

```
prep(store)              → Extract:   lit ce dont ce nœud a besoin depuis le store
exec(prep_result)        → Transform: fait le travail (pur — pas d'effets de bord sur le store)
post(store, prep, exec)  → Load:      écrit les résultats, retourne la chaîne d'action suivante
```

| Phase | Étape ETL | Pureté |
|-------|----------|--------|
| `prep` | Extract | lit le store |
| `exec` | Transform | fonction pure — réessayable, testable sans store |
| `post` | Load + Route | écrit dans le store, retourne une chaîne d'action |

```python
from pocoflow import Node

class CallLLMNode(Node):
    max_retries = 3       # réessaie exec() automatiquement en cas d'échec
    retry_delay = 1.0     # secondes entre les réessais

    def prep(self, store):
        return store["prompt"]

    def exec(self, prompt):
        return llm.call(prompt)   # réessayé jusqu'à 3× en cas d'exception

    def post(self, store, prep, response):
        store["response"] = response
        return "done"
```

### Store — état partagé typé

```python
from pocoflow import Store

store = Store(
    data={"query": "", "result": ""},
    schema={"query": str, "result": str},   # vérifié à chaque écriture
    name="my_pipeline",
)
store["query"] = "explain quantum entanglement"
store["query"] = 42          # ← lève TypeError immédiatement

# Observer : déclenché à chaque écriture (logging, tracing, mises à jour UI)
store.add_observer(lambda key, old, new: print(f"{key}: {old!r} → {new!r}"))

# Snapshot / restauration JSON (sauvegarde légère)
store.snapshot("/tmp/run_42/step_002.json")
store2 = Store.restore("/tmp/run_42/step_002.json")
```

### Flow — graphe orienté avec hooks

```python
from pocoflow import Flow, Store

# Câble les nœuds avec des arêtes nommées non ambiguës
a.then("ok",    b)
a.then("error", c)
a.then("*",     fallback)   # wildcard : correspond à toute action non gérée

# Construit avec persistance SQLite
flow = Flow(
    start=a,
    flow_name="my_pipeline",    # label affiché dans l'UI de monitoring
    db_path="pocoflow.db",      # SQLite : runs, événements, checkpoints
    checkpoint_dir="/tmp/ckpt", # écrit aussi des snapshots JSON (optionnel)
    max_steps=50,               # protection contre les boucles infinies
)

# Hooks — connectez à n'importe quel logger, sink de métriques, ou barre de progression
flow.on("node_start", lambda name, store: print(f"▶ {name}"))
flow.on("node_end",   lambda name, action, elapsed, store:
                          print(f"✓ {name} → {action}  ({elapsed:.2f}s)"))
flow.on("node_error", lambda name, exc, store: alert(name, exc))
flow.on("flow_end",   lambda steps, store: print(f"Terminé en {steps} étapes"))

store = Store({"query": "..."})
flow.run(store)
```

### AsyncNode — sous-tâches parallèles

```python
from pocoflow import AsyncNode
import asyncio

class FetchNode(AsyncNode):
    def prep(self, store):
        return store["urls"]

    async def exec_async(self, urls):
        return await asyncio.gather(*[fetch(u) for u in urls])

    def post(self, store, prep, results):
        store["pages"] = results
        return "done"
```

Implémentez `exec_async()` — le framework l'appelle via `asyncio.run()`.
Utilisez `asyncio.gather()` à l'intérieur pour de vraies sous-tâches parallèles.

---

## Backend SQLite

Quand `db_path` est défini, chaque exécution est entièrement enregistrée dans une base de données SQLite :

```
pf_runs        — une ligne par exécution de flow (run_id, status, timing, error)
pf_checkpoints — Snapshot du Store après chaque nœud (restaurable à n'importe quelle étape)
pf_events      — journal d'événements ordonné (flow_start → node_start/end/error → flow_end)
```

```python
from pocoflow import WorkflowDB

db = WorkflowDB("pocoflow.db")

# Liste toutes les exécutions
for run in db.list_runs():
    print(run["run_id"], run["status"], run["total_steps"])

# Inspecte les événements d'une exécution
for event in db.get_events("my_pipeline-3f9a1b2c"):
    print(event["event"], event["node_name"], event["elapsed_ms"])

# Restaure le Store depuis n'importe quel checkpoint
store = db.load_checkpoint("my_pipeline-3f9a1b2c", step=2)
```

Le mode WAL est activé pour que le moniteur Streamlit puisse interroger pendant qu'un flow s'exécute.

---

## Workflows long-running

Pour les flows qui prennent des minutes ou des heures, utilisez `run_background()` pour éviter le blocage :

```python
flow = Flow(start=my_node, db_path="pocoflow.db", flow_name="research")

# Retourne immédiatement — le flow s'exécute dans un thread daemon
handle = flow.run_background(store)

print(handle.run_id)          # ex. "research-3f9a1b2c"
print(handle.status)          # "running"   (lit en direct depuis SQLite)

# Bloque jusqu'à la fin (timeout optionnel)
result = handle.wait(timeout=300)
print(handle.status)          # "completed"

# Annulation coopérative — s'arrête entre les nœuds
handle.cancel()
```

### Reprise après crash

```python
from pocoflow import WorkflowDB, Flow

db = WorkflowDB("pocoflow.db")

# Trouve l'exécution échouée
runs = [r for r in db.list_runs() if r["status"] == "failed"]
failed = runs[0]

# Restaure le store depuis le dernier checkpoint réussi
checkpoints = db.get_checkpoints(failed["run_id"])
last = checkpoints[-1]
store = db.load_checkpoint(failed["run_id"], step=last["step"])

# Reprend depuis le nœud après le dernier checkpoint
flow = Flow(start=my_flow_start, db_path="pocoflow.db")
flow.run(store, resume_from=node_after_crash)
```

---

## UI de monitoring Streamlit

Visualisez et gérez toutes les exécutions de workflow depuis un navigateur.

**Autonome :**
```bash
streamlit run pocoflow/ui/monitor.py -- pocoflow.db
```

**Intégré dans n'importe quelle page Streamlit :**
```python
from pocoflow.ui.monitor import render_workflow_monitor

render_workflow_monitor("pocoflow.db")
```

Fonctionnalités :
- **Table des exécutions** — ID d'exécution, nom du flow, badge de statut (✅ 🔄 ❌), heure de début, durée, nombre d'étapes
- **Auto-refresh** — activez avec des intervalles de 5 / 10 / 30 s ; mises à jour en direct pendant l'exécution des flows
- **Onglet Timeline** — journal d'événements ordonné par exécution : noms de nœuds, actions, latence par nœud (ms), erreurs
- **Onglet Store Inspector** — curseur d'étape pour voir l'état du Store à n'importe quel checkpoint sous forme de table clé/valeur + JSON brut
- **Onglet Resume** — génère un extrait de code Python prêt à coller pour reprendre depuis le checkpoint sélectionné

---

## Logging

PocoFlow utilise [dd-logging](https://github.com/digital-duck/dd-logging) pour une sortie de log structurée,
avec namespace et sauvegarde en fichier.

```python
from pocoflow.logging import setup_logging, get_logger

# Configurez une fois au démarrage de l'application (ex. dans le point d'entrée CLI ou Streamlit cache_resource)
log_path = setup_logging("run", log_level="debug", adapter="openrouter")
# → logs/run-openrouter-20260217-143022.log

# Dans n'importe quel module
_log = get_logger("nodes.summarise")   # → pocoflow.nodes.summarise
_log.info("summarising  len=%d", len(text))
```

Hiérarchie des loggers :
```
pocoflow
├── pocoflow.store
├── pocoflow.node
├── pocoflow.flow
├── pocoflow.db
└── pocoflow.runner
```

---

## Migration depuis PocketFlow

```python
# Avant
from pocketflow import Node, Flow

node_a >> node_b                 # crée une arête "default" — cause un UserWarning
node_a - "action" >> node_b      # arête nommée (correct mais incohérent)
shared = {}                      # dict brut — pas de sécurité de type

# Après
from pocoflow import Node, Flow, Store

node_a.then("action", node_b)    # API unique non ambiguë, toujours
shared = Store(data=shared_dict) # typé, observable, avec checkpoints
flow.run(shared)                 # dict brut aussi accepté pour rétrocompatibilité
```

---

## Structure du projet

```
pocoflow/
  __init__.py      — API publique : Store, Node, AsyncNode, Flow, WorkflowDB, RunHandle
  store.py         — état partagé typé, observable, avec checkpoints JSON
  node.py          — Node (sync) + AsyncNode (async) + retry
  flow.py          — exécuteur de graphe orienté : hooks, checkpoints JSON + SQLite, background
  db.py            — WorkflowDB : schéma SQLite, CRUD pour runs / checkpoints / événements
  logging.py       — wrapper dd-logging (namespace pocoflow.*)
  runner.py        — RunHandle : status, wait, cancel
  ui/
    monitor.py     — moniteur de workflow Streamlit (autonome + intégrable)
examples/
  hello.py         — flow minimal à deux nœuds avec hooks
tests/
  test_pocoflow.py — 25 tests : Store, Node, Flow, WorkflowDB, RunHandle
docs/
  design.md        — architecture, décisions de conception, guide de migration
```

---

## Comparaison avec PocketFlow

| Fonctionnalité | PocketFlow | PocoFlow v0.2 |
|---------|-----------|--------------|
| Taille du core | ~100 lignes | ~600 lignes |
| État partagé | dict brut | `Store` typé avec schéma |
| API d'arêtes | `>>` et `- "action" >>` (confus) | `.then("action", node)` uniquement |
| Nœuds async | `asyncio.run()` manuel par nœud | `AsyncNode.exec_async()` |
| Observabilité | aucune | système de hooks à 4 événements |
| Checkpointing | aucun | JSON + SQLite (`WorkflowDB`) |
| Journal d'événements | aucun | table `pf_events` — piste d'audit complète |
| Long-running | aucun | `run_background()` → `RunHandle` |
| Retry | aucun | `max_retries` + `retry_delay` sur n'importe quel Node |
| Arêtes wildcard | aucune | `.then("*", fallback)` |
| Logging | manuel | dd-logging (namespace `pocoflow.*`) |
| UI de monitoring | aucune | Moniteur Streamlit avec auto-refresh |
| Dépendances externes | 0 | pocketflow + dd-logging (toutes deux stdlib uniquement) |

---

## Relation avec PocketFlow

PocoFlow est spirituellement un enfant de PocketFlow.