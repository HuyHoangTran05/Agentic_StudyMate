"""
Agentic StudyMate — Chat API Routes

Endpoints:
- POST /api/chat          → Main agentic chat (SSE streaming)
- GET  /api/chat/sessions → List chat sessions
- GET  /api/chat/sessions/{id} → Get message history
- DELETE /api/chat/sessions/{id} → Delete a session
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from starlette.datastructures import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.db.init_db import DEFAULT_USER_ID
from app.config import get_settings
from app.models.db_models import ChatSession, Document, Message, generate_uuid, utcnow
from app.models.schemas import (
    ChatSessionResponse,
    ChatHistoryResponse,
    MessageResponse,
    Citation,
)
from app.core.agent.controller import run_agent_stream, generate_session_title
from app.core.ingest.embedder import get_embedder
from app.core.retrieval.vector_store import get_vector_store
from app.api.routes.documents import (
    answer_image_question_with_context,
    generate_image_search_query,
    persist_uploaded_image,
)


router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


def _sse_event(event: str, data: str) -> str:
    """Format one Server-Sent Event."""
    return f"event: {event}\ndata: {data}\n\n"


async def _get_file_names_for_results(
    db: AsyncSession,
    results: list[dict],
) -> dict[str, str]:
    """Return document_id -> file_name for retrieved vector results."""
    document_ids = sorted({
        result["document_id"]
        for result in results
        if result.get("document_id")
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
        document_id = result.get("document_id")
        file_name = file_names.get(document_id, "unknown")
        page_number = result.get("page_number")
        section_title = result.get("section_title")
        image_url = result.get("image_url")

        meta_parts = [f"File: {file_name}"]
        if page_number is not None:
            meta_parts.append(f"Page: {page_number}")
        if section_title:
            meta_parts.append(f"Section: {section_title}")
        if image_url:
            meta_parts.append(f"Image URL: {image_url}")

        passages.append(
            f"--- Context {index} [{' | '.join(meta_parts)}] ---\n"
            f"{result.get('content') or ''}"
        )

    return "\n\n".join(passages)


def _build_citations_from_results(
    results: list[dict],
    file_names: dict[str, str],
) -> list[Citation]:
    """Expose retrieved chunks as citations for the frontend."""
    citations = []
    for result in results:
        chunk_id = result.get("chunk_id")
        if not chunk_id:
            continue

        content = result.get("content") or ""
        citations.append(
            Citation(
                file_name=file_names.get(result.get("document_id"), "unknown"),
                page_number=result.get("page_number"),
                chunk_id=str(chunk_id),
                section_title=result.get("section_title"),
                snippet=content[:240] if content else None,
                image_url=result.get("image_url"),
            )
        )
    return citations


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
                settings = get_settings()

                yield _sse_event(
                    "status",
                    "Reading image and generating a retrieval query...",
                )
                image_search_query = await generate_image_search_query(
                    image_bytes=image_bytes,
                    mime_type=image_mime_type,
                )
                logger.info(f"Generated Search Query: {image_search_query}")

                yield _sse_event("status", "Searching your documents with the image query...")
                query_vector = await get_embedder().embed_query(image_search_query)
                retrieved_docs = await get_vector_store().search(
                    query_vector=query_vector,
                    document_ids=document_ids,
                    top_k=settings.RETRIEVAL_TOP_K,
                )
                logger.info(f"Retrieved {len(retrieved_docs)} chunks from Vector DB")

                file_names = await _get_file_names_for_results(db, retrieved_docs)
                retrieved_context = _format_retrieved_context(retrieved_docs, file_names)
                citations = _build_citations_from_results(retrieved_docs, file_names)
                parsed_citations = [citation.model_dump() for citation in citations]

                yield _sse_event(
                    "status",
                    f"Found {len(retrieved_docs)} relevant passages; synthesizing with image...",
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
                    "sources_searched": len(retrieved_docs),
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
