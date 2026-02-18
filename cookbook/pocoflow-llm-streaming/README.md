# PocoFlow LLM Streaming

Real-time LLM response streaming with user interrupt capability.

## What It Shows

- **Streaming output**: displays LLM tokens as they arrive
- **User interrupt**: press ENTER to stop generation mid-stream
- **Threading**: background listener for interrupt signal

## Run It

```bash
pip install -r requirements.txt

# OpenAI (default)
export OPENAI_API_KEY="your-key"
python main.py "Explain quantum computing"

# Ollama (local)
python main.py --provider ollama --model llama3.2 "Tell me a story"

# See all options
python main.py --help
```

## How It Works

```mermaid
flowchart LR
    Stream[StreamNode] --> Done[End]
```

StreamNode:
1. Creates a background thread listening for ENTER key
2. Opens a streaming connection to the LLM
3. Prints each token as it arrives
4. Stops early if the user presses ENTER
