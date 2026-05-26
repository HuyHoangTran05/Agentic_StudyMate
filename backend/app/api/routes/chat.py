"""
Agentic StudyMate — Chat API Routes

Endpoints:
- POST /api/chat          → Main agentic chat (SSE streaming)
- GET  /api/chat/sessions → List chat sessions
- GET  /api/chat/sessions/{id} → Get message history
- DELETE /api/chat/sessions/{id} → Delete a session
"""

import asyncio
import base64
import binascii
import json
import logging
from pathlib import Path
from urllib.request import Request as UrlRequest, urlopen

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.db.init_db import DEFAULT_USER_ID
from app.config import get_settings
from app.models.db_models import ChatSession, Chunk, Document, Message, generate_uuid, utcnow
from app.models.schemas import (
    ChatSessionResponse,
    ChatHistoryResponse,
    MessageResponse,
    Citation,
)
from app.core.agent.controller import run_agent_stream, generate_session_title
from app.core.retrieval.hybrid import get_hybrid_retriever
from app.core.db.neo4j_client import get_neo4j_client
from app.api.routes.documents import (
    answer_image_question_with_context,
    generate_image_search_query,
    persist_uploaded_image,
)


router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


SUPPORTED_JSON_IMAGE_FIELDS = (
    "image_base64",
    "imageBase64",
    "image_data",
    "imageData",
    "image",
)


def _sse_event(event: str, data: str) -> str:
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {data}\n\n"


def _get_result_value(result, key: str, default=None):
    """Read a value from either a dict result or a retrieval dataclass."""
    if isinstance(result, dict):
        return result.get(key, default)
    return getattr(result, key, default)


def _decode_base64_image(value: str) -> tuple[bytes, str]:
    """Decode a JSON image payload that may be a data URL or raw base64."""
    raw = value.strip()
    mime_type = "image/jpeg"
    if raw.startswith("data:"):
        header, _, payload = raw.partition(",")
        if not payload:
            raise ValueError("Invalid image data URL")
        mime_type = header.removeprefix("data:").split(";", 1)[0] or mime_type
        raw = payload

    return base64.b64decode(raw, validate=True), mime_type


async def _load_image_from_url(image_url: str) -> tuple[bytes, str]:
    """Load image bytes from a local /static URL, filesystem path, data URL, or HTTP URL."""
    if image_url.startswith("data:"):
        return _decode_base64_image(image_url)

    if image_url.startswith(("http://", "https://")):
        def _fetch():
            request = UrlRequest(image_url, headers={"User-Agent": "AgenticStudyMate/1.0"})
            with urlopen(request, timeout=10) as response:
                content_type = response.headers.get("content-type", "image/jpeg").split(";", 1)[0]
                return response.read(), content_type

        return await asyncio.to_thread(_fetch)

    path = Path(image_url.lstrip("/")) if image_url.startswith("/") else Path(image_url)
    if not path.exists() or not path.is_file():
        raise ValueError(f"Image URL is not accessible from the backend: {image_url}")

    suffix_to_mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    return path.read_bytes(), suffix_to_mime.get(path.suffix.lower(), "image/jpeg")


async def _extract_json_image(body: dict) -> tuple[bytes | None, str | None, str | None]:
    """Detect and load image data supplied in a JSON chat request."""
    image_url = body.get("image_url") or body.get("imageUrl")
    if image_url:
        image_bytes, mime_type = await _load_image_from_url(str(image_url))
        return image_bytes, mime_type, str(image_url)

    for field in SUPPORTED_JSON_IMAGE_FIELDS:
        value = body.get(field)
        if not value:
            continue
        try:
            image_bytes, mime_type = _decode_base64_image(str(value))
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid base64 image payload: {exc}") from exc

        _, stored_url = persist_uploaded_image(image_bytes=image_bytes, mime_type=mime_type)
        return image_bytes, mime_type, stored_url

    return None, None, None


async def _get_file_names_for_results(
    db: AsyncSession,
    results: list[dict],
) -> dict[str, str]:
    """Return document_id -> file_name for retrieved vector results."""
    document_ids = sorted({
        _get_result_value(result, "document_id")
        for result in results
        if _get_result_value(result, "document_id")
    })
    if not document_ids:
        return {}

    rows = await db.execute(
        select(Document.id, Document.file_name).where(Document.id.in_(document_ids))
    )
    return {document_id: file_name for document_id, file_name in rows.all()}


def _format_retrieved_context(
    results: list[dict],
    file_names: dict[str, str],
) -> str:
    """Format Qdrant vector hits for the multimodal synthesis prompt."""
    if not results:
        return "No relevant knowledge-base chunks were retrieved."

    passages = []
    for index, result in enumerate(results, 1):
        document_id = _get_result_value(result, "document_id")
        file_name = file_names.get(document_id, "unknown")
        page_number = _get_result_value(result, "page_number")
        section_title = _get_result_value(result, "section_title")
        image_url = _get_result_value(result, "image_url")

        meta_parts = [f"File: {file_name}"]
        if page_number is not None:
            meta_parts.append(f"Page: {page_number}")
        if section_title:
            meta_parts.append(f"Section: {section_title}")
        if image_url:
            meta_parts.append(f"Image URL: {image_url}")

        passages.append(
            f"--- Context {index} [{' | '.join(meta_parts)}] ---\n"
            f"{_get_result_value(result, 'content') or ''}"
        )

    return "\n\n".join(passages)


def _build_citations_from_results(
    results: list[dict],
    file_names: dict[str, str],
) -> list[Citation]:
    """Expose retrieved chunks as citations for the frontend."""
    citations = []
    for result in results:
        chunk_id = _get_result_value(result, "chunk_id")
        if not chunk_id:
            continue

        content = _get_result_value(result, "content") or ""
        citations.append(
            Citation(
                file_name=file_names.get(_get_result_value(result, "document_id"), "unknown"),
                page_number=_get_result_value(result, "page_number"),
                chunk_id=str(chunk_id),
                section_title=_get_result_value(result, "section_title"),
                snippet=content[:240] if content else None,
                image_url=_get_result_value(result, "image_url"),
            )
        )
    return citations


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    """Keep one citation per chunk_id while preserving order."""
    seen = set()
    deduped = []
    for citation in citations:
        if citation.chunk_id in seen:
            continue
        seen.add(citation.chunk_id)
        deduped.append(citation)
    return deduped


async def _retrieve_graph_context(
    query: str,
    document_ids: list[str] | None,
    db: AsyncSession,
    limit: int = 20,
) -> tuple[str, list[Citation], int]:
    """Retrieve Neo4j triplets plus source chunk citations for a query."""
    try:
        graph_hits = await get_neo4j_client().search_triplets(query, limit=limit)
    except Exception as exc:
        logger.warning("Graph retrieval skipped: %s", exc)
        return "No graph relationships were retrieved.", [], 0

    if not graph_hits:
        return "No graph relationships were retrieved.", [], 0

    chunk_ids = [
        hit.get("chunk_id")
        for hit in graph_hits
        if hit.get("chunk_id")
    ]

    chunks_by_id: dict[str, Chunk] = {}
    file_names: dict[str, str] = {}
    if chunk_ids:
        stmt = (
            select(Chunk, Document.file_name)
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.id.in_(chunk_ids))
        )
        if document_ids:
            stmt = stmt.where(Chunk.document_id.in_(document_ids))

        rows = await db.execute(stmt)
        for chunk, file_name in rows.all():
            chunks_by_id[chunk.id] = chunk
            file_names[chunk.document_id] = file_name

    lines = []
    citations = []
    for index, hit in enumerate(graph_hits, 1):
        chunk_id = hit.get("chunk_id")
        chunk = chunks_by_id.get(chunk_id)
        if document_ids and chunk is None:
            continue

        source = hit.get("source") or "Unknown"
        relation = hit.get("relation") or "RELATED_TO"
        target = hit.get("target") or "Unknown"
        source_ref = f"chunk_id={chunk_id}" if chunk_id else "chunk_id=unknown"
        if chunk:
            source_ref += f", file={file_names.get(chunk.document_id, 'unknown')}"

        lines.append(f"{index}. ({source}) -[{relation}]-> ({target}) [{source_ref}]")

        if chunk:
            citations.append(
                Citation(
                    file_name=file_names.get(chunk.document_id, "unknown"),
                    page_number=chunk.page_number,
                    chunk_id=chunk.id,
                    section_title=chunk.section_title,
                    snippet=chunk.content[:240] if chunk.content else None,
                    image_url=chunk.image_url,
                )
            )

    if not lines:
        return "No graph relationships were retrieved.", [], 0

    return "\n".join(lines), _dedupe_citations(citations), len(lines)


async def _retrieve_multimodal_context(
    query: str,
    document_ids: list[str] | None,
    db: AsyncSession,
) -> tuple[str, list[Citation], int, int]:
    """Retrieve vector/BM25 passages and Neo4j graph context for vision RAG."""
    settings = get_settings()
    retrieved_docs = await get_hybrid_retriever().search(
        query=query,
        document_ids=document_ids,
        top_k=settings.RETRIEVAL_TOP_K,
    )

    file_names = await _get_file_names_for_results(db, retrieved_docs)
    passage_context = _format_retrieved_context(retrieved_docs, file_names)
    passage_citations = _build_citations_from_results(retrieved_docs, file_names)

    graph_context, graph_citations, graph_count = await _retrieve_graph_context(
        query=query,
        document_ids=document_ids,
        db=db,
        limit=settings.RETRIEVAL_TOP_K,
    )

    combined_context = (
        "=== VECTOR/BM25 RETRIEVED PASSAGES ===\n"
        f"{passage_context}\n\n"
        "=== NEO4J GRAPH RELATIONSHIPS ===\n"
        f"{graph_context}"
    )
    citations = _dedupe_citations([*passage_citations, *graph_citations])
    return combined_context, citations, len(retrieved_docs), graph_count


# ─── POST /api/chat — Main Chat Endpoint (SSE Streaming) ─────────────────────


@router.post("")
async def chat(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Main agentic chat endpoint with Server-Sent Events streaming.

    Creates a new session if session_id is not provided.
    Saves user message to DB, runs the agentic pipeline,
    and streams the response as SSE events.
    """
    content_type = request.headers.get("content-type", "")
    uploaded_image_url = None
    image_bytes = None
    image_mime_type = None
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        question = str(form.get("question") or "").strip()
        session_id_from_request = str(form.get("session_id") or "") or None
        document_ids_raw = str(form.get("document_ids") or "")
        document_ids = json.loads(document_ids_raw) if document_ids_raw else None
        image_file = form.get("image")
        if isinstance(image_file, UploadFile):
            image_bytes = await image_file.read()
            image_mime_type = image_file.content_type or ""
            _, uploaded_image_url = persist_uploaded_image(
                image_bytes=image_bytes,
                mime_type=image_mime_type,
            )
    else:
        body = await request.json()
        question = str(body.get("question") or "").strip()
        session_id_from_request = body.get("session_id")
        document_ids = body.get("document_ids")
        image_bytes, image_mime_type, uploaded_image_url = await _extract_json_image(body)

    if not question:
        raise HTTPException(status_code=400, detail="Question is required")

    # Get or create session
    if session_id_from_request:
        session_id = session_id_from_request
        # Verify session exists
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        # Create new session with LLM-generated title
        title = await generate_session_title(question)
        session_id = generate_uuid()
        session = ChatSession(
            id=session_id,
            user_id=DEFAULT_USER_ID,
            title=title,
            created_at=utcnow(),
        )
        db.add(session)
        await db.commit()

    # Save user message
    user_message = Message(
        id=generate_uuid(),
        session_id=session_id,
        role="user",
        content=question,
        image_url=uploaded_image_url,
        created_at=utcnow(),
    )
    db.add(user_message)
    await db.commit()

    # Stream the agentic pipeline
    async def event_stream():
        """Generate SSE event stream from the agentic pipeline."""
        full_answer = ""
        parsed_citations = None

        try:
            # Send session_id as first event (for new sessions)
            yield (
                "event: session\n"
                f"data: {json.dumps({'session_id': session_id, 'image_url': uploaded_image_url})}\n\n"
            )

            if image_bytes is not None and image_mime_type is not None:
                yield _sse_event(
                    "status",
                    "Reading image and extracting retrieval keywords...",
                )
                try:
                    image_search_query = await generate_image_search_query(
                        image_bytes=image_bytes,
                        mime_type=image_mime_type,
                        question=question,
                    )
                except Exception as exc:
                    logger.warning("Vision keyword extraction failed; falling back to user prompt: %s", exc)
                    image_search_query = question

                image_search_query = (image_search_query or "").strip()
                if not image_search_query:
                    image_search_query = question
                logger.info(f"Generated Search Query: {image_search_query}")

                yield _sse_event("status", "Searching vector and graph context with image keywords...")
                retrieved_context, citations, passage_count, graph_count = await _retrieve_multimodal_context(
                    query=image_search_query,
                    document_ids=document_ids,
                    db=db,
                )
                parsed_citations = [citation.model_dump() for citation in citations]

                yield _sse_event(
                    "status",
                    (
                        f"Found {passage_count} passages and {graph_count} graph "
                        "relationships; synthesizing with image..."
                    ),
                )
                full_answer = await answer_image_question_with_context(
                    image_bytes=image_bytes,
                    mime_type=image_mime_type,
                    question=question,
                    context=retrieved_context,
                )

                yield _sse_event("chunk", full_answer)
                yield _sse_event(
                    "citations",
                    json.dumps(parsed_citations, default=str),
                )
                done_data = json.dumps({
                    "question_type": "image_rag",
                    "sub_questions": [image_search_query],
                    "sources_searched": passage_count + graph_count,
                    "citations_removed": 0,
                    "answer": full_answer,
                })
                yield _sse_event("done", done_data)
            else:
                async for event in run_agent_stream(
                    question=question,
                    document_ids=document_ids,
                    db=db,
                ):
                    yield event

                    if event.startswith("event: citations"):
                        data_line = event.split("data: ", 1)[1].strip()
                        parsed_citations = json.loads(data_line)

                    if event.startswith("event: done"):
                        data_line = event.split("data: ", 1)[1].strip()
                        done_data = json.loads(data_line)
                        full_answer = done_data.get("answer", "")

            # Save assistant message to DB
            assistant_message = Message(
                id=generate_uuid(),
                session_id=session_id,
                role="assistant",
                content=full_answer,
                citations=parsed_citations,
                created_at=utcnow(),
            )
            db.add(assistant_message)
            await db.commit()

        except Exception as e:
            print(f"⚠ Chat pipeline error: {e}")
            friendly_msg = (
                "I'm sorry, I'm unable to process your request right now. "
                "The AI service may be temporarily unavailable. "
                "Please try again in a moment."
            )
            yield f"event: error\ndata: {json.dumps({'error': friendly_msg})}\n\n"

            # Save friendly error as assistant message
            error_message = Message(
                id=generate_uuid(),
                session_id=session_id,
                role="assistant",
                content=friendly_msg,
                image_url=None,
                created_at=utcnow(),
            )
            db.add(error_message)
            await db.commit()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ─── GET /api/chat/sessions — List Sessions ──────────────────────────────────


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
):
    """List all chat sessions for the default user, newest first."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == DEFAULT_USER_ID)
        .order_by(ChatSession.created_at.desc())
    )
    sessions = result.scalars().all()
    return sessions


# ─── GET /api/chat/sessions/{id} — Get Message History ───────────────────────


@router.get("/sessions/{session_id}", response_model=ChatHistoryResponse)
async def get_session_history(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get full message history for a chat session."""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .options(selectinload(ChatSession.messages))
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    # Sort messages by created_at
    messages = sorted(session.messages, key=lambda m: m.created_at)

    return ChatHistoryResponse(
        session_id=session_id,
        messages=[
            MessageResponse(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                image_url=msg.image_url,
                citations=[
                    Citation(**c) for c in (msg.citations or [])
                ] if msg.citations else None,
                created_at=msg.created_at,
            )
            for msg in messages
        ],
    )


# ─── DELETE /api/chat/sessions/{id} — Delete Session ─────────────────────────


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a chat session and all its messages."""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")

    await db.delete(session)
    await db.commit()

    return {"status": "deleted", "session_id": session_id}
