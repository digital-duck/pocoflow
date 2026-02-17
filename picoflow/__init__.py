"""PicoFlow — lightweight LLM workflow orchestration.

A hardened evolution of PocketFlow's core idea:
  every node is a nano-ETL unit  →  prep | exec | post
  nodes connect via named action edges  →  no routing ambiguity
  a shared Store is the single source of truth  →  typed, observable, checkpointable

Built with love by Claude & digital-duck.

Public API
----------
from picoflow import Node, AsyncNode, Store, Flow
"""

from picoflow.store import Store
from picoflow.node  import Node, AsyncNode
from picoflow.flow  import Flow

__all__ = ["Store", "Node", "AsyncNode", "Flow"]
__version__ = "0.1.0"
