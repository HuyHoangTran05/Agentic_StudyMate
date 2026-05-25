"""
Agentic StudyMate — Database Initialization

Creates all tables and seeds a default user for MVP (no auth).
"""

from app.models.db_models import Base, User, generate_uuid
from app.db.session import engine, async_session_factory
from sqlalchemy import select

# Default user ID — used throughout the app when auth is skipped
DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_USER_EMAIL = "student@studymate.local"


async def _ensure_image_columns(conn):
    """Add image URL columns for existing SQLite databases."""
    documents_info = await conn.exec_driver_sql("PRAGMA table_info(documents)")
    document_columns = {row[1] for row in documents_info.fetchall()}
    if "image_url" not in document_columns:
        await conn.exec_driver_sql("ALTER TABLE documents ADD COLUMN image_url VARCHAR")

    chunks_info = await conn.exec_driver_sql("PRAGMA table_info(chunks)")
    chunk_columns = {row[1] for row in chunks_info.fetchall()}
    if "image_url" not in chunk_columns:
        await conn.exec_driver_sql("ALTER TABLE chunks ADD COLUMN image_url VARCHAR")


async def init_db():
    """Create all tables and seed default data."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
