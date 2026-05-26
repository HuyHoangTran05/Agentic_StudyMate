"""
Agentic StudyMate — Database Initialization

Creates all tables and seeds a default user for MVP (no auth).
"""

import hashlib
from pathlib import Path

from app.models.db_models import Base, User, generate_uuid
from app.db.session import engine, async_session_factory
from sqlalchemy import select

# Default user ID — used throughout the app when auth is skipped
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_USER_EMAIL = "student@studymate.local"


async def _ensure_document_columns(conn):
    """Add document columns and indexes for existing SQLite databases."""
    documents_info = await conn.exec_driver_sql("PRAGMA table_info(documents)")
    document_columns = {row[1] for row in documents_info.fetchall()}
    if "image_url" not in document_columns:
        await conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN image_url VARCHAR")
    if "file_hash" not in document_columns:
        await conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN file_hash VARCHAR")

    await _backfill_document_hashes(conn)

    await conn.exec_driver_sql(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_documents_file_hash "
        "ON documents(file_hash)"
    )


async def _backfill_document_hashes(conn):
    """Populate file_hash for existing documents when the source file still exists."""
    existing_hashes_result = await conn.exec_driver_sql(
        "SELECT file_hash FROM documents WHERE file_hash IS NOT NULL"
    )
    existing_hashes = {row[0] for row in existing_hashes_result.fetchall()}

    documents_result = await conn.exec_driver_sql(
        "SELECT id, file_path FROM documents "
        "WHERE file_hash IS NULL AND file_path IS NOT NULL"
    )

    for document_id, file_path in documents_result.fetchall():
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            continue

        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if file_hash in existing_hashes:
            continue

        await conn.exec_driver_sql(
            "UPDATE documents SET file_hash = ? WHERE id = ?",
            (file_hash, document_id),
        )
        existing_hashes.add(file_hash)


async def _ensure_image_columns(conn):
    """Add image URL columns for existing SQLite databases."""
    chunks_info = await conn.exec_driver_sql("PRAGMA table_info(chunks)")
    chunk_columns = {row[1] for row in chunks_info.fetchall()}
    if "image_url" not in chunk_columns:
        await conn.exec_driver_sql("ALTER TABLE chunks ADD COLUMN image_url VARCHAR")

    messages_info = await conn.exec_driver_sql("PRAGMA table_info(messages)")
    message_columns = {row[1] for row in messages_info.fetchall()}
    if "image_url" not in message_columns:
        await conn.exec_driver_sql("ALTER TABLE messages ADD COLUMN image_url VARCHAR")


async def init_db():
    """Create all tables and seed default data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_document_columns(conn)
        await _ensure_image_columns(conn)

    # Seed default user if not exists
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.id == DEFAULT_USER_ID)
        )
        if result.scalar_one_or_none() is None:
            default_user = User(
                id=DEFAULT_USER_ID,
                email=DEFAULT_USER_EMAIL,
            )
            session.add(default_user)
            await session.commit()
            print(f"✓ Created default user: {DEFAULT_USER_EMAIL}")
        else:
            print(f"✓ Default user already exists: {DEFAULT_USER_EMAIL}")
