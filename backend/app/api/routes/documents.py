"""
Agentic StudyMate — Document Management Routes

GET  /api/documents       — List all documents for the default user
GET  /api/documents/{id}  — Get a single document's details
DELETE /api/documents/{id} — Delete a document and all its chunks + vectors
"""

import asyncio
import base64
from io import BytesIO
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.db.init_db import DEFAULT_USER_ID
from app.models.db_models import Document, Chunk
from app.models.schemas import (
    DocumentResponse,
    DocumentListResponse,
    ImageUploadResponse,
)

router = APIRouter(prefix="/api", tags=["documents"])
logger = logging.getLogger(__name__)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}

IMAGE_MAX_DIMENSION = 1024


def _is_rate_limit_error(error: Exception) -> bool:
    """Return True for Gemini quota / rate-limit errors."""
    error_text = str(error)
    return (
        "429" in error_text
        or "RESOURCE_EXHAUSTED" in error_text
        or "rate limit" in error_text.lower()
        or "quota" in error_text.lower()
    )


def _resize_image_for_vision(
    image_bytes: bytes,
    mime_type: str,
    max_dimension: int = IMAGE_MAX_DIMENSION,
) -> tuple[bytes, str]:
    """
    Resize an uploaded image to fit within max_dimension x max_dimension.

    The original uploaded image is still saved to disk. This resized copy is
    only used for vision extraction to reduce image token usage.
    The provider payload is normalized to JPEG for OpenAI-compatible APIs.
    """
    from PIL import Image, ImageOps

    output = BytesIO()

    with Image.open(BytesIO(image_bytes)) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)

        if image.mode in ("RGBA", "LA"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            alpha = image.getchannel("A")
            background.paste(image.convert("RGB"), mask=alpha)
            image = background
        elif image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        image.save(output, format="JPEG", optimize=True, quality=85)

    return output.getvalue(), "image/jpeg"


IMAGE_EXTRACTION_PROMPT = (
    "Extract all text from this image perfectly. Additionally, if there are any "
    "diagrams, charts, or visual elements, provide a highly detailed semantic "
    "description of their structure, relationships, and meaning so it can be "
    "effectively indexed for text-based vector search."
)

IMAGE_QUERY_PROMPT = (
    "Briefly describe this image and extract its core keywords to formulate a search query."
)


def _image_data_url(image_bytes: bytes, mime_type: str) -> str:
    """Build a base64 data URL for OpenAI-compatible vision APIs."""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def persist_uploaded_image(image_bytes: bytes, mime_type: str) -> tuple[Path, str]:
    """Persist original uploaded image bytes and return file path plus public URL."""
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image type. Allowed: JPEG, PNG, WEBP.",
        )
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    upload_dir = Path("static/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    extension = ALLOWED_IMAGE_TYPES[mime_type]
    unique_filename = f"{uuid.uuid4()}{extension}"
    file_path = upload_dir / unique_filename
    file_path.write_bytes(image_bytes)
    image_url = f"/static/uploads/{unique_filename}"

    return file_path, image_url


async def _extract_with_gemini(
    resized_bytes: bytes,
    mime_type: str,
    prompt: str,
) -> str:
    """Extract text from an image with Gemini Vision."""
    from google import genai
    from google.genai import types
    from app.config import get_settings

    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("Gemini API key is not configured")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = await asyncio.to_thread(
        client.models.generate_content,
        model=settings.GEMINI_VISION_MODEL,
        contents=[
            types.Part.from_bytes(data=resized_bytes, mime_type=mime_type),
            prompt,
        ],
    )
    return (response.text or "").strip()


async def _extract_with_groq(
    resized_bytes: bytes,
    mime_type: str,
    prompt: str,
) -> str:
    """Extract text from an image with Groq's vision chat API."""
    from groq import AsyncGroq
    from app.config import get_settings

    settings = get_settings()
    if not settings.GROQ_API_KEY:
        raise RuntimeError("Groq API key is not configured")

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    response = await client.chat.completions.create(
        model=settings.GROQ_VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": _image_data_url(resized_bytes, mime_type),
                        },
                    },
                ],
            }
        ],
        temperature=0.0,
        max_tokens=4096,
    )
    return (response.choices[0].message.content or "").strip()


async def _extract_text_from_image(image_bytes: bytes, mime_type: str) -> str:
    """Extract searchable multimodal text from an image using Gemini -> Groq."""
    return await _run_vision_chain(
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=IMAGE_EXTRACTION_PROMPT,
    )


async def generate_image_search_query(image_bytes: bytes, mime_type: str) -> str:
    """Generate a concise text query from an image for vector retrieval."""
    return await _run_vision_chain(
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=IMAGE_QUERY_PROMPT,
    )


async def answer_image_question_with_context(
    image_bytes: bytes,
    mime_type: str,
    question: str,
    context: str,
) -> str:
    """Answer using the uploaded image plus retrieved document context."""
    prompt = (
        "You are a multimodal RAG study assistant. Use the uploaded image and "
        "the retrieved document context together to answer the user's question. "
        "Ground document-specific facts in the retrieved context. Use the image "
        "for visual observations. If no relevant document context is available, "
        "clearly say that no matching knowledge-base context was found and only "
        "answer what can be determined from the image.\n\n"
        f"User message:\n{question}\n\n"
        f"Retrieved context chunks:\n{context}"
    )
    return await _run_vision_chain(
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=prompt,
    )


async def answer_image_question(
    image_bytes: bytes,
    mime_type: str,
    question: str,
) -> str:
    """Answer a user question directly from an uploaded image."""
    prompt = (
        "You are a strict visual study assistant. Answer the user's question "
        "using only the provided image. If the image does not contain enough "
        "information to answer, say so clearly.\n\n"
        f"User question: {question}"
    )
    return await _run_vision_chain(
        image_bytes=image_bytes,
        mime_type=mime_type,
        prompt=prompt,
    )


async def _run_vision_chain(image_bytes: bytes, mime_type: str, prompt: str) -> str:
    """Run a vision prompt using Gemini -> Groq."""
    resized_bytes, resized_mime_type = _resize_image_for_vision(
        image_bytes=image_bytes,
        mime_type=mime_type,
    )

    providers = [
        ("Gemini", _extract_with_gemini),
        ("Groq", _extract_with_groq),
    ]

    last_error: Exception | None = None
    for index, (provider_name, extractor) in enumerate(providers):
        try:
            return await extractor(
                resized_bytes,
                resized_mime_type,
                prompt,
            )
        except Exception as e:
            last_error = e
            if provider_name == "Groq":
                logger.error(f"Groq Vision failed: {str(e)}")

            if index == len(providers) - 1:
                break

            next_provider = providers[index + 1][0]
            if provider_name == "Gemini" and _is_rate_limit_error(e):
                print(
                    f"[WARN] Gemini Vision rate limit hit; falling back to "
                    f"{next_provider}. Error: {type(e).__name__}"
                )
            else:
                print(
                    f"[WARN] {provider_name} Vision failed; falling back to "
                    f"{next_provider}. Error: {type(e).__name__}"
                )

    if last_error:
        raise RuntimeError(f"All vision providers failed. Last error: {last_error}") from last_error
    raise RuntimeError("All vision providers failed without an error.")


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


async def process_image_document(
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
) -> ImageUploadResponse:
    """
    Upload an image, persist the original file, extract text with Gemini Vision,
    chunk/index the extracted text, and return both text and public image URL.
    """
    mime_type = file.content_type or ""
    if mime_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Unsupported image type. Allowed: JPEG, PNG, WEBP.",
        )

    image_bytes = await file.read()
    return await process_image_document_bytes(
        image_bytes=image_bytes,
        mime_type=mime_type,
        file_name=file.filename,
        db=db,
    )


async def process_image_document_bytes(
    image_bytes: bytes,
    mime_type: str,
    file_name: str | None,
    db: AsyncSession,
) -> ImageUploadResponse:
    """Persist an image, extract semantic text, chunk/embed it, and index it."""
    file_path, image_url = persist_uploaded_image(image_bytes, mime_type)
    unique_filename = file_path.name

    document = Document(
        id=str(uuid.uuid4()),
        user_id=DEFAULT_USER_ID,
        file_name=file_name or unique_filename,
        file_type="image",
        file_path=str(file_path),
        image_url=image_url,
        status="processing",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    try:
        from app.core.ingest.extractor import ExtractionResult, ExtractedPage
        from app.core.ingest.chunker import chunk_document
        from app.core.ingest.embedder import get_embedder

        extracted_text = await _extract_text_from_image(image_bytes, mime_type)
        extraction = ExtractionResult(
            pages=[
                ExtractedPage(
                    page_number=1,
                    content=extracted_text,
                    headings=[],
                )
            ],
            total_text=extracted_text,
            metadata={
                "file_type": "image",
                "image_url": image_url,
            },
        )
        chunks = chunk_document(extraction) if extracted_text else []

        chunk_records = []
        for i, chunk in enumerate(chunks):
            chunk_record = Chunk(
                document_id=document.id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=chunk.page_number,
                section_title=chunk.section_title,
                image_url=image_url,
                vector_id=None,
            )
            chunk_records.append(chunk_record)

        if chunk_records:
            db.add_all(chunk_records)
            await db.flush()

            embedder = get_embedder()
            texts = [chunk.content for chunk in chunk_records]
            embedding_result = await embedder.embed_texts(texts)

            try:
                from app.core.retrieval.vector_store import get_vector_store
                vector_store = get_vector_store()
                await vector_store.upsert_chunks(
                    chunks=chunk_records,
                    vectors=embedding_result.vectors,
                    document_id=document.id,
                )
            except Exception as e:
                print(f"Qdrant not available, skipping image vector storage: {e}")

            try:
                from app.core.retrieval.bm25_store import get_bm25_store
                bm25_store = get_bm25_store()
                bm25_store.add_chunks([
                    {
                        "chunk_id": chunk.id,
                        "document_id": chunk.document_id,
                        "content": chunk.content,
                        "page_number": chunk.page_number,
                        "section_title": chunk.section_title,
                        "image_url": chunk.image_url,
                        "chunk_index": chunk.chunk_index,
                    }
                    for chunk in chunk_records
                ])
            except Exception as e:
                print(f"BM25 indexing failed for image document: {e}")

        document.status = "ready"
        document.total_chunks = len(chunk_records)
        await db.commit()

        return ImageUploadResponse(
            document_id=document.id,
            file_name=document.file_name,
            image_url=image_url,
            extracted_text=extracted_text,
            total_chunks=len(chunk_records),
            status=document.status,
        )

    except HTTPException:
        document.status = "failed"
        await db.commit()
        raise
    except Exception as e:
        document.status = "failed"
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail=f"Unable to process image document: {e}",
        ) from e


@router.post("/documents/image", response_model=ImageUploadResponse)
async def upload_image_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload an image for long-term document storage."""
    return await process_image_document(file, db)


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
