"""
Agentic StudyMate — Query Analyzer

Step 1 of the agentic pipeline: classifies the user's question.
Single LLM call with structured JSON output to determine:
- Question type (definition, explanation, comparison, etc.)
- Whether the question is complex
- Whether it needs decomposition into sub-questions
- Key concepts for retrieval
"""

from dataclasses import dataclass, field

from app.core.agent.llm_client import get_llm_client


ANALYZER_SYSTEM_PROMPT = """\
You are a query analysis assistant for an educational study tool.
Analyze the user's question and classify it.

Respond ONLY with a JSON object containing these fields:
{
  "question_type": one of ["definition", "explanation", "comparison", "summary", "application", "general"],
  "is_complex": boolean - true if the question requires multi-step reasoning or combines multiple concepts,
  "needs_planning": boolean - true if the question should be decomposed into sub-questions (e.g., comparisons, multi-part questions),
  "key_concepts": list of strings - the main topics/entities/terms mentioned in the question
}

Guidelines:
- "definition": asking what something IS (e.g., "What is photosynthesis?")
- "explanation": asking HOW or WHY something works (e.g., "How does DNA replication work?")
- "comparison": asking to compare/contrast two or more things (e.g., "Compare mitosis and meiosis")
- "summary": asking for a summary or overview (e.g., "Summarize chapter 3")
- "application": asking to apply a concept (e.g., "Give an example of natural selection")
- "general": anything else

Set needs_planning=true when:
- The question compares multiple things
- The question has multiple distinct parts
- The question requires synthesizing information from different topics\
"""


@dataclass
class QueryAnalysis:
    """Result of analyzing a user query."""
    question_type: str = "general"
    is_complex: bool = False
    needs_planning: bool = False
    key_concepts: list[str] = field(default_factory=list)


async def analyze_query(question: str) -> QueryAnalysis:
    """
    Analyze and classify a user question.

    Args:
        question: The raw user question

    Returns:
        QueryAnalysis with classification results
    """
    client = get_llm_client()

    try:
        result = await client.call_llm_json(
            prompt=f"Analyze this question:\n\n{question}",
            system_prompt=ANALYZER_SYSTEM_PROMPT,
        )

        return QueryAnalysis(
            question_type=result.get("question_type", "general"),
            is_complex=result.get("is_complex", False),
            needs_planning=result.get("needs_planning", False),
            key_concepts=result.get("key_concepts", []),
        )

    except Exception as e:
        print(f"⚠ Query analysis failed, using defaults: {e}")
        return QueryAnalysis(
            question_type="general",
            is_complex=False,
            needs_planning=False,
            key_concepts=[],
        )
