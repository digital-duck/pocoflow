"""PocoFlow FastAPI Background — article generator with SSE progress."""

import asyncio
import json
import os
import uuid

import click
import yaml
from fastapi import FastAPI, BackgroundTasks, Form
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from pocoflow import Node, Flow, Store
from pocoflow.utils import UniversalLLMProvider

# --- Global LLM config (set at startup via CLI) ---
_llm = None
_model = None

app = FastAPI()

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

active_jobs: dict = {}


# ─── Nodes ────────────────────────────────────────────────────────────
class GenerateOutlineNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return store["topic"], store["_llm"], store.get("_model")

    def exec(self, prep_result):
        topic, llm, model = prep_result
        prompt = f"""Create a simple outline for an article about {topic}.
Include at most 3 main sections (no subsections).

Output the sections in YAML format:
```yaml
sections:
    - First section title
    - Second section title
    - Third section title
```"""
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        yaml_str = response.content.split("```yaml")[1].split("```")[0].strip()
        return yaml.safe_load(yaml_str)

    def post(self, store, prep_result, exec_result):
        sections = exec_result["sections"]
        store["sections"] = sections
        queue = store.get("_sse_queue")
        if queue:
            queue.put_nowait({"step": "outline", "progress": 33, "data": {"sections": sections}})
        return "write"


class WriteContentNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return store["sections"], store["_llm"], store.get("_model"), store.get("_sse_queue")

    def exec(self, prep_result):
        sections, llm, model, queue = prep_result
        parts = []
        for i, section in enumerate(sections):
            prompt = f"""Write a short paragraph (MAX 100 words) about: {section}
Use simple language, include one brief example or analogy."""
            response = llm.call(prompt, model=model)
            if not response.success:
                raise RuntimeError(f"LLM failed: {response.error_history}")
            parts.append(f"## {section}\n\n{response.content}\n")
            if queue:
                progress = 33 + ((i + 1) * 33 // len(sections))
                queue.put_nowait({
                    "step": "content",
                    "progress": progress,
                    "data": {"section": section, "completed": i + 1, "total": len(sections)},
                })
        return "\n".join(parts)

    def post(self, store, prep_result, exec_result):
        store["draft"] = exec_result
        return "style"


class ApplyStyleNode(Node):
    max_retries = 3
    retry_delay = 2.0

    def prep(self, store):
        return store["draft"], store["_llm"], store.get("_model")

    def exec(self, prep_result):
        draft, llm, model = prep_result
        prompt = f"""Rewrite this draft in a conversational, engaging style:

{draft}

Make it warm, with rhetorical questions, analogies, and a strong opening/conclusion."""
        response = llm.call(prompt, model=model)
        if not response.success:
            raise RuntimeError(f"LLM failed: {response.error_history}")
        return response.content

    def post(self, store, prep_result, exec_result):
        store["final_article"] = exec_result
        queue = store.get("_sse_queue")
        if queue:
            queue.put_nowait({"step": "complete", "progress": 100, "data": {"final_article": exec_result}})
        return "done"


# ─── Background runner ────────────────────────────────────────────────
def run_article_workflow(job_id: str, topic: str):
    try:
        sse_queue = active_jobs[job_id]
        outline = GenerateOutlineNode()
        write = WriteContentNode()
        style = ApplyStyleNode()
        outline.then("write", write)
        write.then("style", style)

        store = Store(
            data={
                "topic": topic,
                "_llm": _llm,
                "_model": _model,
                "_sse_queue": sse_queue,
                "sections": [],
                "draft": "",
                "final_article": "",
            },
            name="article",
        )
        flow = Flow(start=outline)
        flow.run(store)
    except Exception as e:
        if job_id in active_jobs:
            active_jobs[job_id].put_nowait({"step": "error", "progress": 0, "data": {"error": str(e)}})


# ─── Routes ───────────────────────────────────────────────────────────
@app.post("/start-job")
async def start_job(background_tasks: BackgroundTasks, topic: str = Form(...)):
    job_id = str(uuid.uuid4())
    sse_queue = asyncio.Queue()
    active_jobs[job_id] = sse_queue
    background_tasks.add_task(run_article_workflow, job_id, topic)
    return {"job_id": job_id, "topic": topic, "status": "started"}


@app.get("/progress/{job_id}")
async def get_progress(job_id: str):
    async def event_stream():
        if job_id not in active_jobs:
            yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
            return
        sse_queue = active_jobs[job_id]
        yield f"data: {json.dumps({'step': 'connected', 'progress': 0})}\n\n"
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(sse_queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(msg)}\n\n"
                    if msg.get("step") == "complete":
                        del active_jobs[job_id]
                        break
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'heartbeat': True})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


@app.get("/")
async def index():
    static_index = os.path.join(static_dir, "index.html")
    if os.path.exists(static_index):
        return FileResponse(static_index)
    return {"message": "PocoFlow FastAPI Background — POST /start-job with topic field"}


# ─── CLI entrypoint ──────────────────────────────────────────────────
@click.command()
@click.option("--provider", default="anthropic", help="LLM provider (openai, anthropic, gemini, openrouter, ollama)")
@click.option("--model", default=None, help="Model name (provider default if omitted)")
@click.option("--host", default="0.0.0.0", help="Server host")
@click.option("--port", default=8000, help="Server port")
def main(provider, model, host, port):
    """Start FastAPI server with background article generation."""
    global _llm, _model
    _llm = UniversalLLMProvider(primary_provider=provider, fallback_providers=[])
    _model = model

    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
