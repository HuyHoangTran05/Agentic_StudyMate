# 🎓 Agentic StudyMate — Complete Project Instructions

> **Purpose of this file**: This document captures the full project blueprint, all decisions made,
> what has been built so far, and what remains. Use it to continue development after reinstalling
> Antigravity or any AI coding assistant.

---

## 1. Project Overview

**Agentic StudyMate** is a full-stack RAG-powered study assistant featuring:
- Upload documents (PDF, DOCX, TXT)
- Chat with your documents using an **agentic pipeline** (not basic RAG)
- Generate study tools: quizzes, flashcards, summaries
- Hybrid retrieval: semantic vectors + BM25 keyword search + cross-encoder reranking
- Citation verification: every answer references the source document and page

### What makes this special (vs basic RAG):
1. **Agentic loop**: Classify → Rewrite → Plan → Retrieve → Evaluate → Generate → Verify citations
2. **Hybrid retrieval**: Vector search (Qdrant) + BM25 keyword search, merged with RRF fusion
3. **Cross-encoder reranking**: Second-stage precision filter
4. **Query planning**: Complex questions decomposed into sub-questions
5. **Context evaluation with retry**: If retrieved context is insufficient, rewrites the query and retries
6. **Citation verification**: Verifies every citation maps to actual content

---

## 2. Technical Decisions (Already Decided)

| Decision | Choice | Reason |
|----------|--------|--------|
| **LLM Provider** | All three supported, priority: **Gemini → OpenAI → Anthropic** | Flexibility; Gemini has free tier |
| **Vector Database** | **Qdrant** (Docker) | Production-ready, supports filtering |
| **Frontend Framework** | React + Vite + TypeScript + **TailwindCSS v4** | User requested Tailwind |
| **Database** | **SQLite** first, swappable to PostgreSQL later | Zero setup for dev |
| **Authentication** | Skipped for MVP, single default user | Simplicity |
| **GPU** | **No CUDA GPU** — all ML runs on CPU | User constraint |
| **Embedding Model** | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, CPU) | Lightweight, fast on CPU |
| **Reranker Model** | `cross-encoder/ms-marco-MiniLM-L-6-v2` (CPU) | Trained on MS MARCO, great for QA |
| **Deployment** | Local only for now, Docker Compose later | MVP focus |
| **Approach** | Step-by-step, phase by phase | User wants to understand each step |

---

## 3. Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    FRONTEND (React + Vite + Tailwind v4)         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│  │Dashboard │ │ Upload   │ │  Chat    │ │ Library  │ │ Study  ││
│  │          │ │          │ │ (SSE)    │ │          │ │ Tools  ││
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └────────┘│
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTP / SSE
┌────────────────────────────▼─────────────────────────────────────┐
│                    BACKEND (FastAPI + Python)                     │
│                                                                   │
│  ┌─ API Routes ──────────────────────────────────────────────┐   │
│  │ POST /api/upload        GET /api/documents                │   │
│  │ POST /api/chat          GET /api/chat/sessions            │   │
│  │ POST /api/study-tools/* DELETE /api/documents/{id}        │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─ Ingestion Pipeline ──────────────────────────────────────┐   │
│  │ Extractor (PyMuPDF/docx/txt) → Chunker → Embedder → Store│   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─ Agentic Pipeline ───────────────────────────────────────┐   │
│  │ Query Analyzer → Query Rewriter → Query Planner          │   │
│  │ → Hybrid Retrieve → Rerank → Context Evaluator (retry?)  │   │
│  │ → Answer Generator → Citation Verifier                    │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─ Retrieval Layer ────────────────────────────────────────┐   │
│  │ Vector Search (Qdrant) ─┐                                 │   │
│  │                          ├→ RRF Fusion → Cross-Encoder    │   │
│  │ BM25 Keyword Search ────┘                 Reranker        │   │
│  └───────────────────────────────────────────────────────────┘   │
└──────────────────────┬─────────────────────┬─────────────────────┘
                       │                     │
              ┌────────▼──────┐    ┌─────────▼─────────┐
              │   SQLite DB   │    │   Qdrant (Docker)  │
              │ (metadata,    │    │   (vector embeddings│
              │  messages)    │    │    384-dim cosine)  │
              └───────────────┘    └────────────────────┘
```

---

## 4. Complete Folder Structure (Current State)

```
d:\Agentic_StudyMate\
├── PROJECT_INSTRUCTIONS.md          ← THIS FILE
│
├── backend/
│   ├── .env                         # Environment variables (API keys, DB URL, model names)
│   ├── .gitignore                   # Python gitignore
│   ├── requirements.txt             # All Python dependencies
│   │
│   └── app/
│       ├── __init__.py
│       ├── main.py                  # FastAPI entry point, CORS, lifespan, all routers
│       ├── config.py                # Pydantic Settings loaded from .env
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   └── routes/
│       │       ├── __init__.py
│       │       ├── upload.py        # POST /api/upload + background ingestion pipeline
│       │       ├── documents.py     # GET/DELETE /api/documents
│       │       ├── chat.py          # ✅ POST /api/chat (SSE streaming), GET/DELETE sessions
│       │       └── study_tools.py   # ✅ POST quiz/flashcards/summary endpoints
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── db_models.py         # SQLAlchemy ORM: User, Document, Chunk, ChatSession, Message
│       │   └── schemas.py           # Pydantic schemas: ChatRequest, ChatResponse, Citation, etc.
│       │
│       ├── db/
│       │   ├── __init__.py
│       │   ├── session.py           # Async SQLAlchemy engine + session factory (SQLite)
│       │   └── init_db.py           # Create tables + seed default user on startup
│       │
│       └── core/
│           ├── __init__.py
│           ├── reranker.py          # Cross-encoder reranker (ms-marco-MiniLM, CPU)
│           │
│           ├── ingest/
│           │   ├── __init__.py
│           │   ├── extractor.py     # PDF (pymupdf4llm), DOCX (python-docx), TXT extraction
│           │   ├── chunker.py       # Structure-aware recursive splitter (~512 tokens, 64 overlap)
│           │   └── embedder.py      # all-MiniLM-L6-v2 embeddings (CPU, lazy-loaded singleton)
│           │
│           ├── retrieval/
│           │   ├── __init__.py
│           │   ├── vector_store.py  # Qdrant client wrapper (upsert, search, delete)
│           │   ├── bm25_store.py    # In-memory BM25 index (rank-bm25)
│           │   └── hybrid.py        # RRF fusion merging vector + BM25 results
│           │
│           └── agent/               # ✅ Agentic pipeline (Phase 3)
│               ├── __init__.py
│               ├── llm_client.py    # Unified LLM client (Gemini→OpenAI→Anthropic fallback)
│               ├── controller.py    # Main agentic loop orchestrator (sync + SSE streaming)
│               ├── query_analyzer.py    # Question classification (JSON structured output)
│               ├── query_rewriter.py    # Search query optimization + feedback rewriting
│               ├── query_planner.py     # Sub-question decomposition for complex queries
│               ├── context_evaluator.py # Context sufficiency assessment
│               ├── answer_generator.py  # Citation-aware answer gen (sync + streaming)
│               └── citation_verifier.py # Deterministic citation verification
│
└── frontend/                        # ✅ React + Vite + TypeScript + Tailwind v4 (Phase 4)
    ├── index.html                   # SEO meta, Inter font from Google Fonts
    ├── vite.config.ts               # Tailwind v4 plugin + API proxy to backend
    ├── package.json
    └── src/
        ├── main.tsx                 # Entry point with BrowserRouter
        ├── App.tsx                  # Client-side routing
        ├── index.css                # Design system: glassmorphism, gradients, animations
        ├── lib/
        │   └── api.ts               # Typed API client with SSE stream parser
        ├── components/
        │   ├── Layout.tsx            # Sidebar nav + mobile hamburger
        │   ├── ChatMessage.tsx       # Markdown + citations + copy button
        │   ├── DocumentCard.tsx      # File card with status badge
        │   ├── FlashcardViewer.tsx   # 3D flip animation
        │   └── QuizWidget.tsx        # Interactive MCQ + scoring
        └── pages/
            ├── Dashboard.tsx         # Stats, quick actions, recent chats
            ├── Upload.tsx            # Drag-and-drop with react-dropzone
            ├── Chat.tsx              # SSE streaming chat + session sidebar
            ├── Library.tsx           # Document grid with search
            └── StudyTools.tsx        # Quiz/flashcard/summary generator
```

---

## 5. What Has Been Completed

### ✅ Phase 1: Backend Foundation + Document Ingestion
Everything works end-to-end: upload a file → extract text → chunk → embed → store in Qdrant + SQLite.

| File | Purpose |
|------|---------|
| `backend/requirements.txt` | All Python deps: FastAPI, SQLAlchemy, PyMuPDF, sentence-transformers (CPU torch), Qdrant, BM25, 3 LLM SDKs |
| `backend/.env` | Config template with SQLite URL, LLM keys (empty), model names, Qdrant host, chunk settings |
| `backend/app/config.py` | Pydantic `Settings` class with `get_available_llm()` priority method |
| `backend/app/main.py` | FastAPI app with lifespan (DB init + BM25 init on startup), CORS, health check |
| `backend/app/db/session.py` | Async SQLAlchemy engine with `get_db()` FastAPI dependency |
| `backend/app/db/init_db.py` | Creates all tables, seeds default user `DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"` |
| `backend/app/models/db_models.py` | ORM models: `User`, `Document`, `Chunk`, `ChatSession`, `Message` with UUID string PKs |
| `backend/app/models/schemas.py` | Pydantic schemas for all endpoints including chat, study tools, citations |
| `backend/app/api/routes/upload.py` | `POST /api/upload` — validates file, saves to disk, runs ingestion in `BackgroundTasks` |
| `backend/app/api/routes/documents.py` | `GET /api/documents`, `GET /api/documents/{id}`, `DELETE /api/documents/{id}` with cascade cleanup |
| `backend/app/core/ingest/extractor.py` | PDF→Markdown (pymupdf4llm), DOCX→Markdown (heading-aware), TXT (multi-encoding) |
| `backend/app/core/ingest/chunker.py` | Recursive splitter: headings → paragraphs → sentences → words. ~512 tokens, 64 overlap. Preserves page numbers and section titles |
| `backend/app/core/ingest/embedder.py` | Lazy-loaded `all-MiniLM-L6-v2` on CPU, batch encode, `asyncio.to_thread` for non-blocking |

### ✅ Phase 2: Hybrid Retrieval + Reranking
The retrieval layer is complete: Query → Vector+BM25 → RRF Merge → Cross-encoder Rerank → Top 5.

| File | Purpose |
|------|---------|
| `backend/app/core/retrieval/vector_store.py` | Qdrant wrapper: auto-create collection (384-dim, cosine), upsert with payloads, filtered search, delete by document |
| `backend/app/core/retrieval/bm25_store.py` | In-memory BM25 index using `rank-bm25`. Rebuilds from DB on startup. Incremental add/remove per document |
| `backend/app/core/retrieval/hybrid.py` | `HybridRetriever` — runs vector + BM25 in parallel, merges with RRF (k=60), deduplicates. Graceful when Qdrant is offline |
| `backend/app/core/reranker.py` | Lazy-loaded `ms-marco-MiniLM-L-6-v2` cross-encoder. Scores query-doc pairs, returns top N (default 5) |

**Integration points already wired:**
- `main.py` startup → initializes BM25 from DB
- `upload.py` ingestion → adds new chunks to BM25 index after embedding
- `documents.py` delete → removes chunks from BM25 index + Qdrant

---

### ✅ Phase 3: Agentic Pipeline + Chat API
The agentic brain is complete — 7-step pipeline with LLM-generated session titles and graceful error handling.

| File | Purpose |
|------|---------|
| `backend/app/core/agent/llm_client.py` | Unified async LLM client (Gemini→OpenAI→Anthropic fallback). Supports JSON structured output + streaming. |
| `backend/app/core/agent/query_analyzer.py` | Classifies questions by type, complexity, and planning needs via structured JSON output |
| `backend/app/core/agent/query_rewriter.py` | Rewrites conversational questions into retrieval-optimized queries, with feedback-based retry |
| `backend/app/core/agent/query_planner.py` | Decomposes complex questions into 2-4 sub-questions |
| `backend/app/core/agent/context_evaluator.py` | Assesses chunk sufficiency, returns gap descriptions for retry loop |
| `backend/app/core/agent/answer_generator.py` | Citation-aware answer generation (sync + streaming). Uses `[filename, page N]` format |
| `backend/app/core/agent/citation_verifier.py` | Deterministic citation verification — regex parse + chunk cross-reference |
| `backend/app/core/agent/controller.py` | Main orchestrator: analyze→rewrite→plan→retrieve+rerank→evaluate(retry)→generate→verify. SSE streaming with status events |
| `backend/app/api/routes/chat.py` | `POST /api/chat` (SSE streaming), `GET/DELETE /api/chat/sessions` |
| `backend/app/api/routes/study_tools.py` | `POST /api/study-tools/quiz\|flashcards\|summary` with graceful error handling |

**Key design decisions:**
- LLM errors (rate limits, quota) return friendly user messages instead of raw errors
- Session titles are LLM-generated from the first question
- All agent modules have fallback behavior (defaults on failure) to avoid cascading crashes
- SSE events: `status` (pipeline stages), `chunk` (answer text), `citations` (JSON), `done` (metadata)

### ✅ Phase 4: React Frontend
Premium dark-mode UI with glassmorphism, gradient accents, and micro-animations.

| File | Purpose |
|------|---------|
| `frontend/vite.config.ts` | Tailwind v4 plugin + API proxy to localhost:8000 |
| `frontend/src/index.css` | Full design system: theme tokens, glass panels, gradients, animations, markdown styles |
| `frontend/src/lib/api.ts` | Typed API client with SSE stream parser for chat |
| `frontend/src/components/Layout.tsx` | Sidebar nav with active indicators, mobile hamburger |
| `frontend/src/components/ChatMessage.tsx` | Markdown rendering, citation badges, copy button, typing indicator |
| `frontend/src/components/DocumentCard.tsx` | File card with type icon, status badge, hover-reveal delete |
| `frontend/src/components/FlashcardViewer.tsx` | 3D CSS flip animation, progress dots, navigation |
| `frontend/src/components/QuizWidget.tsx` | Interactive MCQ, answer reveal, score tracking, completion screen |
| `frontend/src/pages/Dashboard.tsx` | Gradient hero, stat cards, quick actions, recent chats |
| `frontend/src/pages/Upload.tsx` | react-dropzone with drag states, upload results |
| `frontend/src/pages/Chat.tsx` | SSE streaming chat, session sidebar, document filter, status pills |
| `frontend/src/pages/Library.tsx` | Document grid with search, delete confirmation |
| `frontend/src/pages/StudyTools.tsx` | Tool tabs (quiz/flashcards/summary), item slider, interactive results |

---

## 6. What Remains To Be Built

All core phases are complete. Potential future enhancements:
- **Phase 5**: Authentication (JWT, user accounts)
- **Phase 6**: Docker Compose deployment
- **Phase 7**: PostgreSQL migration
- **Phase 8**: Conversation memory (multi-turn context)

---

## 7. Key Implementation Details

### Chunking Strategy
- **Recursive split order**: headings → paragraphs → sentences → words
- **Token estimation**: `len(text) // 4` (rough ~4 chars/token for English)
- **Default**: 512 tokens per chunk, 64 token overlap
- **Tables** treated as indivisible units
- Each chunk stores: `page_number`, `section_title`, `chunk_index`

### Retrieval Pipeline
```
Query → Embed (MiniLM-L6-v2, 384D)
     ├→ Qdrant Vector Search (cosine, top 20)
     └→ BM25 Keyword Search (top 20)
              ↓
         RRF Merge (k=60) → Deduplicate
              ↓
     Cross-Encoder Rerank (ms-marco, top 5)
              ↓
         Final chunks for LLM
```

### RRF Fusion Formula
```
RRF_score(chunk) = Σ  1 / (k + rank_i + 1)   where k=60
```

### Citation System Prompt (for answer_generator)
```
You must cite every claim using this format: [filename, page N].
If you cannot find supporting text in the provided context, respond:
"I could not find enough information in the uploaded documents."
```

### Default User (no auth MVP)
- `DEFAULT_USER_ID = "00000000-0000-0000-0000-000000000001"`
- `DEFAULT_USER_EMAIL = "student@studymate.local"`
- Auto-created on startup in `init_db.py`

### All Models Run on CPU
- Embedding: `all-MiniLM-L6-v2` (~80MB, 384-dim) — loaded lazily
- Reranker: `ms-marco-MiniLM-L-6-v2` (~80MB) — loaded lazily
- Both use `asyncio.to_thread()` to avoid blocking the event loop

---

## 8. How to Run (Setup from Scratch)

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker Desktop (for Qdrant)

### Backend Setup
```bash
cd d:\Agentic_StudyMate\backend

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate     # Windows

# Install dependencies (CPU-only PyTorch)
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# Configure .env — add at least one LLM API key:
# GEMINI_API_KEY=your-key-here

# Start Qdrant (in a separate terminal)
docker run -p 6333:6333 qdrant/qdrant

# Run the backend
uvicorn app.main:app --reload
```

The server starts at `http://localhost:8000`. Check `http://localhost:8000/api/health`.

### Frontend Setup (Phase 4, not yet built)
```bash
cd d:\Agentic_StudyMate\frontend
npm install
npm run dev
```

Frontend will run at `http://localhost:5173`.

---

## 9. API Endpoints Summary

### Currently Working (Phase 1-2)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/upload` | Upload PDF/DOCX/TXT → triggers ingestion |
| GET | `/api/documents` | List all documents |
| GET | `/api/documents/{id}` | Get document details |
| DELETE | `/api/documents/{id}` | Delete document + chunks + vectors |

### To Be Built (Phase 3)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat` | Main agentic chat (streaming) |
| GET | `/api/chat/sessions` | List chat sessions |
| GET | `/api/chat/sessions/{id}` | Get message history |
| POST | `/api/study-tools/quiz` | Generate MCQs |
| POST | `/api/study-tools/flashcards` | Generate flashcards |
| POST | `/api/study-tools/summary` | Generate summary |

---

## 10. Database Schema (SQLite)

```sql
-- Auto-created on startup by SQLAlchemy
-- 5 tables: users, documents, chunks, chat_sessions, messages

users (id TEXT PK, email TEXT UNIQUE, created_at TIMESTAMP)
documents (id TEXT PK, user_id FK, file_name, file_type, file_path, upload_time, total_chunks, status)
chunks (id TEXT PK, document_id FK, chunk_index INT, content TEXT, page_number INT, section_title TEXT, vector_id TEXT)
chat_sessions (id TEXT PK, user_id FK, title TEXT, created_at TIMESTAMP)
messages (id TEXT PK, session_id FK, role TEXT, content TEXT, citations JSON, created_at TIMESTAMP)
```

---

## 11. Prompt to Continue Development

When you reinstall Antigravity, paste this prompt to continue:

```
I'm building Agentic StudyMate — a full-stack RAG study assistant. 
Read the file d:\Agentic_StudyMate\PROJECT_INSTRUCTIONS.md for the complete 
project blueprint, all decisions made, and what has been completed.

Phases 1-4 are ALL DONE (backend + agentic pipeline + frontend).
Continue with improvements or next phases as needed.
```

---

## 12. Dependencies Reference

### Python (backend/requirements.txt)
```
fastapi, uvicorn, python-multipart          # Web framework
sqlalchemy[asyncio], aiosqlite              # Database (SQLite async)
pymupdf, pymupdf4llm, python-docx          # Document parsing
sentence-transformers, torch (CPU)          # Embeddings + Reranker
qdrant-client                               # Vector database
rank-bm25                                   # BM25 keyword search
google-genai, openai, anthropic             # LLM providers
pydantic-settings, python-dotenv            # Configuration
```

### Node.js (frontend — to be installed in Phase 4)
```
react, react-router-dom                     # UI framework
tailwindcss, @tailwindcss/vite              # Styling (v4)
axios                                        # HTTP client
react-markdown                              # Render markdown answers
react-dropzone                              # File upload UI
```
