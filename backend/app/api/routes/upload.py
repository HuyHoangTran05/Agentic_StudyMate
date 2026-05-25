"""
Agentic StudyMate — Document Upload Route

POST /api/upload — Accepts file upload, triggers the full ingestion pipeline:
1. Validate file type (PDF, DOCX, TXT)
2. Save file to disk
3. Create document record in DB (status=processing)
4. Extract text → chunk → embed → store vectors
5. Update document status to ready/failed

The ingestion runs as a background task so the upload returns immediately.
"""

import os
import traceback
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.init_db import DEFAULT_USER_ID
from app.models.db_models import Document, Chunk
from app.models.schemas import UploadResponse
from app.config import get_settings

router = APIRouter(prefix="/api", tags=["upload"])

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}


def get_file_extension(filename: str) -> str:
    """Extract and validate file extension."""
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document file for processing.
    
    Accepts PDF, DOCX, or TXT files.
    Returns immediately with document_id; processing happens in background.
    """
    # Validate file type
    file_ext = get_file_extension(file.filename or "unknown")
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{file_ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Ensure upload directory exists
    settings = get_settings()
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save file to disk
    import uuid
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}.{file_ext}"
    file_path = upload_dir / safe_filename

    content = await file.read()
    file_path.write_bytes(content)

    # Create document record
    document = Document(
        id=file_id,
        user_id=DEFAULT_USER_ID,
        file_name=file.filename or "unknown",
        file_type=file_ext,
        file_path=str(file_path),
        status="processing",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Schedule background ingestion
    background_tasks.add_task(
        run_ingestion_pipeline,
        document_id=file_id,
        file_path=str(file_path),
        file_type=file_ext,
    )

    return UploadResponse(
        document_id=file_id,
        file_name=file.filename or "unknown",
        status="processing",
        message=f"File uploaded successfully. Processing {file_ext.upper()} document...",
    )


async def run_ingestion_pipeline(document_id: str, file_path: str, file_type: str):
    """
    Background task: Extract → Chunk → Embed → Store.
    
    Updates document status to 'ready' on success or 'failed' on error.
    """
    from app.db.session import async_session_factory
    from app.core.ingest.extractor import extract_document
    from app.core.ingest.chunker import chunk_document
    from app.core.ingest.embedder import get_embedder

    async with async_session_factory() as db:
        try:
            print(f"📄 Starting ingestion for document {document_id}")

            # Step 1: Extract text
            print(f"  → Extracting text from {file_type.upper()}...")
            extraction = await extract_document(file_path, file_type)
            print(f"  ✓ Extracted {len(extraction.pages)} pages")

            # Step 2: Chunk text
            print(f"  → Chunking text...")
            chunks = chunk_document(extraction)
            print(f"  ✓ Created {len(chunks)} chunks")

            if not chunks:
                # No text found — mark as failed
                doc = await db.get(Document, document_id)
                if doc:
                    doc.status = "failed"
                    doc.total_chunks = 0
                await db.commit()
                print(f"  ⚠ No text extracted from document")
                return

            # Step 3: Generate embeddings
            print(f"  → Generating embeddings (CPU, this may take a moment)...")
            embedder = get_embedder()
            texts = [chunk.content for chunk in chunks]
            embedding_result = await embedder.embed_texts(texts)
            print(f"  ✓ Generated {len(embedding_result.vectors)} embeddings ({embedding_result.dimension}D)")

            # Step 4: Store chunks in database
            print(f"  → Storing chunks in database...")
            chunk_records = []
            for i, chunk in enumerate(chunks):
                chunk_record = Chunk(
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    page_number=chunk.page_number,
                    section_title=chunk.section_title,
                    vector_id=None,  # Set to the generated Qdrant point UUID on upsert
                )
                chunk_records.append(chunk_record)

            db.add_all(chunk_records)

            # Step 5: Store vectors in Qdrant (if available)
            try:
                from app.core.retrieval.vector_store import get_vector_store
                vector_store = get_vector_store()
                await vector_store.upsert_chunks(
                    chunks=chunk_records,
                    vectors=embedding_result.vectors,
                    document_id=document_id,
                )
                print(f"  ✓ Stored vectors in Qdrant")
            except Exception as e:
                print(f"  ⚠ Qdrant not available, skipping vector storage: {e}")
                # Continue without Qdrant — BM25 still works

            # Step 6: Add chunks to BM25 index
            try:
                from app.core.retrieval.bm25_store import get_bm25_store
                bm25_store = get_bm25_store()
                bm25_chunks = [
                    {
                        "chunk_id": cr.id,
                        "document_id": cr.document_id,
                        "content": cr.content,
                        "page_number": cr.page_number,
                        "section_title": cr.section_title,
                        "chunk_index": cr.chunk_index,
                    }
                    for cr in chunk_records
                ]
                bm25_store.add_chunks(bm25_chunks)
                print(f"  ✓ Added {len(bm25_chunks)} chunks to BM25 index")
            except Exception as e:
                print(f"  ⚠ BM25 indexing failed: {e}")

            # Update document status
            doc = await db.get(Document, document_id)
            if doc:
                doc.status = "ready"
                doc.total_chunks = len(chunks)

            await db.commit()
            print(f"✅ Ingestion complete for document {document_id}: {len(chunks)} chunks")

        except Exception as e:
            print(f"❌ Ingestion failed for document {document_id}: {e}")
            traceback.print_exc()
            # Mark as failed
            try:
                doc = await db.get(Document, document_id)
                if doc:
                    doc.status = "failed"
                await db.commit()
            except Exception:
                pass
