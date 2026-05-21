"""
Agentic StudyMate — Query Rewriter

Step 2 of the agentic pipeline: rewrites conversational questions
into optimal retrieval queries.

Supports two modes:
1. Initial rewrite: removes filler, focuses on key terms
2. Feedback-based rewrite: incorporates gap description from context
   evaluator to target missing information on retry
"""

from app.core.agent.llm_client import get_llm_client


REWRITER_SYSTEM_PROMPT = """\
You are a search query optimizer for an educational document retrieval system.

Your job is to rewrite the user's question into an optimal search query that will
find the most relevant passages in uploaded study documents.

Rules:
- Remove conversational filler ("Can you tell me...", "I was wondering...")
- Focus on key terms and concepts
- Keep academic/technical terminology intact
- Make the query specific enough to find relevant passages
- Output ONLY the rewritten query text — no explanation, no quotes, no prefix\
"""


REWRITER_WITH_FEEDBACK_PROMPT = """\
You are a search query optimizer for an educational document retrieval system.

A previous search did not find enough information. You are given:
1. The original question
2. A description of what information is MISSING

Rewrite the query to specifically target the missing information.
Try different terminology, synonyms, or related concepts that might
appear in study documents.

Output ONLY the rewritten query text — no explanation, no quotes, no prefix\
"""


async def rewrite_query(
    question: str,
    feedback: str | None = None,
) -> str:
    """
    Rewrite a user question into an optimal retrieval query.

    Args:
        question: The raw user question
        feedback: Optional gap description from context evaluator (for retry)

    Returns:
        Optimized search query string
    """
    client = get_llm_client()

    try:
        if feedback:
            prompt = (
                f"Original question: {question}\n\n"
                f"Missing information: {feedback}\n\n"
                f"Rewrite the query to find the missing information."
            )
            system_prompt = REWRITER_WITH_FEEDBACK_PROMPT
        else:
            prompt = f"Rewrite this question as a search query:\n\n{question}"
            system_prompt = REWRITER_SYSTEM_PROMPT

        result = await client.call_llm(
            prompt=prompt,
            system_prompt=system_prompt,
        )

        rewritten = result.strip().strip('"').strip("'")

        # Fallback: if the LLM returned nothing useful, use the original
        if not rewritten or len(rewritten) < 3:
            return question

        return rewritten

    except Exception as e:
        print(f"⚠ Query rewrite failed, using original: {e}")
        return question
