"""
Agentic StudyMate — Query Planner

Step 3 of the agentic pipeline: decomposes complex questions
into sub-questions for more targeted retrieval.

Only runs when QueryAnalysis.needs_planning is True.

Example:
    "Compare photosynthesis and cellular respiration"
    → ["What is photosynthesis?",
       "What is cellular respiration?",
       "What are the key differences between photosynthesis and cellular respiration?"]
"""

from app.core.agent.llm_client import get_llm_client
from app.core.agent.query_analyzer import QueryAnalysis


PLANNER_SYSTEM_PROMPT = """\
You are a question decomposition assistant for an educational study tool.

Given a complex question, break it down into 2-4 simpler sub-questions that,
when answered individually, provide all the information needed to answer
the original question.

Rules:
- Each sub-question should be self-contained and searchable
- Keep sub-questions focused on one concept each
- For comparisons: create one sub-question per item, plus one for differences/similarities
- For multi-part questions: create one sub-question per part
- Maximum 4 sub-questions
- Minimum 2 sub-questions

Respond ONLY with a JSON object:
{
  "sub_questions": ["question 1", "question 2", ...]
}\
"""


async def decompose_query(
    question: str,
    analysis: QueryAnalysis | None = None,
) -> list[str]:
    """
    Decompose a complex question into sub-questions.

    Args:
        question: The original user question
        analysis: Optional QueryAnalysis for context

    Returns:
        List of 2-4 sub-questions
    """
    client = get_llm_client()

    try:
        context_info = ""
        if analysis:
            context_info = (
                f"\nQuestion type: {analysis.question_type}"
                f"\nKey concepts: {', '.join(analysis.key_concepts)}"
            )

        result = await client.call_llm_json(
            prompt=(
                f"Decompose this question into sub-questions:"
                f"\n\n{question}"
                f"{context_info}"
            ),
            system_prompt=PLANNER_SYSTEM_PROMPT,
        )

        sub_questions = result.get("sub_questions", [])

        # Validate: must have 2-4 sub-questions
        if not sub_questions or len(sub_questions) < 2:
            return [question]  # Fallback: use original as-is

        return sub_questions[:4]  # Cap at 4

    except Exception as e:
        print(f"⚠ Query planning failed, using original question: {e}")
        return [question]
