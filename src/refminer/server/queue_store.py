"""Persistent queue job store with SSE event hub."""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)


QUEUE_JOBS_FILENAME = "queue_jobs.json"
MAX_QUEUE_JOBS = 500


@dataclass(frozen=True)
class QueueEvent:
    event: str
    data: dict[str, Any]


class QueueEventHub:
    """Thread-safe pub/sub hub for queue job events."""

    def __init__(self) -> None:
        self._subscribers: set[queue.Queue[QueueEvent]] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> queue.Queue[QueueEvent]:
        q: queue.Queue[QueueEvent] = queue.Queue()
        with self._lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: queue.Queue[QueueEvent]) -> None:
        with self._lock:
            self._subscribers.discard(q)

    def publish(self, event: str, data: dict[str, Any]) -> None:
        payload = QueueEvent(event=event, data=data)
        with self._lock:
            subscribers = list(self._subscribers)
        job_id = data.get("id", "?")[:8]
        phase = data.get("phase", "none")
        status = data.get("status", "?")
        logger.info(
            f"[QueueHub] publish job={job_id} status={status} phase={phase} subscribers={len(subscribers)}"
        )
        for q in subscribers:
            try:
                q.put_nowait(payload)
            except queue.Full:
                logger.warning(
                    f"[QueueHub] queue full, dropping event for job={job_id}"
                )
                continue


class QueueStore:
    """Persistent in-process queue job store."""

    def __init__(self, index_dir: Path, hub: QueueEventHub) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        self._path = index_dir / QUEUE_JOBS_FILENAME
        self._hub = hub
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._last_loaded_mtime_ns: Optional[int] = None
        self._load()
        self._clear_stale_jobs()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(raw, list):
            return
        for item in raw:
            if not isinstance(item, dict):
                continue
            job_id = item.get("id")
            if not job_id:
                continue
            self._jobs[str(job_id)] = item
        try:
            self._last_loaded_mtime_ns = self._path.stat().st_mtime_ns
        except Exception:
            self._last_loaded_mtime_ns = None

    def _clear_stale_jobs(self) -> None:
        """Clear jobs that were in progress when server stopped."""
        stale_statuses = {"pending", "uploading", "processing"}
        stale_ids = [
            job_id
            for job_id, job in self._jobs.items()
            if job.get("status") in stale_statuses
        ]
        if not stale_ids:
            return
        logger.info(
            f"[QueueStore] clearing {len(stale_ids)} stale jobs from previous session"
        )
        for job_id in stale_ids:
            del self._jobs[job_id]
        self._save()

    def _load_if_changed(self) -> None:
        try:
            mtime_ns = self._path.stat().st_mtime_ns
        except Exception:
            return
        if self._last_loaded_mtime_ns is None or mtime_ns > self._last_loaded_mtime_ns:
            self._jobs = {}
            self._load()

    def _save(self) -> None:
        items = list(self._jobs.values())
        tmp_path = self._path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(items, ensure_ascii=True), encoding="utf-8")
        tmp_path.replace(self._path)
        try:
            self._last_loaded_mtime_ns = self._path.stat().st_mtime_ns
        except Exception:
            self._last_loaded_mtime_ns = None

    def _emit(self, job: dict[str, Any]) -> None:
        # Copy to prevent race conditions - subsequent updates can modify the
        # original dict before the SSE consumer processes this event
        self._hub.publish("job", dict(job))

    def _trim(self) -> None:
        if len(self._jobs) <= MAX_QUEUE_JOBS:
            return
        ordered = sorted(
            self._jobs.values(),
            key=lambda item: item.get("updated_at", item.get("created_at", 0)),
            reverse=True,
        )
        keep = {item["id"] for item in ordered[:MAX_QUEUE_JOBS] if "id" in item}
        for job_id in list(self._jobs.keys()):
            if job_id not in keep:
                self._jobs.pop(job_id, None)

    def create_job(
        self,
        *,
        job_type: str,
        scope: str,
        project_id: Optional[str] = None,
        name: Optional[str] = None,
        rel_path: Optional[str] = None,
        status: str = "pending",
        phase: Optional[str] = None,
        progress: Optional[int] = None,
        error: Optional[str] = None,
        duplicate_path: Optional[str] = None,
    ) -> dict[str, Any]:
        now = time.time()
        now_ns = time.time_ns()
        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "type": job_type,
            "scope": scope,
            "project_id": project_id,
            "name": name,
            "rel_path": rel_path,
            "status": status,
            "phase": phase,
            "progress": progress,
            "error": error,
            "duplicate_path": duplicate_path,
            "created_at": now,
            "created_at_ns": now_ns,
            "updated_at": now,
            "updated_at_ns": now_ns,
        }
        with self._lock:
            self._jobs[job_id] = job
            self._trim()
            self._save()
        self._emit(job)
        return job

    def update_job(self, job_id: str, **updates: Any) -> Optional[dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return None
            for key, value in updates.items():
                if value is None:
                    if key in {
                        "phase",
                        "error",
                        "duplicate_path",
                        "rel_path",
                        "name",
                        "progress",
                    }:
                        job[key] = None
                    continue
                if key == "progress":
                    try:
                        value = int(value)
                    except Exception:
                        continue
                    value = max(0, min(100, value))
                job[key] = value
            job["updated_at"] = time.time()
            job["updated_at_ns"] = time.time_ns()
            self._jobs[job_id] = job
            self._trim()
            self._save()
        self._emit(job)
        return job

    def get_job(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            self._load_if_changed()
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list_jobs(
        self,
        *,
        scope: Optional[str] = None,
        project_id: Optional[str] = None,
        include_completed: bool = False,
        include_dismissed: bool = False,
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            self._load_if_changed()
            items = list(self._jobs.values())

        def include(item: dict[str, Any]) -> bool:
            if scope and item.get("scope") != scope:
                return False
            if project_id and item.get("project_id") != project_id:
                return False
            if not include_completed and item.get("status") in {
                "complete",
                "cancelled",
            }:
                return False
            if not include_dismissed and item.get("status") == "dismissed":
                return False
            return True

        filtered = [item for item in items if include(item)]
        filtered.sort(
            key=lambda item: item.get(
                "updated_at_ns", item.get("updated_at", item.get("created_at", 0))
            ),
            reverse=True,
        )
        if limit is not None:
            filtered = filtered[: max(0, int(limit))]
        return [dict(item) for item in filtered]

    def touch_jobs(self, jobs: Iterable[dict[str, Any]]) -> None:
        for job in jobs:
            self._emit(job)
