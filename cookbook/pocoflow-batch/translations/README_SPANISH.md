# PocoFlow

> Orquestación ligera de flujos de trabajo LLM.
> Una evolución robusta de [PocketFlow](https://github.com/The-Pocket/PocketFlow).

Construido con amor por **Claude & digital-duck** 🦆

---

## Qué es

PocoFlow es un framework minimalista para construir pipelines de LLM como **grafos dirigidos de
nodos nano-ETL** que se comunican a través de un Store compartido y tipado.

Mantiene la mejor idea de PocketFlow — la abstracción `prep | exec | post` — y corrige
las debilidades que surgen en producción:

| Debilidad | Solución de PocoFlow |
|----------|-------------|
| Store de dict crudo — sin seguridad de tipos | `Store` con esquema opcional + `TypeError` en escrituras incorrectas |
| API de aristas `>>` ambigua | API única y clara: `.then("action", next_node)` |
| Sin soporte async integrado | `AsyncNode.exec_async()` — el framework maneja `asyncio.run()` |
| Sin observabilidad | Sistema de hooks: `node_start / node_end / node_error / flow_end` |
| Sin checkpointing | Snapshots JSON + **backend SQLite** con log de eventos completo |
| Sin soporte de ejecución prolongada | `run_background()` → `RunHandle` con estado, wait, cancel |
| Logging inconsistente | Integración **dd-logging** — estructurado, respaldado por archivos, con espacios de nombres |
| Sin visibilidad de flujos de trabajo | **UI monitor Streamlit** — tabla de ejecuciones en vivo, timeline, inspector de store |

**Dependencias:** [pocketflow](https://github.com/The-Pocket/PocketFlow) + [dd-logging](https://github.com/digital-duck/dd-logging)

---

## Instalación

```bash
# Core
pip install pocoflow

# Con UI monitor Streamlit
pip install "pocoflow[ui]"

# Desarrollo local (desde el monorepo digital-duck)
pip install -e ~/projects/digital-duck/dd-logging
pip install -e ~/projects/digital-duck/pocoflow"[ui,dev]"
```

---

## Inicio Rápido

```python
from pocoflow import Node, Flow, Store

class SummariseNode(Node):
    def prep(self, store):
        return store["document"]

    def exec(self, text):
        return llm.summarise(text)          # tu llamada LLM aquí

    def post(self, store, prep, summary):
        store["summary"] = summary
        return "done"

store = Store({"document": "...", "summary": ""})
Flow(start=SummariseNode(), db_path="pocoflow.db", flow_name="summarise").run(store)
print(store["summary"])
```

Luego abre el monitor:

```bash
streamlit run pocoflow/ui/monitor.py -- pocoflow.db
```

---

## Conceptos Centrales

### Node — nano-ETL

Cada nodo es una unidad de procesamiento de tres fases que mapea directamente a **Extract → Transform → Load**:

```
prep(store)              → Extract:   lee lo que este nodo necesita del store
exec(prep_result)        → Transform: hace el trabajo (puro — sin efectos secundarios en el store)
post(store, prep, exec)  → Load:      escribe resultados de vuelta, devuelve string de acción siguiente
```

| Fase | Paso ETL | Pureza |
|-------|----------|--------|
| `prep` | Extract | lee el store |
| `exec` | Transform | función pura — reintentable, testeable sin un store |
| `post` | Load + Route | escribe en el store, devuelve string de acción |

```python
from pocoflow import Node

class CallLLMNode(Node):
    max_retries = 3       # reintentar exec() automáticamente en fallo
    retry_delay = 1.0     # segundos entre reintentos

    def prep(self, store):
        return store["prompt"]

    def exec(self, prompt):
        return llm.call(prompt)   # reintentado hasta 3× en excepción

    def post(self, store, prep, response):
        store["response"] = response
        return "done"
```

### Store — estado compartido tipado

```python
from pocoflow import Store

store = Store(
    data={"query": "", "result": ""},
    schema={"query": str, "result": str},   # verificación de tipo en cada escritura
    name="my_pipeline",
)
store["query"] = "explain quantum entanglement"
store["query"] = 42          # ← lanza TypeError inmediatamente

# Observer: se dispara en cada escritura (logging, tracing, actualizaciones de UI)
store.add_observer(lambda key, old, new: print(f"{key}: {old!r} → {new!r}"))

# Snapshot / restauración JSON (respaldo ligero)
store.snapshot("/tmp/run_42/step_002.json")
store2 = Store.restore("/tmp/run_42/step_002.json")
```

### Flow — grafo dirigido con hooks

```python
from pocoflow import Flow, Store

# Conectar nodos con aristas nombradas sin ambigüedad
a.then("ok",    b)
a.then("error", c)
a.then("*",     fallback)   # comodín: coincide con cualquier acción no manejada

# Construir con persistencia SQLite
flow = Flow(
    start=a,
    flow_name="my_pipeline",    # etiqueta mostrada en la UI monitor
    db_path="pocoflow.db",      # SQLite: ejecuciones, eventos, checkpoints
    checkpoint_dir="/tmp/ckpt", # también escribe snapshots JSON (opcional)
    max_steps=50,               # protección contra bucles infinitos
)

# Hooks — conectar a cualquier logger, sink de métricas o barra de progreso
flow.on("node_start", lambda name, store: print(f"▶ {name}"))
flow.on("node_end",   lambda name, action, elapsed, store:
                          print(f"✓ {name} → {action}  ({elapsed:.2f}s)"))
flow.on("node_error", lambda name, exc, store: alert(name, exc))
flow.on("flow_end",   lambda steps, store: print(f"Done in {steps} steps"))

store = Store({"query": "..."})
flow.run(store)
```

### AsyncNode — subtareas paralelas

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

Implementa `exec_async()` — el framework lo llama vía `asyncio.run()`.
Usa `asyncio.gather()` dentro para verdaderas subtareas paralelas.

---

## Backend SQLite

Cuando se establece `db_path`, cada ejecución se registra completamente en una base de datos SQLite:

```
pf_runs        — una fila por ejecución de flujo (run_id, estado, timing, error)
pf_checkpoints — Snapshot del Store después de cada nodo (restaurable en cualquier paso)
pf_events      — log de eventos ordenado (flow_start → node_start/end/error → flow_end)
```

```python
from pocoflow import WorkflowDB

db = WorkflowDB("pocoflow.db")

# Listar todas las ejecuciones
for run in db.list_runs():
    print(run["run_id"], run["status"], run["total_steps"])

# Inspeccionar eventos para una ejecución
for event in db.get_events("my_pipeline-3f9a1b2c"):
    print(event["event"], event["node_name"], event["elapsed_ms"])

# Restaurar Store desde cualquier checkpoint
store = db.load_checkpoint("my_pipeline-3f9a1b2c", step=2)
```

El modo WAL está habilitado para que el monitor Streamlit pueda consultar mientras se ejecuta un flujo.

---

## Flujos de Trabajo de Larga Duración

Para flujos que toman minutos u horas, usa `run_background()` para evitar bloqueos:

```python
flow = Flow(start=my_node, db_path="pocoflow.db", flow_name="research")

# Retorna inmediatamente — el flujo se ejecuta en un hilo daemon
handle = flow.run_background(store)

print(handle.run_id)          # ej. "research-3f9a1b2c"
print(handle.status)          # "running"   (lee en vivo desde SQLite)

# Bloquear hasta completar (timeout opcional)
result = handle.wait(timeout=300)
print(handle.status)          # "completed"

# Cancelación cooperativa — se detiene entre nodos
handle.cancel()
```

### Reanudar después de un fallo

```python
from pocoflow import WorkflowDB, Flow

db = WorkflowDB("pocoflow.db")

# Encontrar la ejecución fallida
runs = [r for r in db.list_runs() if r["status"] == "failed"]
failed = runs[0]

# Restaurar store desde el último checkpoint exitoso
checkpoints = db.get_checkpoints(failed["run_id"])
last = checkpoints[-1]
store = db.load_checkpoint(failed["run_id"], step=last["step"])

# Reanudar desde el nodo después del último checkpoint
flow = Flow(start=my_flow_start, db_path="pocoflow.db")
flow.run(store, resume_from=node_after_crash)
```

---

## UI Monitor Streamlit

Visualiza y gestiona todas las ejecuciones de flujos de trabajo desde un navegador.

**Standalone:**
```bash
streamlit run pocoflow/ui/monitor.py -- pocoflow.db
```

**Embebido en cualquier página Streamlit:**
```python
from pocoflow.ui.monitor import render_workflow_monitor

render_workflow_monitor("pocoflow.db")
```

Características:
- **Tabla de ejecuciones** — ID de ejecución, nombre del flujo, insignia de estado (✅ 🔄 ❌), hora de inicio, duración, conteo de pasos
- **Auto-actualización** — activa con intervalos de 5 / 10 / 30 s; actualiza en vivo mientras los flujos se ejecutan
- **Pestaña Timeline** — log de eventos ordenado por ejecución: nombres de nodos, acciones, latencia por nodo (ms), errores
- **Pestaña Store Inspector** — deslizador de pasos para ver el estado del Store en cualquier checkpoint como tabla clave/valor + JSON crudo
- **Pestaña Resume** — genera un fragmento de código Python listo para pegar para reanudar desde el checkpoint seleccionado

---

## Logging

PocoFlow usa [dd-logging](https://github.com/digital-duck/dd-logging) para salida de log
estructurada, con espacios de nombres y respaldada por archivos.

```python
from pocoflow.logging import setup_logging, get_logger

# Configurar una vez al inicio de la app (ej. en punto de entrada CLI o cache_resource de Streamlit)
log_path = setup_logging("run", log_level="debug", adapter="openrouter")
# → logs/run-openrouter-20260217-143022.log

# En cualquier módulo
_log = get_logger("nodes.summarise")   # → pocoflow.nodes.summarise
_log.info("summarising  len=%d", len(text))
```

Jerarquía de loggers:
```
pocoflow
├── pocoflow.store
├── pocoflow.node
├── pocoflow.flow
├── pocoflow.db
└── pocoflow.runner
```

---

## Migrando desde PocketFlow

```python
# Antes
from pocketflow import Node, Flow

node_a >> node_b                 # crea arista "default" — causa UserWarning
node_a - "action" >> node_b      # arista nombrada (correcto pero inconsistente)
shared = {}                      # dict crudo — sin seguridad de tipos

# Después
from pocoflow import Node, Flow, Store

node_a.then("action", node_b)    # API única sin ambigüedad, siempre
shared = Store(data=shared_dict) # tipado, observable, con checkpoints
flow.run(shared)                 # dict plano también aceptado para compatibilidad hacia atrás
```

---

## Estructura del Proyecto

```
pocoflow/
  __init__.py      — API pública: Store, Node, AsyncNode, Flow, WorkflowDB, RunHandle
  store.py         — estado compartido tipado, observable, con checkpoints JSON
  node.py          — Node (sync) + AsyncNode (async) + retry
  flow.py          — ejecutor de grafo dirigido: hooks, checkpoints JSON + SQLite, background
  db.py            — WorkflowDB: esquema SQLite, CRUD para ejecuciones / checkpoints / eventos
  logging.py       — wrapper dd-logging (espacio de nombres pocoflow.*)
  runner.py        — RunHandle: estado, wait, cancel
  ui/
    monitor.py     — monitor de flujos de trabajo Streamlit (standalone + embebible)
examples/
  hello.py         — flujo mínimo de dos nodos con hooks
tests/
  test_pocoflow.py — 25 tests: Store, Node, Flow, WorkflowDB, RunHandle
docs/
  design.md        — arquitectura, decisiones de diseño, guía de migración
```

---

## Comparación con PocketFlow

| Característica | PocketFlow | PocoFlow v0.2 |
|---------|-----------|--------------|
| Tamaño del core | ~100 líneas | ~600 líneas |
| Estado compartido | dict crudo | `Store` tipado con esquema |
| API de aristas | `>>` y `- "action" >>` (confuso) | `.then("action", node)` únicamente |
| Nodos async | `asyncio.run()` manual por nodo | `AsyncNode.exec_async()` |
| Observabilidad | ninguna | sistema de hooks de 4 eventos |
| Checkpointing | ninguno | JSON + SQLite (`WorkflowDB`) |
| Log de eventos | ninguno | tabla `pf_events` — pista de auditoría completa |
| Ejecución prolongada | ninguna | `run_background()` → `RunHandle` |
| Retry | ninguno | `max_retries` + `retry_delay` en cualquier Node |
| Aristas comodín | ninguna | `.then("*", fallback)` |
| Logging | manual | dd-logging (espacio de nombres `pocoflow.*`) |
| UI Monitor | ninguna | Monitor Streamlit con auto-actualización |
| Deps externas | 0 | pocketflow + dd-logging (ambos solo stdlib) |

---

## Relación con PocketFlow

PocoFlow es espiritualmente un hijo de PocketFlow. Mantuvimos:
- La abstracción nano-ETL `prep | exec | post` — hermosa y correcta
- Cero dependencia de proveedores — trae tu propio cliente LLM
- Sin magia de framework — cada comportamiento es rastreable a código que puedes leer en minutos

Agregamos lo que los flujos de trabajo LLM en producción realmente demandan:
- `Store` tipado, observable, con checkpoints
- API de aristas `.then()` sin ambigüedad (no más `UserWarning`)
- `AsyncNode` con `exec_async()`