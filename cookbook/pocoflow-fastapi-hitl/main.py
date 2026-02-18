"""PocoFlow FastAPI HITL — human-in-the-loop review via web UI."""

import asyncio
import json
import threading
import uuid

import click
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider

_llm = None
_model = None

app = FastAPI()
tasks: dict = {}


# ─── Nodes ────────────────────────────────────────────────────────────
class ProcessNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return store.get("task_input", ""), store["_llm"], store.get("_model")

    def exec(self, prep_result):
        text, llm, model = prep_result
        prompt = f"Improve and polish the following text. Return only the improved version:\n\n{text}"
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        return response.content

    def post(self, store, prep_result, exec_result):
        store["processed_output"] = exec_result
        queue = store.get("_sse_queue")
        if queue:
            queue.put_nowait({"status": "waiting_for_review", "output": exec_result})
        return "review"


class ReviewNode(Node):
    def prep(self, store):
        return store.get("_review_event"), store.get("_task_info")

    def exec(self, prep_result):
        review_event, task_info = prep_result
        if review_event:
            review_event.wait()  # blocks until feedback arrives
        return task_info.get("feedback_value", "rejected") if task_info else "rejected"

    def post(self, store, prep_result, exec_result):
        event = store.get("_review_event")
        if event:
            event.clear()

        if exec_result == "approved":
            store["final_result"] = store.get("processed_output")
            return "approved"
        return "rejected"


class ResultNode(Node):
    def prep(self, store):
        return store.get("final_result", "No result.")

    def exec(self, prep_result):
        return prep_result

    def post(self, store, prep_result, exec_result):
        queue = store.get("_sse_queue")
        if queue:
            queue.put_nowait({"status": "completed", "final_result": exec_result})
            queue.put_nowait(None)  # sentinel
        return "done"


# ─── Background runner ────────────────────────────────────────────────
def run_hitl_flow(task_id: str, text: str):
    try:
        task_info = tasks[task_id]
        review_event = threading.Event()
        sse_queue = asyncio.Queue()

        task_info["review_event"] = review_event
        task_info["sse_queue"] = sse_queue

        process = ProcessNode()
        review = ReviewNode()
        result = ResultNode()

        process.then("review", review)
        review.then("approved", result)
        review.then("rejected", process)

        store = Store(
            data={
                "task_input": text,
                "_llm": _llm,
                "_model": _model,
                "_review_event": review_event,
                "_task_info": task_info,
                "_sse_queue": sse_queue,
            },
            name="hitl",
        )

        flow = Flow(start=process)
        flow.run(store)
    except Exception as e:
        if task_id in tasks and "sse_queue" in tasks[task_id]:
            tasks[task_id]["sse_queue"].put_nowait({"status": "failed", "error": str(e)})
            tasks[task_id]["sse_queue"].put_nowait(None)


# ─── Routes ───────────────────────────────────────────────────────────
class SubmitRequest(BaseModel):
    data: str


class FeedbackRequest(BaseModel):
    feedback: str  # "approved" or "rejected"


@app.post("/submit")
async def submit_task(req: SubmitRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "pending"}
    background_tasks.add_task(run_hitl_flow, task_id, req.data)
    return {"task_id": task_id, "status": "submitted"}


@app.post("/feedback/{task_id}")
async def provide_feedback(task_id: str, req: FeedbackRequest):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    task_info = tasks[task_id]
    review_event = task_info.get("review_event")
    if not review_event:
        raise HTTPException(status_code=400, detail="Task not ready for feedback")

    task_info["feedback_value"] = req.feedback
    review_event.set()
    return {"message": f"Feedback '{req.feedback}' received"}


@app.get("/stream/{task_id}")
async def stream_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        # Wait for sse_queue to be created
        for _ in range(50):
            if "sse_queue" in tasks.get(task_id, {}):
                break
            await asyncio.sleep(0.1)

        queue = tasks.get(task_id, {}).get("sse_queue")
        if not queue:
            yield f"data: {json.dumps({'error': 'Queue not ready'})}\n\n"
            return

        try:
            while True:
                msg = await queue.get()
                if msg is None:
                    yield f"data: {json.dumps({'status': 'stream_closed'})}\n\n"
                    break
                yield f"data: {json.dumps(msg)}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})


@app.get("/")
async def index():
    return {"message": "PocoFlow FastAPI HITL — POST /submit, GET /stream/{id}, POST /feedback/{id}"}


@click.command()
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
@click.option("--host", default="0.0.0.0", help="Server host")
@click.option("--port", default=8000, help="Server port")
def main(provider, model, host, port):
    """Start FastAPI server with human-in-the-loop review workflow."""
    global _llm, _model
    _llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])
    _model = model

    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
