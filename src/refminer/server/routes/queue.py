"""Queue job endpoints and SSE stream."""

from __future__ import annotations

import asyncio
import logging
import queue
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from refminer.server.globals import queue_events, queue_store
from refminer.server.models import QueueJobCreateRequest
from refminer.server.utils import sse

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/queue", tags=["queue"])


@router.get("/jobs")
def list_queue_jobs(
    scope: Optional[str] = None,
    project_id: Optional[str] = None,
    include_completed: bool = False,
    limit: int = 200,
):
    return queue_store.list_jobs(
        scope=scope,
        project_id=project_id,
        include_completed=include_completed,
        limit=limit,
    )


@router.get("/jobs/{job_id}")
def get_queue_job(job_id: str):
    job = queue_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs")
def create_queue_job(req: QueueJobCreateRequest):
    job = queue_store.create_job(
        job_type=req.type,
        scope=req.scope,
        project_id=req.project_id,
        name=req.name,
        rel_path=req.rel_path,
        status=req.status or "pending",
        phase=req.phase,
        progress=req.progress,
    )
    return job


@router.get("/stream")
async def stream_queue_jobs(
    scope: Optional[str] = None,
    project_id: Optional[str] = None,
):
    async def event_stream():
        q = queue_events.subscribe()
        logger.info(
            f"[QueueStream] new subscriber connected scope={scope} project_id={project_id}"
        )
        try:
            initial = queue_store.list_jobs(
                scope=scope,
                project_id=project_id,
                include_completed=True,
                limit=500,
            )
            for job in initial:
                job_id = job.get("id", "?")[:8]
                phase = job.get("phase", "none")
                status = job.get("status", "?")
                logger.info(
                    f"[QueueStream] initial job={job_id} status={status} phase={phase}"
                )
                yield sse("job", job)
            yield sse("ready", {"ok": True})

            while True:
                item = await asyncio.to_thread(q.get)
                payload = item.data
                job_id = payload.get("id", "?")[:8]
                phase = payload.get("phase", "none")
                status = payload.get("status", "?")

                if scope and payload.get("scope") != scope:
                    logger.debug(f"[QueueStream] skipping job={job_id} wrong scope")
                    continue
                if project_id and payload.get("project_id") != project_id:
                    logger.debug(f"[QueueStream] skipping job={job_id} wrong project")
                    continue

                logger.info(
                    f"[QueueStream] yielding event job={job_id} status={status} phase={phase}"
                )
                yield sse(item.event, payload)
        finally:
            logger.info("[QueueStream] subscriber disconnected")
            queue_events.unsubscribe(q)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
