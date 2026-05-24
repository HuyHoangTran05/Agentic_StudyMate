"""
Agentic StudyMate — Study Tools API Routes (Map-Reduce)

Endpoints:
- POST /api/study-tools/quiz       -> Generate MCQs from a document
- POST /api/study-tools/flashcards -> Generate flashcards from a document
- POST /api/study-tools/summary    -> Generate summary + key points from a document

Uses a Map-Reduce approach to handle large documents safely:
  MAP   -> Split chunks into small batches (5 chunks each)
  CALL  -> LLM per batch with strict JSON output + throttling
  REDUCE -> Aggregate all results into a single response

This prevents Groq/Gemini TPM (Tokens Per Minute) and 429 rate limit errors
when processing documents with 30+ chunks.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.db_models import Document, Chunk
from app.models.schemas import (
    StudyToolRequest,
    QuizResponse,
    MCQuestion,
    MCQOption,
    FlashcardResponse,
    Flashcard,
    SummaryResponse,
)
from app.core.agent.map_reduce import map_reduce_llm, map_reduce_summary


router = APIRouter(prefix="/api/study-tools", tags=["study-tools"])


# --- Helpers ------------------------------------------------------------------


async def _get_document_chunks(
    document_id: str, db: AsyncSession
) -> tuple[Document, list[Chunk]]:
    """Fetch document and its chunks, raising 404 if not found."""
    # Fetch document
    result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is still {document.status}. Please wait for processing to complete.",
        )

    # Fetch chunks ordered by index
    result = await db.execute(
        select(Chunk)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index)
    )
    chunks = result.scalars().all()

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="Document has no processed chunks.",
        )

    return document, chunks


# --- POST /api/study-tools/quiz --- Generate MCQs ----------------------------


QUIZ_SYSTEM_PROMPT = """\
You are an expert educational quiz generator. Generate multiple-choice questions
based ONLY on the provided document passages.

Each question must:
- Be directly answerable from the provided text
- Have exactly 4 options (A, B, C, D)
- Have exactly one correct answer
- Include a brief explanation of why the correct answer is right

You MUST respond with a valid JSON object and NOTHING else.
No markdown, no code fences, no extra text. Just pure JSON:
{
  "questions": [
    {
      "question": "the question text",
      "options": [
        {"label": "A", "text": "option text"},
        {"label": "B", "text": "option text"},
        {"label": "C", "text": "option text"},
        {"label": "D", "text": "option text"}
      ],
      "correct_answer": "A",
      "explanation": "brief explanation"
    }
  ]
}\
"""

QUIZ_USER_TEMPLATE = (
    "Generate exactly {num_items} multiple-choice questions from these passages "
    "of '{file_name}':\n\n{context}"
)


@router.post("/quiz", response_model=QuizResponse)
async def generate_quiz(
    request: StudyToolRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate multiple-choice quiz questions from a document using Map-Reduce."""
    document, chunks = await _get_document_chunks(request.document_id, db)

    try:
        raw_questions = await map_reduce_llm(
            chunks=chunks,
            system_prompt=QUIZ_SYSTEM_PROMPT,
            user_prompt_template=QUIZ_USER_TEMPLATE,
            result_key="questions",
            file_name=document.file_name,
            total_items=request.num_items,
        )
    except Exception as e:
        print(f"[ERROR] Quiz generation failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Unable to generate quiz right now. The AI service is temporarily unavailable. Please try again in a moment.",
        )

    # Parse into response models (take requested count)
    questions = []
    for q in raw_questions[:request.num_items]:
        try:
            options = [
                MCQOption(label=opt["label"], text=opt["text"])
                for opt in q.get("options", [])
            ]
            questions.append(MCQuestion(
                question=q["question"],
                options=options,
                correct_answer=q.get("correct_answer", "A"),
                explanation=q.get("explanation", ""),
            ))
        except (KeyError, TypeError) as e:
            print(f"[WARN] Skipping malformed question: {e}")
            continue

    return QuizResponse(
        document_id=request.document_id,
        questions=questions,
    )


# --- POST /api/study-tools/flashcards --- Generate Flashcards -----------------


FLASHCARD_SYSTEM_PROMPT = """\
You are an expert educational flashcard generator. Generate study flashcards
based ONLY on the provided document passages.

Each flashcard must:
- Have a clear, specific question or term on the front
- Have a concise, accurate answer or definition on the back
- Be directly based on the provided text

You MUST respond with a valid JSON object and NOTHING else.
No markdown, no code fences, no extra text. Just pure JSON:
{
  "flashcards": [
    {
      "front": "question or term",
      "back": "answer or definition"
    }
  ]
}\
"""

FLASHCARD_USER_TEMPLATE = (
    "Generate exactly {num_items} study flashcards from these passages "
    "of '{file_name}':\n\n{context}"
)


@router.post("/flashcards", response_model=FlashcardResponse)
async def generate_flashcards(
    request: StudyToolRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate study flashcards from a document using Map-Reduce."""
    document, chunks = await _get_document_chunks(request.document_id, db)

    try:
        raw_flashcards = await map_reduce_llm(
            chunks=chunks,
            system_prompt=FLASHCARD_SYSTEM_PROMPT,
            user_prompt_template=FLASHCARD_USER_TEMPLATE,
            result_key="flashcards",
            file_name=document.file_name,
            total_items=request.num_items,
        )
    except Exception as e:
        print(f"[ERROR] Flashcard generation failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Unable to generate flashcards right now. The AI service is temporarily unavailable. Please try again in a moment.",
        )

    # Parse into response models (take requested count)
    flashcards = []
    for fc in raw_flashcards[:request.num_items]:
        try:
            flashcards.append(Flashcard(front=fc["front"], back=fc["back"]))
        except (KeyError, TypeError) as e:
            print(f"[WARN] Skipping malformed flashcard: {e}")
            continue

    return FlashcardResponse(
        document_id=request.document_id,
        flashcards=flashcards,
    )


# --- POST /api/study-tools/summary --- Generate Summary ----------------------


SUMMARY_SYSTEM_PROMPT = """\
You are an expert educational summarizer. Generate a comprehensive summary
and key points from the provided document passages.

The summary should:
- Capture the main themes and arguments
- Be well-structured with clear paragraphs
- Use markdown formatting for readability

The key points should:
- Be the 5-8 most important takeaways
- Be concise (one sentence each)
- Cover different aspects of the content

You MUST respond with a valid JSON object and NOTHING else.
No markdown, no code fences, no extra text. Just pure JSON:
{
  "summary": "the full summary text with markdown formatting",
  "key_points": ["point 1", "point 2", ...]
}\
"""

SUMMARY_USER_TEMPLATE = (
    "Summarize these passages from '{file_name}' and extract key points:\n\n{context}"
)


@router.post("/summary", response_model=SummaryResponse)
async def generate_summary(
    request: StudyToolRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a summary and key points from a document using Map-Reduce."""
    document, chunks = await _get_document_chunks(request.document_id, db)

    try:
        result = await map_reduce_summary(
            chunks=chunks,
            system_prompt=SUMMARY_SYSTEM_PROMPT,
            user_prompt_template=SUMMARY_USER_TEMPLATE,
            file_name=document.file_name,
        )
    except Exception as e:
        print(f"[ERROR] Summary generation failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Unable to generate summary right now. The AI service is temporarily unavailable. Please try again in a moment.",
        )

    return SummaryResponse(
        document_id=request.document_id,
        summary=result.get("summary", ""),
        key_points=result.get("key_points", []),
    )
