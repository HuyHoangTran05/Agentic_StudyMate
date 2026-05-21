"""
Agentic StudyMate — Document Management Routes

GET  /api/documents       — List all documents for the default user
GET  /api/documents/{id}  — Get a single document's details
DELETE /api/documents/{id} — Delete a document and all its chunks + vectors
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.db.init_db import DEFAULT_USER_ID
from app.models.db_models import Document, Chunk
from app.models.schemas import DocumentResponse, DocumentListResponse

router = APIRouter(prefix="/api", tags=["documents"])


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(db: AsyncSession = Depends(get_db)):
    """List all documents for the current user."""
    result = await db.execute(
        select(Document)
        .where(Document.user_id == DEFAULT_USER_ID)
        .order_by(Document.upload_time.desc())
    )
    documents = result.scalars().all()

    return DocumentListResponse(
        documents=[DocumentResponse.model_validate(doc) for doc in documents],
        total=len(documents),
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    """Get details of a specific document."""
    doc = await db.get(Document, document_id)
    if not doc or doc.user_id != DEFAULT_USER_ID:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.model_validate(doc)


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)):
    """
    Delete a document and all associated data:
    - Database chunks (cascade)
    - Vector embeddings in Qdrant
    - File on disk
    """
    doc = await db.get(Document, document_id)
    if not doc or doc.user_id != DEFAULT_USER_ID:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete vectors from Qdrant
    try:
        from app.core.retrieval.vector_store import get_vector_store
        vector_store = get_vector_store()
        await vector_store.delete_by_document(document_id)
    except Exception as e:
        print(f"⚠ Could not delete vectors from Qdrant: {e}")

    # Remove from BM25 index
    try:
        from app.core.retrieval.bm25_store import get_bm25_store
        bm25_store = get_bm25_store()
        bm25_store.remove_document(document_id)
    except Exception as e:
        print(f"⚠ Could not remove from BM25 index: {e}")

    # Delete file from disk
    if doc.file_path:
        import os
        try:
            os.remove(doc.file_path)
        except FileNotFoundError:
            pass

    # Delete document (chunks cascade)
    await db.delete(doc)
    await db.commit()

    return {"message": f"Document '{doc.file_name}' deleted successfully", "document_id": document_id}
