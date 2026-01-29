"""Q&A and summarization endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import AsyncIterator, Iterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from refminer.analyze.workflow import analyze
from refminer.llm.agent import run_agent
from refminer.llm.client import (
    blocks_to_markdown,
    parse_answer_text,
    format_evidence,
    ChatCompletionsClient,
    _load_config,
)
from refminer.server.globals import get_bank_paths
from refminer.server.models import AskRequest, SummarizeRequest
from refminer.server.utils import (
    sse,
    clean_response_text,
    filter_evidence_by_citations,
    resolve_response_citations,
)
from refminer.server.streaming.agent import stream_agent

router = APIRouter(prefix="/api/projects/{project_id}", tags=["ask"])


@router.post("/ask")
async def ask(project_id: str, req: AskRequest):
    """Non-streaming Q&A endpoint."""
    _, idx_dir = get_bank_paths()
    result = run_agent(
        req.question,
        context=req.context,
        use_notes=req.use_notes,
        notes=req.notes,
        history=req.history,
        index_dir=idx_dir,
    )

    if result.response_text:
        filtered_evidence = filter_evidence_by_citations(
            result.evidence, result.response_citations
        )
        evidence_payload = [asdict(item) for item in filtered_evidence]
    else:
        evidence_payload = [asdict(item) for item in result.evidence]
    analysis = result.analysis or analyze(req.question, result.evidence)

    if result.response_text:
        cleaned_response = clean_response_text(result.response_text)
        _lines, citations = format_evidence(result.evidence)
        answer_blocks = parse_answer_text(cleaned_response, citations)
        resolved_citations = resolve_response_citations(
            result.response_citations, citations
        )
        if resolved_citations:
            if all(not block.citations for block in answer_blocks):
                answer_blocks[0].citations = resolved_citations
            else:
                for block in answer_blocks:
                    if not block.citations:
                        block.citations = resolved_citations
        answer_payload = [
            {"heading": block.heading, "body": block.body, "citations": block.citations}
            for block in answer_blocks
        ]
        answer_markdown = blocks_to_markdown(answer_blocks)
    else:
        return {
            "error": "LLM_NOT_CONFIGURED",
            "message": "LLM not available. Please configure an LLM provider in Settings.",
        }

    return {
        "question": req.question,
        "scope": analysis.get("scope", []),
        "evidence": evidence_payload,
        "answer": answer_payload,
        "answer_markdown": answer_markdown,
        "crosscheck": analysis.get("crosscheck", ""),
    }


@router.post("/ask/stream")
async def ask_stream(project_id: str, req: AskRequest) -> StreamingResponse:
    """Streaming Q&A endpoint using SSE."""
    generator = stream_agent(
        project_id,
        req.question,
        context=req.context,
        use_notes=req.use_notes,
        notes=req.notes,
        history=req.history,
    )
    return StreamingResponse(generator, media_type="text/event-stream")


# --- Summarization ---


def _generate_title_fallback(messages: list[dict]) -> str:
    """Generate a fallback title from the first user message."""
    first_msg = next((m for m in messages if m.get("role") == "user"), None)
    if not first_msg:
        return "New Chat"
    content = first_msg.get("content", "")
    if len(content) > 30:
        return content[:30] + "..."
    return content


def _stream_summarize(messages: list[dict]) -> Iterator[str]:
    """Stream chat title generation."""
    config = _load_config()
    if not config:
        yield sse("title_done", {"title": _generate_title_fallback(messages)})
        return

    conversation = "\n".join(
        f"{m.get('role', 'user').upper()}: {m.get('content', '')[:200]}"
        for m in messages[:4]
    )

    prompt_messages = [
        {
            "role": "system",
            "content": "Generate a very short title (3-6 words) for this conversation. Reply with ONLY the title, no quotes or punctuation.",
        },
        {"role": "user", "content": conversation},
    ]

    try:
        client = ChatCompletionsClient(config)
        full_title = ""
        for delta in client.stream_chat(prompt_messages):
            for char in delta:
                full_title += char
                yield sse("title_delta", {"delta": char})
        title = full_title.strip().strip("\"'")
        if len(title) > 50:
            title = title[:50] + "..."
        yield sse("title_done", {"title": title or _generate_title_fallback(messages)})
    except Exception:
        yield sse("title_done", {"title": _generate_title_fallback(messages)})


@router.post("/summarize")
async def summarize(project_id: str, request: SummarizeRequest):
    """Generate a chat title via LLM streaming."""
    if not request.messages:

        async def empty_gen() -> AsyncIterator[str]:
            yield sse("title_done", {"title": "New Chat"})

        return StreamingResponse(empty_gen(), media_type="text/event-stream")

    return StreamingResponse(
        _stream_summarize(request.messages), media_type="text/event-stream"
    )
