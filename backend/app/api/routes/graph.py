"""Graph Explorer routes for inspecting Neo4j triplets."""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.db.neo4j_client import get_neo4j_client
from app.core.ingest.chunker import TextChunk
from app.core.ingest.graph_extractor import ingest_triplets_for_chunks
from app.db.session import async_session_factory, get_db
from app.models.db_models import Chunk, Document

router = APIRouter(prefix="/api/graph", tags=["graph"])
logger = logging.getLogger(__name__)


def _safe_error_message(error: Exception) -> str:
    """Return a compact error message without exposing configured secrets."""
    message = str(error) or error.__class__.__name__
    settings = get_settings()
    for secret in (
        settings.NEO4J_PASSWORD,
        settings.GROQ_API_KEY,
        settings.GEMINI_API_KEY,
        settings.OPENAI_API_KEY,
        settings.ANTHROPIC_API_KEY,
    ):
        if secret:
            message = message.replace(secret, "***")
    return message[:300]


def _compact_snippet(content: str | None, max_length: int = 260) -> str | None:
    if not content:
        return None
    snippet = " ".join(content.split())
    return snippet if len(snippet) <= max_length else f"{snippet[:max_length].rstrip()}..."


def _chunk_to_text_chunk(chunk: Chunk) -> TextChunk:
    return TextChunk(
        content=chunk.content,
        chunk_index=chunk.chunk_index,
        page_number=chunk.page_number,
        section_title=chunk.section_title,
        metadata={
            "document_id": chunk.document_id,
            "image_url": chunk.image_url,
        },
    )


async def _rebuild_document_graph_job(document_id: str) -> None:
    """Rebuild Neo4j relationships for a document from existing SQLite chunks."""
    try:
        async with async_session_factory() as db:
            document = await db.get(Document, document_id)
            if not document:
                logger.warning("Graph rebuild skipped; document %s no longer exists", document_id)
                return

            result = await db.execute(
                select(Chunk)
                .where(Chunk.document_id == document_id)
                .order_by(Chunk.chunk_index.asc())
            )
            chunks = list(result.scalars().all())
            if not chunks:
                logger.warning("Graph rebuild skipped; document %s has no chunks", document_id)
                return

            chunk_ids = [chunk.id for chunk in chunks]
            neo4j_client = get_neo4j_client()
            deleted = await neo4j_client.delete_triplets_for_chunk_ids(chunk_ids)
            logger.info(
                "Graph rebuild removed %s existing relationships for document %s",
                deleted,
                document_id,
            )

            chunk_sources = [(_chunk_to_text_chunk(chunk), chunk.id) for chunk in chunks]
            await ingest_triplets_for_chunks(chunk_sources)
            logger.info(
                "Graph rebuild finished for document %s (%s chunks)",
                document_id,
                len(chunks),
            )
    except Exception as error:
        logger.error(
            "Graph rebuild failed for document %s: %s",
            document_id,
            _safe_error_message(error),
        )


@router.post("/documents/{document_id}/rebuild")
async def rebuild_document_graph(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Queue a Knowledge Graph rebuild for an existing document's chunks."""
    document = await db.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        select(Chunk)
        .where(Chunk.document_id == document_id)
        .order_by(Chunk.chunk_index.asc())
    )
    chunks = list(result.scalars().all())
    if not chunks:
        return {
            "status": "warning",
            "document_id": document.id,
            "file_name": document.file_name,
            "chunks_processed": 0,
            "message": "This document has no indexed chunks to rebuild from.",
        }

    settings = get_settings()
    if not settings.get_available_llm():
        return {
            "status": "warning",
            "document_id": document.id,
            "file_name": document.file_name,
            "chunks_processed": len(chunks),
            "message": "No LLM provider is configured. Configure an LLM before rebuilding the graph.",
        }

    try:
        await get_neo4j_client().verify_connection()
    except Exception as error:
        return {
            "status": "error",
            "document_id": document.id,
            "file_name": document.file_name,
            "chunks_processed": len(chunks),
            "message": "Neo4j is unavailable. Start Neo4j before rebuilding the graph.",
            "error": _safe_error_message(error),
        }

    background_tasks.add_task(_rebuild_document_graph_job, document_id)

    return {
        "status": "queued",
        "document_id": document.id,
        "file_name": document.file_name,
        "chunks_processed": len(chunks),
        "message": "Knowledge graph rebuild started. Refresh in a moment.",
    }


@router.get("/triplets")
async def get_graph_triplets(
    q: str | None = Query(default=None),
    document_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """Return Neo4j triplets enriched with source document/chunk metadata."""
    selected_document = None
    selected_chunks: list[Chunk] = []

    if document_id:
        selected_document = await db.get(Document, document_id)
        if selected_document:
            result = await db.execute(select(Chunk).where(Chunk.document_id == document_id))
            selected_chunks = list(result.scalars().all())

        if not selected_document:
            return {
                "triplets": [],
                "total": 0,
                "status": "warning",
                "message": "Selected document was not found.",
                "error": None,
                "selected_document_id": document_id,
                "selected_document_has_triplets": False,
            }

        if not selected_chunks:
            return {
                "triplets": [],
                "total": 0,
                "status": "warning",
                "message": "No indexed chunks were found for the selected document.",
                "error": None,
                "selected_document_id": document_id,
                "selected_document_has_triplets": False,
            }

    try:
        neo4j = get_neo4j_client()
        if document_id:
            raw_triplets = await neo4j.list_triplets_by_chunk_ids(
                chunk_ids=[chunk.id for chunk in selected_chunks],
                query=q.strip() if q and q.strip() else None,
                limit=limit,
            )
        elif q and q.strip():
            raw_triplets = await neo4j.search_triplets(q.strip(), limit=limit)
        else:
            raw_triplets = await neo4j.list_triplets(limit=limit)
    except Exception as error:
        return {
            "triplets": [],
            "total": 0,
            "status": "error",
            "message": "Neo4j is unavailable. Start Neo4j and refresh.",
            "error": _safe_error_message(error),
            "selected_document_id": document_id,
            "selected_document_has_triplets": False if document_id else None,
        }

    deduped: list[dict] = []
    seen: set[tuple[str, str, str, str | None]] = set()
    for triplet in raw_triplets:
        key = (
            str(triplet.get("source") or ""),
            str(triplet.get("relation") or ""),
            str(triplet.get("target") or ""),
            triplet.get("chunk_id"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(triplet)

    chunk_ids = [triplet.get("chunk_id") for triplet in deduped if triplet.get("chunk_id")]
    chunk_lookup: dict[str, tuple[Chunk, Document]] = {}

    if document_id and selected_document:
        for chunk in selected_chunks:
            chunk_lookup[chunk.id] = (chunk, selected_document)
    elif chunk_ids:
        result = await db.execute(
            select(Chunk, Document)
            .join(Document, Chunk.document_id == Document.id)
            .where(Chunk.id.in_(chunk_ids))
        )
        for chunk, document in result.all():
            chunk_lookup[chunk.id] = (chunk, document)

    enriched = []
    for triplet in deduped:
        chunk_id = triplet.get("chunk_id")
        chunk_document = chunk_lookup.get(chunk_id) if chunk_id else None

        if document_id and (not chunk_document or chunk_document[1].id != document_id):
            continue

        chunk = chunk_document[0] if chunk_document else None
        document = chunk_document[1] if chunk_document else None

        enriched.append(
            {
                "source": triplet.get("source") or "",
                "relation": triplet.get("relation") or "RELATED_TO",
                "target": triplet.get("target") or "",
                "chunk_id": chunk_id,
                "document_id": document.id if document else None,
                "file_name": document.file_name if document else None,
                "page_number": chunk.page_number if chunk else None,
                "section_title": chunk.section_title if chunk else None,
                "snippet": _compact_snippet(chunk.content if chunk else None),
            }
        )

    return {
        "triplets": enriched,
        "total": len(enriched),
        "status": "ok" if enriched or not document_id else "warning",
        "message": None if enriched or not document_id else "No graph relationships were found for the selected document.",
        "error": None,
        "selected_document_id": document_id,
        "selected_document_has_triplets": bool(enriched) if document_id else None,
    }
