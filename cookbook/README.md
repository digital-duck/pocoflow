# PocoFlow Cookbook

Ported from [PocketFlow cookbook](https://github.com/The-Pocket/PocketFlow/tree/main/cookbook), adapted for PocoFlow's API (`Store`, `.then()`, `AsyncNode`, etc.).

## Examples

### Core Patterns

| Example | What It Shows |
|---------|---------------|
| [pocoflow-node](pocoflow-node/) | Single node lifecycle: prep/exec/post |
| [pocoflow-flow](pocoflow-flow/) | Multi-node wiring, action routing |
| [pocoflow-batch](pocoflow-batch/) | Batch processing patterns |
| [pocoflow-batch-node](pocoflow-batch-node/) | Batch over nodes |
| [pocoflow-batch-flow](pocoflow-batch-flow/) | Batch over flows |
| [pocoflow-parallel-batch](pocoflow-parallel-batch/) | Parallel batch processing |
| [pocoflow-parallel-batch-flow](pocoflow-parallel-batch-flow/) | Parallel batch over flows |
| [pocoflow-nested-batch](pocoflow-nested-batch/) | Nested batch processing |
| [pocoflow-async-basic](pocoflow-async-basic/) | AsyncNode + exec_async() |
| [pocoflow-map-reduce](pocoflow-map-reduce/) | Map-reduce pattern |
| [pocoflow-workflow](pocoflow-workflow/) | Multi-step workflow |

### LLM Applications

| Example | What It Shows |
|---------|---------------|
| [pocoflow-hello-world](pocoflow-hello-world/) | Minimal single-node LLM flow |
| [pocoflow-chat](pocoflow-chat/) | Basic LLM node, self-loop, retry |
| [pocoflow-chat-memory](pocoflow-chat-memory/) | Chat + conversation persistence |
| [pocoflow-structured-output](pocoflow-structured-output/) | LLM + YAML parsing, retry on bad output |
| [pocoflow-thinking](pocoflow-thinking/) | Chain-of-thought reasoning with plan refinement |
| [pocoflow-code-generator](pocoflow-code-generator/) | Code generation pipeline |
| [pocoflow-text2sql](pocoflow-text2sql/) | Natural language to SQL with debug loop |
| [pocoflow-rag](pocoflow-rag/) | Retrieval-augmented generation |
| [pocoflow-llm-streaming](pocoflow-llm-streaming/) | LLM streaming responses |

### Agents & Multi-Agent

| Example | What It Shows |
|---------|---------------|
| [pocoflow-agent](pocoflow-agent/) | Tool-calling agent loop |
| [pocoflow-supervisor](pocoflow-supervisor/) | Multi-agent supervisor |

### Tool Integration

| Example | What It Shows |
|---------|---------------|
| [pocoflow-tool-search](pocoflow-tool-search/) | Web search + LLM analysis |
| [pocoflow-tool-crawler](pocoflow-tool-crawler/) | Web crawler with LLM page analysis |
| [pocoflow-tool-embeddings](pocoflow-tool-embeddings/) | OpenAI text embeddings |
| [pocoflow-tool-pdf-vision](pocoflow-tool-pdf-vision/) | PDF extraction via vision model |

### Integration & Advanced

| Example | What It Shows |
|---------|---------------|
| [pocoflow-google-calendar](pocoflow-google-calendar/) | Google Calendar API integration |
| [pocoflow-voice-chat](pocoflow-voice-chat/) | Voice chat with STT/TTS |
| [pocoflow-visualization](pocoflow-visualization/) | Flow graph visualization (Mermaid + D3.js) |
| [pocoflow-tracing](pocoflow-tracing/) | Execution tracing with Langfuse |
