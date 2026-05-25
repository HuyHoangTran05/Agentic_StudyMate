"""
Agentic StudyMate — Answer Generator

Step 6 of the agentic pipeline: generates citation-aware answers
from retrieved document chunks.

Supports two modes:
1. Sync (full response) — for study tools and non-streaming endpoints
2. Streaming (async generator) — for SSE chat responses

Citation format: [filename, page N]
Multi-LLM support with automatic fallback.
"""

from typing import AsyncGenerator

from app.core.agent.llm_client import get_llm_client
from app.core.agent.query_analyzer import QueryAnalysis
from app.core.reranker import RerankResult


GENERATOR_SYSTEM_PROMPT = """\
You are a strict academic assistant. You must ONLY answer the user's question
using the provided context. If the context does not contain sufficient
information to directly answer the question, or if the context is completely
unrelated to the topic of the question, you MUST immediately reply with
"I'm sorry, but the provided documents do not contain information to answer this question."
DO NOT attempt to draw creative analogies, make forced
comparisons, or use outside knowledge.

You must follow these rules strictly:

1. CITE EVERY CLAIM using this exact format: [filename, page N]
   - Use the filename and page number from the source metadata
   - Place citations immediately after the relevant statement
   
2. If you CANNOT find supporting information in the provided passages,
   respond with: "I'm sorry, but the provided documents do not contain information to answer this question."

3. Structure your answer clearly:
   - Use markdown formatting (headers, bold, lists) for readability
   - Start with a direct answer, then elaborate
   - For comparisons, use a structured format (table or side-by-side)

4. Be thorough but concise — focus on what the documents actually say.

5. Do NOT make up information or cite sources that aren't in the passages.\
"""


def _format_context(chunks: list[RerankResult]) -> str:
    """Format retrieved chunks into context text for the LLM."""
    if not chunks:
        return "No relevant passages found."

    passages = []
    for i, chunk in enumerate(chunks, 1):
        # Build source metadata line
        meta_parts = []
        if hasattr(chunk, "_file_name") and chunk._file_name:
            meta_parts.append(f"File: {chunk._file_name}")
        if chunk.page_number is not None:
            meta_parts.append(f"Page: {chunk.page_number}")
        if chunk.section_title:
            meta_parts.append(f"Section: {chunk.section_title}")

        meta_line = " | ".join(meta_parts) if meta_parts else "Source metadata unavailable"
        passages.append(f"--- Passage {i} [{meta_line}] ---\n{chunk.content}")

    return "\n\n".join(passages)


def _build_prompt(
    question: str,
    chunks: list[RerankResult],
    analysis: QueryAnalysis | None = None,
) -> str:
    """Build the full user prompt with question and context."""
    context = _format_context(chunks)

    type_hint = ""
    if analysis:
        type_hint = f"\n[Question type: {analysis.question_type}]"

    return (
        f"Question: {question}{type_hint}\n\n"
        f"=== DOCUMENT PASSAGES ===\n\n{context}\n\n"
        f"=== END PASSAGES ===\n\n"
        f"Answer the question based on the passages above. "
        f"If the passages are insufficient or unrelated, use the exact refusal "
        f"sentence from the system prompt. Cite every claim using [filename, page N] format."
    )


async def generate_answer(
    question: str,
    chunks: list[RerankResult],
    analysis: QueryAnalysis | None = None,
) -> str:
    """
    Generate a complete answer with citations (sync mode).

    Args:
        question: The user's question
        chunks: Reranked retrieval results with file_name attached
        analysis: Optional query analysis for context

    Returns:
        Complete answer text with inline citations
    """
    client = get_llm_client()
    prompt = _build_prompt(question, chunks, analysis)

    return await client.call_llm(
        prompt=prompt,
        system_prompt=GENERATOR_SYSTEM_PROMPT,
    )


async def generate_answer_stream(
    question: str,
    chunks: list[RerankResult],
    analysis: QueryAnalysis | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream answer generation with citations (async generator).

    Args:
        question: The user's question
        chunks: Reranked retrieval results with file_name attached
        analysis: Optional query analysis for context

    Yields:
        Text chunks as they arrive from the LLM
    """
    client = get_llm_client()
    prompt = _build_prompt(question, chunks, analysis)

    async for chunk in client.stream_llm(
        prompt=prompt,
        system_prompt=GENERATOR_SYSTEM_PROMPT,
    ):
        yield chunk
