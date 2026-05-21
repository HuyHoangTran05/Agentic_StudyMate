"""
Agentic StudyMate — Context Evaluator

Step 5 of the agentic pipeline (after retrieval + reranking):
evaluates whether the retrieved chunks contain enough information
to answer the user's question.

If insufficient, returns a gap description that the query rewriter
uses to craft a better search query on retry.
"""

from dataclasses import dataclass

from app.core.agent.llm_client import get_llm_client
from app.core.reranker import RerankResult


EVALUATOR_SYSTEM_PROMPT = """\
You are a context sufficiency evaluator for a study assistant.

Given a user's question and a set of retrieved text passages from their documents,
determine if the passages contain enough information to write a complete,
well-supported answer.

Respond ONLY with a JSON object:
{
  "is_sufficient": boolean - true if the passages contain enough info to answer fully,
  "confidence": float between 0.0 and 1.0 - how confident you are in the assessment,
  "gap": string - if insufficient, describe what specific information is MISSING.
          If sufficient, set to empty string ""
}

Guidelines:
- Be generous: if the passages cover the main points, mark as sufficient
- Only mark insufficient if KEY information is clearly missing
- The gap description should be specific enough to guide a new search query
- Consider that partial answers are acceptable — mark insufficient only if
  the passages would lead to a misleading or very incomplete answer\
"""


@dataclass
class ContextEvaluation:
    """Result of evaluating context sufficiency."""
    is_sufficient: bool = True
    confidence: float = 1.0
    gap: str = ""


async def evaluate_context(
    question: str,
    chunks: list[RerankResult],
) -> ContextEvaluation:
    """
    Evaluate if retrieved chunks are sufficient to answer the question.

    Args:
        question: The original user question
        chunks: Reranked retrieval results

    Returns:
        ContextEvaluation with sufficiency assessment
    """
    # If no chunks at all, definitely insufficient
    if not chunks:
        return ContextEvaluation(
            is_sufficient=False,
            confidence=1.0,
            gap="No relevant passages were found in the uploaded documents.",
        )

    client = get_llm_client()

    try:
        # Format chunks for the LLM
        passages = []
        for i, chunk in enumerate(chunks, 1):
            source = f"[Source: page {chunk.page_number}]" if chunk.page_number else ""
            passages.append(f"Passage {i} {source}:\n{chunk.content}")

        passages_text = "\n\n---\n\n".join(passages)

        prompt = (
            f"Question: {question}\n\n"
            f"Retrieved passages:\n\n{passages_text}\n\n"
            f"Are these passages sufficient to answer the question?"
        )

        result = await client.call_llm_json(
            prompt=prompt,
            system_prompt=EVALUATOR_SYSTEM_PROMPT,
        )

        return ContextEvaluation(
            is_sufficient=result.get("is_sufficient", True),
            confidence=result.get("confidence", 0.5),
            gap=result.get("gap", ""),
        )

    except Exception as e:
        print(f"⚠ Context evaluation failed, assuming sufficient: {e}")
        # On failure, assume sufficient to avoid infinite retry loops
        return ContextEvaluation(
            is_sufficient=True,
            confidence=0.5,
            gap="",
        )
