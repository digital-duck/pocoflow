# PocoFlow FastAPI WebSocket

Chat interface using WebSocket for real-time communication.

## Usage

```bash
python main.py --provider anthropic
python main.py --provider ollama --model llama3.2 --port 8080
```

Connect to `ws://localhost:8000/ws` and send JSON messages: `{"content": "Hello!"}`.

## How it works

1. Client connects via WebSocket
2. Each message triggers a `StreamingChatNode` that calls the LLM
3. Conversation history is maintained per connection
4. Response is sent back over the WebSocket
