"""
Agentic StudyMate — Pydantic Request/Response Schemas

Defines API data contracts for all endpoints.
"""

from datetime import datetime
from pydantic import BaseModel, Field


# ─── Citations ────────────────────────────────────────────────────────────────

class Citation(BaseModel):
    """A single citation reference."""
    file_name: str
    page_number: int | None = None
    chunk_id: str
    section_title: str | None = None
    snippet: str | None = None  # brief text excerpt
    image_url: str | None = None


# ─── Document Schemas ─────────────────────────────────────────────────────────

class DocumentResponse(BaseModel):
    """Response schema for a document."""
    id: str
    file_name: str
    file_type: str
    image_url: str | None = None
    upload_time: datetime
    total_chunks: int
    status: str

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    """List of documents."""
    documents: list[DocumentResponse]
    total: int


# ─── Chat Schemas ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Request to send a chat message."""
    session_id: str | None = None
    question: str
    document_ids: list[str] | None = None  # None = search all docs


class ChatResponse(BaseModel):
    """Response from the agentic chat pipeline."""
    session_id: str
    answer: str
    citations: list[Citation]
    sub_questions: list[str] | None = None
    question_type: str  # definition | comparison | summary | etc.
    sources_searched: int = 0


class ChatSessionResponse(BaseModel):
    """A chat session summary."""
    id: str
    title: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """A single chat message."""
    id: str
    role: str
    content: str
    image_url: str | None = None
    citations: list[Citation] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatHistoryResponse(BaseModel):
    """Full message history for a session."""
    session_id: str
    messages: list[MessageResponse]


# ─── Study Tools Schemas ──────────────────────────────────────────────────────

class StudyToolRequest(BaseModel):
    """Request for study tool generation."""
    document_id: str
    num_items: int = Field(default=5, ge=1, le=20)


class MCQOption(BaseModel):
    """A single MCQ option."""
    label: str  # A, B, C, D
    text: str


class MCQuestion(BaseModel):
    """A multiple-choice question."""
    question: str
    options: list[MCQOption]
    correct_answer: str  # label: A, B, C, D
    explanation: str


class QuizResponse(BaseModel):
    """Generated quiz."""
    document_id: str
    questions: list[MCQuestion]


class Flashcard(BaseModel):
    """A single flashcard."""
    front: str  # question/term
    back: str   # answer/definition


class FlashcardResponse(BaseModel):
    """Generated flashcards."""
    document_id: str
    flashcards: list[Flashcard]


class SummaryResponse(BaseModel):
    """Generated summary."""
    document_id: str
    summary: str
    key_points: list[str]


# ─── Upload Schemas ───────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Response after file upload."""
    document_id: str
    file_name: str
    status: str
    message: str


class ImageUploadResponse(BaseModel):
    """Response after image upload and vision extraction."""
    document_id: str
    file_name: str
    image_url: str
    extracted_text: str
    total_chunks: int
    status: str
