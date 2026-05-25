"""
Agentic StudyMate — Vector Store (Qdrant)

Wrapper around the Qdrant client for storing and searching chunk embeddings.
Uses cosine similarity with 384-dimensional vectors (all-MiniLM-L6-v2).

Features:
- Auto-creates collection on first use
- Batch upsert with payload metadata
- Filtered search by document_ids
- Delete by document_id
"""

from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from app.config import get_settings


class VectorStore:
    """Qdrant vector store wrapper."""

    def __init__(self):
        self._settings = get_settings()
        self._client: QdrantClient | None = None
        self._collection_name = self._settings.QDRANT_COLLECTION

    def _get_client(self) -> QdrantClient:
        """Get or create Qdrant client (lazy init)."""
        if self._client is None:
            self._client = QdrantClient(
                host=self._settings.QDRANT_HOST,
                port=self._settings.QDRANT_PORT,
            )
            self._ensure_collection()
        return self._client

    def _ensure_collection(self):
        """Create the collection if it doesn't exist."""
        try:
            self._client.get_collection(self._collection_name)
        except (UnexpectedResponse, Exception):
            self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=models.VectorParams(
                    size=self._settings.EMBEDDING_DIMENSION,
                    distance=models.Distance.COSINE,
                ),
            )
            print(f"✓ Created Qdrant collection: {self._collection_name}")

    async def upsert_chunks(
        self,
        chunks: list,
        vectors: list[list[float]],
        document_id: str,
    ):
        """
        Batch upsert chunk vectors with metadata payloads.
        
        Args:
            chunks: List of Chunk ORM objects
            vectors: Corresponding embedding vectors
            document_id: Parent document ID for filtering
        """
        import asyncio

        def _upsert():
            client = self._get_client()
            points = []

            for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
                point_id = f"{document_id}_{i}"
                points.append(
                    models.PointStruct(
                        id=point_id,
                        vector=vector,
                        payload={
                            "document_id": document_id,
                            "chunk_id": chunk.id,
                            "chunk_index": chunk.chunk_index,
                            "content": chunk.content,
                            "page_number": chunk.page_number,
                            "section_title": chunk.section_title,
                            "image_url": getattr(chunk, "image_url", None),
                        },
                    )
                )

            # Batch upsert (Qdrant handles batching internally)
            client.upsert(
                collection_name=self._collection_name,
                points=points,
            )

        await asyncio.to_thread(_upsert)

    async def search(
        self,
        query_vector: list[float],
        document_ids: list[str] | None = None,
        top_k: int = 20,
    ) -> list[dict]:
        """
        Search for similar chunks.
        
        Args:
            query_vector: The query embedding
            document_ids: Optional filter to specific documents
            top_k: Number of results to return
            
        Returns:
            List of dicts with chunk data and scores
        """
        import asyncio

        def _search():
            client = self._get_client()

            # Build filter
            query_filter = None
            if document_ids:
                query_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchAny(any=document_ids),
                        )
                    ]
                )

            # qdrant-client >= 1.12 uses query_points() instead of search()
            results = client.query_points(
                collection_name=self._collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=self._settings.VECTOR_SCORE_THRESHOLD,
            )

            return [
                {
                    "chunk_id": hit.payload.get("chunk_id"),
                    "document_id": hit.payload.get("document_id"),
                    "content": hit.payload.get("content"),
                    "page_number": hit.payload.get("page_number"),
                    "section_title": hit.payload.get("section_title"),
                    "image_url": hit.payload.get("image_url"),
                    "chunk_index": hit.payload.get("chunk_index"),
                    "score": hit.score,
                    "source": "vector",
                }
                for hit in results.points
            ]

        return await asyncio.to_thread(_search)

    async def delete_by_document(self, document_id: str):
        """Delete all vectors belonging to a document."""
        import asyncio

        def _delete():
            client = self._get_client()
            client.delete(
                collection_name=self._collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="document_id",
                                match=models.MatchValue(value=document_id),
                            )
                        ]
                    )
                ),
            )

        await asyncio.to_thread(_delete)


# Singleton
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get or create the singleton vector store instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
