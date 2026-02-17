"""PocoFlow — lightweight LLM workflow orchestration.

A hardened evolution of PocketFlow's core idea:
  every node is a nano-ETL unit  →  prep | exec | post
  nodes connect via named action edges  →  no routing ambiguity
  a shared Store is the single source of truth  →  typed, observable, checkpointable

Built with love by Claude & digital-duck.

Public API
----------
from pocoflow import Node, AsyncNode, Store, Flow
"""

from pocoflow.store  import Store
from pocoflow.node   import Node, AsyncNode
from pocoflow.flow   import Flow
from pocoflow.db     import WorkflowDB
from pocoflow.runner import RunHandle

__all__ = ["Store", "Node", "AsyncNode", "Flow", "WorkflowDB", "RunHandle"]
__version__ = "0.2.0"
