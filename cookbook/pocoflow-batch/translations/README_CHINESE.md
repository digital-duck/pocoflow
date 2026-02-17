# PocoFlow

> 轻量级 LLM 工作流编排。
> [PocketFlow](https://github.com/The-Pocket/PocketFlow) 的强化演进版本。

由 **Claude & digital-duck** 用心构建 🦆

---

## 简介

PocoFlow 是一个用于构建 LLM 流水线的极简框架，采用**有向图的纳米 ETL 节点**通过共享的类型化 Store 进行通信。

它保留了 PocketFlow 最好的想法 —— `prep | exec | post` 抽象 —— 并修复了在生产环境中暴露的弱点：

| 弱点 | PocoFlow 修复 |
|----------|-------------|
| 原始字典存储 — 无类型安全 | 带可选模式的 `Store` + 错误写入时抛出 `TypeError` |
| 模糊的 `>>` 边缘 API | 单一清晰的 API：`.then("action", next_node)` |
| 无内置异步支持 | `AsyncNode.exec_async()` — 框架处理 `asyncio.run()` |
| 无可观测性 | 钩子系统：`node_start / node_end / node_error / flow_end` |
| 无检查点功能 | JSON 快照 + **SQLite 后端**，完整事件日志 |
| 无长时间运行支持 | `run_background()` → `RunHandle`，带状态、等待、取消功能 |
| 日志记录不一致 | **dd-logging** 集成 — 结构化、文件支持、命名空间化 |
| 无工作流可视化 | **Streamlit 监控 UI** — 实时运行表、时间线、存储检查器 |

**依赖项：** [pocketflow](https://github.com/The-Pocket/PocketFlow) + [dd-logging](https://github.com/digital-duck/dd-logging)

---

## 安装

```bash
# 核心
pip install pocoflow

# 包含 Streamlit 监控 UI
pip install "pocoflow[ui]"

# 本地开发（从 digital-duck 单体仓库）
pip install -e ~/projects/digital-duck/dd-logging
pip install -e ~/projects/digital-duck/pocoflow"[ui,dev]"
```

---

## 快速开始

```python
from pocoflow import Node, Flow, Store

class SummariseNode(Node):
    def prep(self, store):
        return store["document"]

    def exec(self, text):
        return llm.summarise(text)          # 你的 LLM 调用

    def post(self, store, prep, summary):
        store["summary"] = summary
        return "done"

store = Store({"document": "...", "summary": ""})
Flow(start=SummariseNode(), db_path="pocoflow.db", flow_name="summarise").run(store)
print(store["summary"])
```

然后打开监控界面：

```bash
streamlit run pocoflow/ui/monitor.py -- pocoflow.db
```

---

## 核心概念

### Node — 纳米 ETL

每个节点都是一个三阶段处理单元，直接映射到 **Extract → Transform → Load**：

```
prep(store)              → Extract:   从存储中读取该节点需要的内容
exec(prep_result)        → Transform: 执行工作（纯函数 — 无存储副作用）
post(store, prep, exec)  → Load:      将结果写回，返回下一个动作字符串
```

| 阶段 | ETL 步骤 | 纯度 |
|-------|----------|--------|
| `prep` | Extract | 读取存储 |
| `exec` | Transform | 纯函数 — 可重试、可在无存储情况下测试 |
| `post` | Load + Route | 写入存储，返回动作字符串 |

```python
from pocoflow import Node

class CallLLMNode(Node):
    max_retries = 3       # 失败时自动重试 exec()
    retry_delay = 1.0     # 重试间隔秒数

    def prep(self, store):
        return store["prompt"]

    def exec(self, prompt):
        return llm.call(prompt)   # 异常时最多重试 3 次

    def post(self, store, prep, response):
        store["response"] = response
        return "done"
```

### Store — 类型化共享状态

```python
from pocoflow import Store

store = Store(
    data={"query": "", "result": ""},
    schema={"query": str, "result": str},   # 每次写入时进行类型检查
    name="my_pipeline",
)
store["query"] = "explain quantum entanglement"
store["query"] = 42          # ← 立即抛出 TypeError

# 观察者：每次写入时触发（日志记录、追踪、UI 更新）
store.add_observer(lambda key, old, new: print(f"{key}: {old!r} → {new!r}"))

# JSON 快照 / 恢复（轻量级备份）
store.snapshot("/tmp/run_42/step_002.json")
store2 = Store.restore("/tmp/run_42/step_002.json")
```

### Flow — 带钩子的有向图

```python
from pocoflow import Flow, Store

# 使用明确命名的边连接节点
a.then("ok",    b)
a.then("error", c)
a.then("*",     fallback)   # 通配符：匹配任何未处理的动作

# 使用 SQLite 持久化构建
flow = Flow(
    start=a,
    flow_name="my_pipeline",    # 监控 UI 中显示的标签
    db_path="pocoflow.db",      # SQLite：运行、事件、检查点
    checkpoint_dir="/tmp/ckpt", # 同时写入 JSON 快照（可选）
    max_steps=50,               # 防止无限循环
)

# 钩子 — 可连接到任何日志记录器、指标接收器或进度条
flow.on("node_start", lambda name, store: print(f"▶ {name}"))
flow.on("node_end",   lambda name, action, elapsed, store:
                          print(f"✓ {name} → {action}  ({elapsed:.2f}s)"))
flow.on("node_error", lambda name, exc, store: alert(name, exc))
flow.on("flow_end",   lambda steps, store: print(f"Done in {steps} steps"))

store = Store({"query": "..."})
flow.run(store)
```

### AsyncNode — 并行子任务

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

实现 `exec_async()` — 框架通过 `asyncio.run()` 调用它。
在内部使用 `asyncio.gather()` 实现真正的并行子任务。

---

## SQLite 后端

当设置 `db_path` 时，每次运行都会完整记录在 SQLite 数据库中：

```
pf_runs        — 每次流程执行一行（run_id、状态、时间、错误）
pf_checkpoints — 每个节点后的 Store 快照（可在任何步骤恢复）
pf_events      — 有序事件日志（flow_start → node_start/end/error → flow_end）
```

```python
from pocoflow import WorkflowDB

db = WorkflowDB("pocoflow.db")

# 列出所有运行
for run in db.list_runs():
    print(run["run_id"], run["status"], run["total_steps"])

# 检查运行的事件
for event in db.get_events("my_pipeline-3f9a1b2c"):
    print(event["event"], event["node_name"], event["elapsed_ms"])

# 从任何检查点恢复 Store
store = db.load_checkpoint("my_pipeline-3f9a1b2c", step=2)
```

启用了 WAL 模式，因此 Streamlit 监控界面可以在流程运行时进行轮询。

---

## 长时间运行的工作流

对于需要几分钟或几小时的流程，使用 `run_background()` 避免阻塞：

```python
flow = Flow(start=my_node, db_path="pocoflow.db", flow_name="research")

# 立即返回 — 流程在守护线程中运行
handle = flow.run_background(store)

print(handle.run_id)          # 例如 "research-3f9a1b2c"
print(handle.status)          # "running"（从 SQLite 实时读取）

# 阻塞直到完成（可选超时）
result = handle.wait(timeout=300)
print(handle.status)          # "completed"

# 协作式取消 — 在节点之间停止
handle.cancel()
```

### 崩溃后恢复

```python
from pocoflow import WorkflowDB, Flow

db = WorkflowDB("pocoflow.db")

# 查找失败的运行
runs = [r for r in db.list_runs() if r["status"] == "failed"]
failed = runs[0]

# 从最后一个成功的检查点恢复存储
checkpoints = db.get_checkpoints(failed["run_id"])
last = checkpoints[-1]
store = db.load_checkpoint(failed["run_id"], step=last["step"])

# 从最后一个检查点之后的节点恢复
flow = Flow(start=my_flow_start, db_path="pocoflow.db")
flow.run(store, resume_from=node_after_crash)
```

---

## Streamlit 监控 UI

从浏览器可视化和管理所有工作流运行。

**独立运行：**
```bash
streamlit run pocoflow/ui/monitor.py -- pocoflow.db
```

**嵌入任何 Streamlit 页面：**
```python
from pocoflow.ui.monitor import render_workflow_monitor

render_workflow_monitor("pocoflow.db")
```

功能：
- **运行表** — 运行 ID、流程名称、状态徽章（✅ 🔄 ❌）、开始时间、持续时间、步骤数
- **自动刷新** — 可设置 5 / 10 / 30 秒间隔切换；流程运行时实时更新
- **时间线标签页** — 每次运行的有序事件日志：节点名称、动作、每个节点的延迟（ms）、错误
- **Store 检查器标签页** — 步骤滑块，可查看任何检查点的 Store 状态（键值表 + 原始 JSON）
- **恢复标签页** — 生成可直接粘贴的 Python 代码片段，用于从选定的检查点恢复

---

## 日志记录

PocoFlow 使用 [dd-logging](https://github.com/digital-duck/dd-logging) 进行结构化、
命名空间化、文件支持的日志输出。

```python
from pocoflow.logging import setup_logging, get_logger

# 在应用启动时设置一次（例如在 CLI 入口点或 Streamlit cache_resource 中）
log_path = setup_logging("run", log_level="debug", adapter="openrouter")
# → logs/run-openrouter-20260217-143022.log

# 在任何模块中
_log = get_logger("nodes.summarise")   # → pocoflow.nodes.summarise
_log.info("summarising  len=%d", len(text))
```

日志记录器层次结构：
```
pocoflow
├── pocoflow.store
├── pocoflow.node
├── pocoflow.flow
├── pocoflow.db
└── pocoflow.runner
```

---

## 从 PocketFlow 迁移

```python
# 之前
from pocketflow import Node, Flow

node_a >> node_b                 # 创建 "default" 边 — 导致 UserWarning
node_a - "action" >> node_b      # 命名边（正确但不一致）
shared = {}                      # 原始字典 — 无类型安全

# 之后
from pocoflow import Node, Flow, Store

node_a.then("action", node_b)    # 单一明确的 API，始终如一
shared = Store(data=shared_dict) # 类型化、可观测、可检查点
flow.run(shared)                 # 为向后兼容也接受普通字典
```

---

## 项目布局

```
pocoflow/
  __init__.py      — 公共 API：Store、Node、AsyncNode、Flow、WorkflowDB、RunHandle
  store.py         — 类型化、可观测、JSON 可检查点的共享状态
  node.py          — Node（同步）+ AsyncNode（异步）+ 重试
  flow.py          — 有向图运行器：钩子、JSON + SQLite 检查点、后台运行
  db.py            — WorkflowDB：SQLite 模式，运行/检查点/事件的 CRUD
  logging.py       — dd-logging 包装器（pocoflow.* 命名空间）
  runner.py        — RunHandle：状态、等待、取消
  ui/
    monitor.py     — Streamlit 工作流监控器（独立 + 可嵌入）
examples/
  hello.py         — 带钩子的最小双节点流程
tests/
  test_pocoflow.py — 25 个测试：Store、Node、Flow、WorkflowDB、RunHandle
docs/
  design.md        — 架构、设计决策、迁移指南
```

---

## 与 PocketFlow 的比较

| 功能 | PocketFlow | PocoFlow v0.2 |
|---------|-----------|--------------|
| 核心大小 | ~100 行 | ~600 行 |
| 共享状态 | 原始字典 | 带模式的类型化 `Store` |
| 边缘 API | `>>` 和 `- "action" >>`（令人困惑） | 仅 `.then("action", node)` |
| 异步节点 | 每个节点手动 `asyncio.run()` | `AsyncNode.exec_