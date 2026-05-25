"""
Agentic StudyMate — SQLAlchemy ORM Models

Defines the database schema:
- User (single default user for MVP)
- Document (uploaded files)
- Chunk (text segments with metadata)
- ChatSession (conversation threads)
- Message (individual chat messages with citations)
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def generate_uuid() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


# ─── Users ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    email = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")


# ─── Documents ────────────────────────────────────────────────────────────────

class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf, docx, txt, image
    file_path = Column(String, nullable=True)    # path to stored file
    image_url = Column(String, nullable=True)    # public URL for uploaded images
    upload_time = Column(DateTime, default=utcnow)
    total_chunks = Column(Integer, default=0)
    status = Column(String, default="processing")  # processing | ready | failed

    # Relationships
    user = relationship("User", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


# ─── Chunks ───────────────────────────────────────────────────────────────────

class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True, default=generate_uuid)
    document_id = Column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)
    section_title = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    vector_id = Column(String, nullable=True)  # ID stored in Qdrant

    # Relationships
    document = relationship("Document", back_populates="chunks")


# ─── Chat Sessions ───────────────────────────────────────────────────────────

class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=generate_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("Message", back_populates="session", cascade="all, delete-orphan")


# ─── Messages ─────────────────────────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)    # user | assistant
    content = Column(Text, nullable=False)
    citations = Column(JSON, nullable=True)  # [{file_name, page_number, chunk_id}]
    created_at = Column(DateTime, default=utcnow)

    # Relationships
    session = relationship("ChatSession", back_populates="messages")
