"""
Agentic StudyMate — Chat API Routes

Endpoints:
- POST /api/chat          → Main agentic chat (SSE streaming)
- GET  /api/chat/sessions → List chat sessions
- GET  /api/chat/sessions/{id} → Get message history
- DELETE /api/chat/sessions/{id} → Delete a session
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.db.init_db import DEFAULT_USER_ID
from app.models.db_models import ChatSession, Message, generate_uuid, utcnow
from app.models.schemas import (
    ChatRequest,
    ChatSessionResponse,
    ChatHistoryResponse,
    MessageResponse,
    Citation,
)
from app.core.agent.controller import run_agent_stream, generate_session_title


router = APIRouter(prefix="/api/chat", tags=["chat"])


# ─── POST /api/chat — Main Chat Endpoint (SSE Streaming) ─────────────────────


@router.post("")
async def chat(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Main agentic chat endpoint with Server-Sent Events streaming.

    Creates a new session if session_id is not provided.
    Saves user message to DB, runs the agentic pipeline,
    and streams the response as SSE events.
    """
    # Get or create session
    if request.session_id:
        session_id = request.session_id
        # Verify session exists
        result = await db.execute(
            select(ChatSession).where(ChatSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        # Create new session with LLM-generated title
        title = await generate_session_title(request.question)
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
        content=request.question,
        created_at=utcnow(),
    )
    db.add(user_message)
    await db.commit()

    # Stream the agentic pipeline
    async def event_stream():
        """Generate SSE event stream from the agentic pipeline."""
        full_answer = ""
        citations_list = []

        try:
            # Send session_id as first event (for new sessions)
            yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"

            async for event in run_agent_stream(
                question=request.question,
                document_ids=request.document_ids,
                db=db,
            ):
                yield event

                # Capture final answer and citations from done event
                if event.startswith("event: done"):
                    data_line = event.split("data: ", 1)[1].strip()
                    done_data = json.loads(data_line)
                    full_answer = done_data.get("answer", "")
                    citations_list = done_data.get("citations", [])

            # Save assistant message to DB
            # Parse citations from the done event
            parsed_citations = None
            if event.startswith("event: citations"):
                data_line = event.split("data: ", 1)[1].strip()
                parsed_citations = json.loads(data_line)

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
