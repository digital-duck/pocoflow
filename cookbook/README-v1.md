# PocoFlow Cookbook

Ported from [PocketFlow cookbook](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook), adapted for PocoFlow's API (`Store`, `.then()`, `AsyncNode`, etc.).

## Porting Progress

| # | Example | Validates | Phase | Status |
|---|---------|-----------|-------|--------|
| 1 | pocoflow-chat | Basic LLM node, self-loop, retry | 1 - Core | Done - OK|
| 2 | pocoflow-node | Single node lifecycle: prep/exec/post | 1 - Core | Done - OK|
| 3 | pocoflow-flow | Multi-node wiring, action routing | 1 - Core | Done - OK|
| 4 | pocoflow-batch | Batch processing patterns | 1 - Core | Done - OK |
| 5 | pocoflow-async-basic | AsyncNode + exec_async() | 1 - Core | Done - OK |
| 6 | pocoflow-structured-output | LLM + JSON parsing, retry on bad output | 1 - Core | Done - OK |
| 7 | pocoflow-chat-memory | Chat + conversation persistence | 1 - Core | Done - OK |
| 8 | pocoflow-chat-guardrail | Input/output guardrails | 2 - Safety | Pending |
| 9 | pocoflow-agent | Tool-calling agent loop | 2 - Safety | Done |
| 10 | pocoflow-agent-skills | Agent with multiple skills | 2 - Safety | Pending |
| 11 | pocoflow-supervisor | Multi-agent supervisor | 2 - Safety | Done |
| 12 | pocoflow-workflow | Multi-step workflow | 3 - Patterns | Done |
| 13 | pocoflow-batch-flow | Batch over flows | 3 - Patterns | Done |
| 14 | pocoflow-batch-node | Batch over nodes | 3 - Patterns | Done |
| 15 | pocoflow-map-reduce | Map-reduce pattern | 3 - Patterns | Done |
| 16 | pocoflow-parallel-batch | Parallel batch processing | 3 - Patterns | Done |
| 17 | pocoflow-parallel-batch-flow | Parallel batch over flows | 3 - Patterns | Done |
| 18 | pocoflow-nested-batch | Nested batch processing | 3 - Patterns | Done |
| 19 | pocoflow-majority-vote | Consensus via majority vote | 3 - Patterns | Pending |
| 20 | pocoflow-communication | Inter-node communication | 3 - Patterns | Pending |
| 21 | pocoflow-rag | Retrieval-augmented generation | 4 - LLM Apps | Done |
| 22 | pocoflow-structured-output | Structured LLM output | 4 - LLM Apps | Pending |
| 23 | pocoflow-thinking | Chain-of-thought reasoning | 4 - LLM Apps | Done |
| 24 | pocoflow-code-generator | Code generation pipeline | 4 - LLM Apps | Done |
| 25 | pocoflow-text2sql | Natural language to SQL | 4 - LLM Apps | Done |
| 26 | pocoflow-llm-streaming | LLM streaming responses | 4 - LLM Apps | Done |
| 27 | pocoflow-hello-world | Minimal hello world | 4 - LLM Apps | Done |
| 28 | pocoflow-tao | Tao philosophy example | 4 - LLM Apps | Pending |
| 29 | pocoflow-cli-hitl | CLI human-in-the-loop | 5 - Integration | Pending |
| 30 | pocoflow-fastapi-background | FastAPI + background flow | 5 - Integration | Pending |
| 31 | pocoflow-fastapi-hitl | FastAPI human-in-the-loop | 5 - Integration | Pending |
| 32 | pocoflow-fastapi-websocket | FastAPI + WebSocket | 5 - Integration | Pending |
| 33 | pocoflow-gradio-hitl | Gradio human-in-the-loop | 5 - Integration | Pending |
| 34 | pocoflow-streamlit-fsm | Streamlit finite state machine | 5 - Integration | Pending |
| 35 | pocoflow-visualization | Flow visualization | 5 - Integration | Done |
| 36 | pocoflow-tracing | Execution tracing | 5 - Integration | Done |
| 37 | pocoflow-mcp | Model Context Protocol | 6 - Advanced | Pending |
| 38 | pocoflow-a2a | Agent-to-agent | 6 - Advanced | Pending |
| 39 | pocoflow-multi-agent | Multi-agent orchestration | 6 - Advanced | Pending |
| 40 | pocoflow-tool-crawler | Web crawler tool | 6 - Advanced | Done |
| 41 | pocoflow-tool-database | Database tool | 6 - Advanced | Pending |
| 42 | pocoflow-tool-embeddings | Embeddings tool | 6 - Advanced | Done |
| 43 | pocoflow-tool-pdf-vision | PDF + vision tool | 6 - Advanced | Done |
| 44 | pocoflow-tool-search | Search tool | 6 - Advanced | Done |
| 45 | pocoflow-google-calendar | Google Calendar integration | 6 - Advanced | Done |
| 46 | pocoflow-voice-chat | Voice chat | 6 - Advanced | Done |
