"""
Agentic StudyMate system status routes.

Provides a safe, read-only snapshot of local RAG service health without
exposing API keys, passwords, or database URLs.
"""

import asyncio
import re
from typing import Any

from fastapi import APIRouter, Depends
from qdrant_client import QdrantClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.db.neo4j_client import get_neo4j_client
from app.db.session import get_db
from app.models.db_models import Chunk, Document


router = APIRouter(prefix="/api/system", tags=["system"])


def _safe_error(exc: Exception) -> str:
    """Return a short error message with obvious credentials removed."""
    message = str(exc)
    message = re.sub(r"//([^:/@\s]+):([^@\s]+)@", "//***:***@", message)
    return message[:240]


def _safe_uri(uri: str) -> str:
    """Hide userinfo if a URI contains credentials."""
    return re.sub(r"//([^:/@\s]+):([^@\s]+)@", "//***:***@", uri)


async def _database_status(db: AsyncSession) -> dict[str, Any]:
    """Count metadata rows in SQLite/Postgres through SQLAlchemy."""
    documents = await db.scalar(select(func.count(Document.id)))
    chunks = await db.scalar(select(func.count(Chunk.id)))

    status_rows = await db.execute(
        select(Document.status, func.count(Document.id)).group_by(Document.status)
    )
    counts = {status: count for status, count in status_rows.all()}

    return {
        "status": "ok",
        "documents": int(documents or 0),
        "chunks": int(chunks or 0),
        "ready_documents": int(counts.get("ready", 0)),
        "processing_documents": int(counts.get("processing", 0)),
        "failed_documents": int(counts.get("failed", 0)),
    }


async def _qdrant_status() -> dict[str, Any]:
    """Check Qdrant collection availability and point count."""
    settings = get_settings()
    base = {
        "status": "warning",
        "host": settings.QDRANT_HOST,
        "port": settings.QDRANT_PORT,
        "collection": settings.QDRANT_COLLECTION,
        "points": None,
    }

    def _check() -> int:
        client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        client.get_collection(settings.QDRANT_COLLECTION)
        return int(client.count(collection_name=settings.QDRANT_COLLECTION, exact=True).count)

    try:
        points = await asyncio.to_thread(_check)
        return {**base, "status": "ok", "points": points}
    except Exception as exc:
        return {**base, "status": "error", "error": _safe_error(exc)}


async def _neo4j_status() -> dict[str, Any]:
    """Check Neo4j availability and relationship count."""
    settings = get_settings()
    base = {
        "status": "not_configured",
        "uri": _safe_uri(settings.NEO4J_URI),
        "triplets": None,
    }

    if not (settings.NEO4J_URI and settings.NEO4J_USER and settings.NEO4J_PASSWORD):
        return {**base, "error": "Neo4j credentials are not configured."}

    try:
        client = get_neo4j_client()
        await client.verify_connection()
        triplets = await client.count_triplets()
        return {**base, "status": "ok", "triplets": triplets}
    except Exception as exc:
        return {**base, "status": "error", "error": _safe_error(exc)}


def _llm_status() -> dict[str, Any]:
    """Report configured LLM provider and models without secrets."""
    settings = get_settings()
    provider = settings.get_available_llm()
    return {
        "status": "configured" if provider else "not_configured",
        "provider": provider,
        "text_model": settings.TEXT_MODEL,
        "vision_model": settings.VISION_MODEL,
    }


@router.get("/status")
async def system_status(db: AsyncSession = Depends(get_db)):
    """Return a safe health snapshot for the Agentic StudyMate stack."""
    database = await _database_status(db)
    qdrant, neo4j = await asyncio.gather(_qdrant_status(), _neo4j_status())
    settings = get_settings()

    return {
        "api": {"status": "ok"},
        "database": database,
        "qdrant": qdrant,
        "neo4j": neo4j,
        "llm": _llm_status(),
        "models": {
            "embedding_model": settings.EMBEDDING_MODEL,
            "reranker_model": settings.RERANKER_MODEL,
        },
    }
