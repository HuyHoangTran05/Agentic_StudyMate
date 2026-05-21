"""
Agentic StudyMate — Agent Controller

The main orchestrator implementing the full agentic loop:

    analyze → rewrite → plan (if needed) → retrieve+rerank
    → evaluate (retry loop) → generate → verify citations

Supports both sync (full response) and streaming (SSE events).
"""

import json
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.db_models import Chunk, Document
from app.core.retrieval.hybrid import get_hybrid_retriever, RetrievalResult
from app.core.reranker import get_reranker, RerankResult
from app.core.agent.query_analyzer import analyze_query, QueryAnalysis
from app.core.agent.query_rewriter import rewrite_query
from app.core.agent.query_planner import decompose_query
from app.core.agent.context_evaluator import evaluate_context
from app.core.agent.answer_generator import generate_answer, generate_answer_stream
from app.core.agent.citation_verifier import verify_citations, VerifiedAnswer
from app.core.agent.llm_client import get_llm_client
from app.models.schemas import ChatResponse, Citation


async def _get_file_names(
    db: AsyncSession, document_ids: list[str] | None
) -> dict[str, str]:
    """Build a mapping of document_id → file_name for citation enrichment."""
    if document_ids:
        result = await db.execute(
            select(Document.id, Document.file_name).where(
                Document.id.in_(document_ids)
            )
        )
    else:
        result = await db.execute(select(Document.id, Document.file_name))

    return {row[0]: row[1] for row in result.all()}


def _attach_file_names(
    chunks: list[RerankResult], file_names: dict[str, str]
) -> list[RerankResult]:
    """Attach file_name to each chunk for citation purposes."""
    for chunk in chunks:
        chunk._file_name = file_names.get(chunk.document_id, "unknown")
    return chunks


def _deduplicate_chunks(chunks: list[RerankResult]) -> list[RerankResult]:
    """Deduplicate chunks by chunk_id, keeping highest-scored version."""
    seen: dict[str, RerankResult] = {}
    for chunk in chunks:
        if chunk.chunk_id not in seen:
            seen[chunk.chunk_id] = chunk
        elif chunk.rerank_score > seen[chunk.chunk_id].rerank_score:
            seen[chunk.chunk_id] = chunk
    return list(seen.values())


async def generate_session_title(question: str) -> str:
    """Generate a concise session title from the first question using LLM."""
    client = get_llm_client()
    try:
        result = await client.call_llm(
            prompt=f"Generate a very short title (max 6 words) for a chat session that starts with this question:\n\n{question}",
            system_prompt=(
                "You generate ultra-short chat session titles. "
                "Respond with ONLY the title text — no quotes, no punctuation at the end, no prefix. "
                "Examples: 'Photosynthesis Overview', 'DNA Replication Steps', 'Comparing Cell Types'"
            ),
        )
        title = result.strip().strip('"').strip("'").strip(".")
        return title[:80] if title else question[:50]
    except Exception:
        return question[:50]


# ─── Sync Pipeline ────────────────────────────────────────────────────────────


async def run_agent(
    question: str,
    document_ids: list[str] | None,
    db: AsyncSession,
) -> ChatResponse:
    """
    Run the full agentic pipeline (synchronous / non-streaming).

    Args:
        question: User's question
        document_ids: Optional filter to specific documents
        db: Database session for fetching file names

    Returns:
        ChatResponse with answer, citations, and metadata
    """
    settings = get_settings()
    retriever = get_hybrid_retriever()
    reranker = get_reranker()

    # Get file name mapping for citations
    file_names = await _get_file_names(db, document_ids)

    # Step 1: Analyze the query
    analysis = await analyze_query(question)

    # Step 2: Rewrite for retrieval
    search_query = await rewrite_query(question)

    # Step 3: Plan sub-questions if needed
    if analysis.needs_planning:
        sub_questions = await decompose_query(question, analysis)
    else:
        sub_questions = [search_query]

    # Step 4: Retrieve + Rerank for each sub-question
    all_chunks: list[RerankResult] = []
    for sub_q in sub_questions:
        candidates = await retriever.search(
            sub_q, document_ids, top_k=settings.RETRIEVAL_TOP_K
        )
        ranked = await reranker.rerank(sub_q, candidates, top_n=settings.RERANK_TOP_N)
        all_chunks.extend(ranked)

    all_chunks = _deduplicate_chunks(all_chunks)
    all_chunks = _attach_file_names(all_chunks, file_names)

    # Step 5: Context evaluation with retry
    for attempt in range(settings.MAX_RETRIES):
        evaluation = await evaluate_context(question, all_chunks)
        if evaluation.is_sufficient:
            break

        # Retry with feedback-driven rewrite
        new_query = await rewrite_query(question, feedback=evaluation.gap)
        extra_candidates = await retriever.search(
            new_query, document_ids, top_k=10
        )
        extra_ranked = await reranker.rerank(new_query, extra_candidates, top_n=3)
        extra_ranked = _attach_file_names(extra_ranked, file_names)
        all_chunks.extend(extra_ranked)
        all_chunks = _deduplicate_chunks(all_chunks)

    # Step 6: Generate answer
    try:
        raw_answer = await generate_answer(question, all_chunks, analysis)
    except Exception as e:
        print(f"⚠ Answer generation failed: {e}")
        raw_answer = (
            "I'm sorry, I'm unable to generate an answer right now. "
            "The AI service is temporarily unavailable. Please try again in a moment."
        )

    # Step 7: Verify citations
    verified = verify_citations(raw_answer, all_chunks)

    return ChatResponse(
        session_id="",  # Set by the API route
        answer=verified.answer,
        citations=verified.citations,
        sub_questions=sub_questions if analysis.needs_planning else None,
        question_type=analysis.question_type,
        sources_searched=len(all_chunks),
    )


# ─── Streaming Pipeline ──────────────────────────────────────────────────────


async def run_agent_stream(
    question: str,
    document_ids: list[str] | None,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Run the agentic pipeline with SSE streaming.

    Yields SSE-formatted events:
        event: status   → pipeline stage updates
        event: chunk    → streamed answer text
        event: citations → final verified citations (JSON)
        event: done     → completion signal with metadata

    Args:
        question: User's question
        document_ids: Optional filter to specific documents
        db: Database session for fetching file names

    Yields:
        SSE-formatted event strings
    """
    settings = get_settings()
    retriever = get_hybrid_retriever()
    reranker = get_reranker()

    def sse_event(event: str, data: str) -> str:
        """Format an SSE event."""
        return f"event: {event}\ndata: {data}\n\n"

    # Get file name mapping
    file_names = await _get_file_names(db, document_ids)

    # Step 1: Analyze
    yield sse_event("status", "Analyzing your question...")
    analysis = await analyze_query(question)
    yield sse_event("status", f"Question type: {analysis.question_type}")

    # Step 2: Rewrite
    yield sse_event("status", "Optimizing search query...")
    search_query = await rewrite_query(question)

    # Step 3: Plan
    sub_questions = [search_query]
    if analysis.needs_planning:
        yield sse_event("status", "Breaking down into sub-questions...")
        sub_questions = await decompose_query(question, analysis)
        yield sse_event(
            "status",
            f"Searching {len(sub_questions)} sub-questions..."
        )

    # Step 4: Retrieve + Rerank
    yield sse_event("status", "Searching your documents...")
    all_chunks: list[RerankResult] = []
    for sub_q in sub_questions:
        candidates = await retriever.search(
            sub_q, document_ids, top_k=settings.RETRIEVAL_TOP_K
        )
        ranked = await reranker.rerank(sub_q, candidates, top_n=settings.RERANK_TOP_N)
        all_chunks.extend(ranked)

    all_chunks = _deduplicate_chunks(all_chunks)
    all_chunks = _attach_file_names(all_chunks, file_names)

    yield sse_event("status", f"Found {len(all_chunks)} relevant passages")

    # Step 5: Evaluate context (with retry)
    for attempt in range(settings.MAX_RETRIES):
        yield sse_event("status", "Evaluating context quality...")
        evaluation = await evaluate_context(question, all_chunks)
        if evaluation.is_sufficient:
            break

        yield sse_event("status", f"Refining search (attempt {attempt + 2})...")
        new_query = await rewrite_query(question, feedback=evaluation.gap)
        extra_candidates = await retriever.search(new_query, document_ids, top_k=10)
        extra_ranked = await reranker.rerank(new_query, extra_candidates, top_n=3)
        extra_ranked = _attach_file_names(extra_ranked, file_names)
        all_chunks.extend(extra_ranked)
        all_chunks = _deduplicate_chunks(all_chunks)

    # Step 6: Generate answer (streaming)
    yield sse_event("status", "Generating answer...")

    full_answer = ""
    llm_failed = False
    try:
        async for text_chunk in generate_answer_stream(question, all_chunks, analysis):
            full_answer += text_chunk
            yield sse_event("chunk", text_chunk)
    except Exception as e:
        print(f"⚠ Answer generation failed: {e}")
        llm_failed = True
        full_answer = (
            "I'm sorry, I'm unable to generate an answer right now. "
            "The AI service is temporarily unavailable (quota or rate limit exceeded). "
            "Please try again in a moment."
        )
        yield sse_event("chunk", full_answer)

    # Step 7: Verify citations (skip if LLM failed — no citations to verify)
    if not llm_failed:
        yield sse_event("status", "Verifying citations...")
        verified = verify_citations(full_answer, all_chunks)
    else:
        verified = VerifiedAnswer(answer=full_answer)

    # Send verified citations
    citations_json = json.dumps(
        [c.model_dump() for c in verified.citations],
        default=str,
    )
    yield sse_event("citations", citations_json)

    # Send completion signal
    done_data = json.dumps({
        "question_type": analysis.question_type,
        "sub_questions": sub_questions if analysis.needs_planning else None,
        "sources_searched": len(all_chunks),
        "citations_removed": verified.removed_count,
        "answer": verified.answer,
    })
    yield sse_event("done", done_data)
