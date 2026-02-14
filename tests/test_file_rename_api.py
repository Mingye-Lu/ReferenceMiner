# pyright: reportMissingTypeStubs=false

import json
import sys
import unittest
from pathlib import Path
from typing import cast, TypedDict
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from refminer.server import app
from refminer.server.file_rename import RenameFileResult


class InMemoryQueueStore:
    def __init__(self) -> None:
        self.created_jobs: list[dict[str, object]] = []
        self.updated_jobs: list[tuple[str, dict[str, object]]] = []

    def create_job(self, **kwargs: object) -> dict[str, str]:
        job = {"id": "job-1", **kwargs}
        self.created_jobs.append(job)
        return {"id": "job-1"}

    def update_job(self, job_id: str, **kwargs: object) -> None:
        self.updated_jobs.append((job_id, kwargs))


class SSEMessage(TypedDict):
    event: str
    data: dict[str, object]


def parse_sse_messages(response_text: str) -> list[SSEMessage]:
    messages: list[SSEMessage] = []
    blocks = [block for block in response_text.split("\n\n") if block.strip()]
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        event_line = next((line for line in lines if line.startswith("event:")), None)
        data_line = next((line for line in lines if line.startswith("data:")), None)
        if event_line is None or data_line is None:
            continue

        event = event_line.split(":", 1)[1].strip()
        payload_obj = cast(object, json.loads(data_line.split(":", 1)[1].strip()))
        if not isinstance(payload_obj, dict):
            continue
        payload_raw = cast(dict[object, object], payload_obj)
        payload: dict[str, object] = {}
        for key, value in payload_raw.items():
            payload[str(key)] = value
        messages.append({"event": event, "data": payload})
    return messages


class TestFileRenameApi(unittest.TestCase):
    def test_rename_stream_success_emits_ordered_events(self) -> None:
        queue_store = InMemoryQueueStore()
        old_rel_path = str(Path("nested") / "old_name.pdf")
        new_rel_path = str(Path("nested") / "new_name.pdf")

        with (
            patch("refminer.server.streaming.rename.queue_store", queue_store),
            patch(
                "refminer.server.streaming.rename.resolve_rel_path",
                return_value=old_rel_path,
            ),
            patch(
                "refminer.server.streaming.rename.rename_file_on_disk_and_reindex",
                return_value=RenameFileResult(
                    old_rel_path=old_rel_path,
                    new_rel_path=new_rel_path,
                    removed_chunks=7,
                ),
            ),
            TestClient(app) as client,
        ):
            response = client.post(
                f"/api/bank/files/{old_rel_path}/rename/stream",
                json={"new_name": "new_name.pdf"},
            )

        self.assertEqual(response.status_code, 200)
        messages = parse_sse_messages(response.text)
        self.assertEqual(
            [message["event"] for message in messages],
            ["start", "progress", "file", "complete"],
        )

        self.assertEqual(messages[0]["data"]["old_rel_path"], old_rel_path)
        self.assertEqual(messages[0]["data"]["new_name"], "new_name.pdf")
        self.assertEqual(messages[1]["data"]["percent"], 50)
        self.assertEqual(messages[2]["data"]["rel_path"], old_rel_path)

        complete_payload = messages[3]["data"]
        self.assertEqual(complete_payload["old_rel_path"], old_rel_path)
        self.assertEqual(complete_payload["new_rel_path"], new_rel_path)
        self.assertEqual(complete_payload["removed_chunks"], 7)

        self.assertEqual(queue_store.created_jobs[0]["rel_path"], old_rel_path)
        self.assertEqual(queue_store.updated_jobs[-1][1]["status"], "complete")

    def test_rename_stream_conflict_emits_error_event(self) -> None:
        queue_store = InMemoryQueueStore()
        old_rel_path = str(Path("nested") / "old_name.pdf")

        with (
            patch("refminer.server.streaming.rename.queue_store", queue_store),
            patch(
                "refminer.server.streaming.rename.resolve_rel_path",
                return_value=old_rel_path,
            ),
            patch(
                "refminer.server.streaming.rename.rename_file_on_disk_and_reindex",
                side_effect=HTTPException(
                    status_code=409,
                    detail="File already exists: nested/new_name.pdf",
                ),
            ),
            TestClient(app) as client,
        ):
            response = client.post(
                f"/api/bank/files/{old_rel_path}/rename/stream",
                json={"new_name": "new_name.pdf"},
            )

        self.assertEqual(response.status_code, 200)

        messages = parse_sse_messages(response.text)
        self.assertEqual(
            [message["event"] for message in messages],
            ["start", "progress", "file", "error"],
        )

        error_payload = messages[-1]["data"]
        self.assertEqual(error_payload["code"], "CONFLICT")
        self.assertIn("File already exists", str(error_payload["message"]))
        self.assertEqual(queue_store.updated_jobs[-1][1]["status"], "error")


if __name__ == "__main__":
    _ = unittest.main()
