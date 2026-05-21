"""
Agentic StudyMate — FastAPI Application Entry Point

The main app with:
- CORS middleware for frontend access
- Lifespan events (DB init on startup)
- All API routers mounted
- Health check endpoint
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    
    Startup:
    - Initialize database (create tables, seed default user)
    - Log configuration summary
    
    Shutdown:
    - Clean up resources
    """
    settings = get_settings()
    print("=" * 60)
    print("🎓 Agentic StudyMate — Starting up")
    print("=" * 60)

    # Initialize database
    await init_db()
    print(f"✓ Database ready: {settings.DATABASE_URL}")

    # Initialize BM25 search index from existing chunks
    from app.core.retrieval.bm25_store import get_bm25_store
    bm25_store = get_bm25_store()
    await bm25_store.initialize_from_db()

    # Log LLM provider
    llm_provider = settings.get_available_llm()
    if llm_provider:
        print(f"✓ LLM provider: {llm_provider}")
    else:
        print("⚠ No LLM API key configured — chat will not work")

    print(f"✓ Embedding model: {settings.EMBEDDING_MODEL}")
    print(f"✓ Vector DB: Qdrant @ {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    print(f"✓ CORS origins: {settings.CORS_ORIGINS}")
    print("=" * 60)
    print("🚀 Ready to accept requests!")
    print("=" * 60)

    yield  # App is running

    # Shutdown
    print("👋 Agentic StudyMate shutting down...")


# Create the FastAPI app
app = FastAPI(
    title="Agentic StudyMate",
    description="An AI-powered study assistant with RAG, hybrid retrieval, and agentic query processing.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Mount Routers ────────────────────────────────────────────────────────────

from app.api.routes.upload import router as upload_router
from app.api.routes.documents import router as documents_router
from app.api.routes.chat import router as chat_router
from app.api.routes.study_tools import router as study_tools_router

app.include_router(upload_router)
app.include_router(documents_router)
app.include_router(chat_router)
app.include_router(study_tools_router)


# ─── Health Check ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    settings = get_settings()
    return {
        "status": "healthy",
        "version": "0.1.0",
        "llm_provider": settings.get_available_llm(),
        "database": "connected",
    }
