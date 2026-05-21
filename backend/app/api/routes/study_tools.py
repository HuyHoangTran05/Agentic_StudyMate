"""
Agentic StudyMate — Study Tools API Routes

Endpoints:
- POST /api/study-tools/quiz       → Generate MCQs from a document
- POST /api/study-tools/flashcards → Generate flashcards from a document
- POST /api/study-tools/summary    → Generate summary + key points from a document

All endpoints use the LLM with document chunks as context.
No retrieval step needed — uses ALL chunks from the specified document.
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
from app.core.agent.llm_client import get_llm_client


router = APIRouter(prefix="/api/study-tools", tags=["study-tools"])


# ─── Helpers ──────────────────────────────────────────────────────────────────


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


def _format_chunks_for_llm(chunks: list[Chunk], max_chunks: int = 30) -> str:
    """Format document chunks into context text, limited to avoid token overflow."""
    selected = chunks[:max_chunks]
    passages = []
    for chunk in selected:
        page_info = f" (page {chunk.page_number})" if chunk.page_number else ""
        section_info = f" — {chunk.section_title}" if chunk.section_title else ""
        passages.append(f"[Passage{page_info}{section_info}]\n{chunk.content}")
    return "\n\n---\n\n".join(passages)


# ─── POST /api/study-tools/quiz — Generate MCQs ─────────────────────────────


QUIZ_SYSTEM_PROMPT = """\
You are an expert educational quiz generator. Generate multiple-choice questions
based on the provided document content.

Each question must:
- Be directly answerable from the provided text
- Have exactly 4 options (A, B, C, D)
- Have exactly one correct answer
- Include a brief explanation of why the correct answer is right

Respond ONLY with a JSON object:
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


@router.post("/quiz", response_model=QuizResponse)
async def generate_quiz(
    request: StudyToolRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate multiple-choice quiz questions from a document."""
    document, chunks = await _get_document_chunks(request.document_id, db)
    context = _format_chunks_for_llm(chunks)
    client = get_llm_client()

    try:
        result = await client.call_llm_json(
            prompt=(
                f"Generate {request.num_items} multiple-choice questions from this document content:\n\n"
                f"Document: {document.file_name}\n\n"
                f"{context}"
            ),
            system_prompt=QUIZ_SYSTEM_PROMPT,
        )
    except Exception as e:
        print(f"⚠ Quiz generation failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Unable to generate quiz right now. The AI service is temporarily unavailable. Please try again in a moment.",
        )

    questions = []
    for q in result.get("questions", [])[:request.num_items]:
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

    return QuizResponse(
        document_id=request.document_id,
        questions=questions,
    )


# ─── POST /api/study-tools/flashcards — Generate Flashcards ─────────────────


FLASHCARD_SYSTEM_PROMPT = """\
You are an expert educational flashcard generator. Generate study flashcards
based on the provided document content.

Each flashcard must:
- Have a clear, specific question or term on the front
- Have a concise, accurate answer or definition on the back
- Be directly based on the document content

Respond ONLY with a JSON object:
{
  "flashcards": [
    {
      "front": "question or term",
      "back": "answer or definition"
    }
  ]
}\
"""


@router.post("/flashcards", response_model=FlashcardResponse)
async def generate_flashcards(
    request: StudyToolRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate study flashcards from a document."""
    document, chunks = await _get_document_chunks(request.document_id, db)
    context = _format_chunks_for_llm(chunks)
    client = get_llm_client()

    try:
        result = await client.call_llm_json(
            prompt=(
                f"Generate {request.num_items} study flashcards from this document content:\n\n"
                f"Document: {document.file_name}\n\n"
                f"{context}"
            ),
            system_prompt=FLASHCARD_SYSTEM_PROMPT,
        )
    except Exception as e:
        print(f"⚠ Flashcard generation failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Unable to generate flashcards right now. The AI service is temporarily unavailable. Please try again in a moment.",
        )

    flashcards = [
        Flashcard(front=fc["front"], back=fc["back"])
        for fc in result.get("flashcards", [])[:request.num_items]
    ]

    return FlashcardResponse(
        document_id=request.document_id,
        flashcards=flashcards,
    )


# ─── POST /api/study-tools/summary — Generate Summary ───────────────────────


SUMMARY_SYSTEM_PROMPT = """\
You are an expert educational summarizer. Generate a comprehensive summary
and key points from the provided document content.

The summary should:
- Capture the main themes and arguments
- Be well-structured with clear paragraphs
- Use markdown formatting for readability

The key points should:
- Be the 5-8 most important takeaways
- Be concise (one sentence each)
- Cover different aspects of the content

Respond ONLY with a JSON object:
{
  "summary": "the full summary text with markdown formatting",
  "key_points": ["point 1", "point 2", ...]
}\
"""


@router.post("/summary", response_model=SummaryResponse)
async def generate_summary(
    request: StudyToolRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate a summary and key points from a document."""
    document, chunks = await _get_document_chunks(request.document_id, db)
    context = _format_chunks_for_llm(chunks, max_chunks=50)  # More chunks for summary
    client = get_llm_client()

    try:
        result = await client.call_llm_json(
            prompt=(
                f"Summarize this document and extract key points:\n\n"
                f"Document: {document.file_name}\n\n"
                f"{context}"
            ),
            system_prompt=SUMMARY_SYSTEM_PROMPT,
        )
    except Exception as e:
        print(f"⚠ Summary generation failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Unable to generate summary right now. The AI service is temporarily unavailable. Please try again in a moment.",
        )

    return SummaryResponse(
        document_id=request.document_id,
        summary=result.get("summary", ""),
        key_points=result.get("key_points", []),
    )
