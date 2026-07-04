"""SSE stage-event streams."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.deps import get_repository
from app.pipeline.events import bus
from app.pipeline.stage_runner import stream_stage

router = APIRouter()


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    """Full-run event replay (used by the batch runner / legacy view)."""
    async def gen():
        ch = bus.channel(run_id)
        index = 0
        while True:
            new, index, done = await asyncio.to_thread(ch.read_from, index, 1.0)
            for ev in new:
                yield f"data: {json.dumps(ev)}\n\n"
            if done and index >= len(ch.events):
                break
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/runs/{run_id}/stages/{stage}/stream")
def stream_stage_endpoint(run_id: str, stage: str):
    """Lazy per-stage stream: computes the stage on connect and emits it bit by bit.

    Sync generator → Starlette iterates it in a threadpool, so the pacing
    sleeps in the runner don't block the event loop.
    """
    repo = get_repository()
    run = repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    company_id = run.company_id

    def gen():
        try:
            for ev in stream_stage(repo, run_id, company_id, stage):
                yield f"data: {json.dumps(ev)}\n\n"
        except Exception as e:  # pragma: no cover
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        yield "event: end\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
