"""PocoFlow FastAPI WebSocket — streaming chat over WebSocket."""

import json
import os

import click
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider

_llm = None
_model = None

app = FastAPI()

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


class StreamingChatNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        user_msg = store.get("user_message", "")
        history = store.get("conversation_history", [])
        history.append({"role": "user", "content": user_msg})
        return history, store["_llm"], store.get("_model"), store.get("_websocket")

    def exec(self, prep_result):
        messages, llm, model, ws = prep_result
        # Use non-streaming call (streaming requires provider-specific async)
        response = llm.call(messages=messages, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        return response.content, ws

    def post(self, store, prep_result, exec_result):
        content, ws = exec_result
        history = store.get("conversation_history", [])
        history.append({"role": "assistant", "content": content})
        store["conversation_history"] = history
        # ws message sending happens in the websocket handler
        store["_response"] = content
        return "done"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    store_data = {
        "conversation_history": [],
        "_llm": _llm,
        "_model": _model,
        "_websocket": websocket,
    }

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            store_data["user_message"] = message.get("content", "")
            store_data["_response"] = ""

            node = StreamingChatNode()
            store = Store(data=store_data, name="ws_chat")
            flow = Flow(start=node)
            flow.run(store)

            # Send the response back over websocket
            await websocket.send_text(json.dumps({
                "type": "message",
                "content": store_data.get("_response", ""),
            }))

    except WebSocketDisconnect:
        pass


@app.get("/")
async def index():
    static_index = os.path.join(static_dir, "index.html")
    if os.path.exists(static_index):
        return FileResponse(static_index)
    return {"message": "PocoFlow WebSocket Chat — connect to /ws"}


@click.command()
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
@click.option("--host", default="0.0.0.0", help="Server host")
@click.option("--port", default=8000, help="Server port")
def main(provider, model, host, port):
    """Start FastAPI WebSocket chat server."""
    global _llm, _model
    _llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])
    _model = model

    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
