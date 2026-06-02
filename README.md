# Agentic StudyMate

## Overview

Agentic StudyMate is an Agentic Multimodal RAG study assistant. It lets users upload study materials, chat with their local knowledge base, ask image-based questions, and generate study tools from processed documents.

The system combines text RAG, vision RAG, hybrid retrieval, GraphRAG, reranking, SSE streaming, and citation verification. It is built for local development with FastAPI, React/Vite, SQLite, Qdrant, Neo4j, local CPU embeddings, and Groq-hosted LLM inference.

## Key Features

- PDF, DOCX, and TXT upload through `POST /api/upload`.
- PNG and JPEG image document upload through `POST /api/documents/image`.
- SHA-256 file hash duplicate detection for text document uploads.
- `409 Conflict` responses for duplicate text documents.
- Safe frontend duplicate-file handling in `Upload.tsx` and `Library.tsx`, displaying `File already exists in the library!` instead of crashing.
- Text extraction for PDF, DOCX, and TXT files.
- Vision extraction for uploaded image documents.
- Structure-aware document chunking with page and section metadata.
- SQLite metadata storage for documents, chunks, chat sessions, messages, image URLs, and file hashes.
- Qdrant vector storage with 384-dimensional cosine vectors.
- BM25 keyword retrieval with an in-memory index rebuilt on startup.
- Hybrid retrieval with Qdrant vector search, BM25 search, and RRF fusion.
- CPU cross-encoder reranking with `cross-encoder/ms-marco-MiniLM-L-6-v2`.
- Neo4j Knowledge Graph / GraphRAG ingestion and retrieval when configured.
- Entity-relation triplet extraction from document chunks.
- Graph relationships linked back to SQLite chunk IDs for citation mapping.
- SSE streaming chat with status, chunk, citations, done, session, and error events.
- Chat sessions with persistent message history.
- Deterministic citation verification for text RAG answers.
- Multimodal image question answering.
- Two-pass image retrieval flow for image chat.
- Unified Groq model strategy using `meta-llama/llama-4-scout-17b-16e-instruct` for both `TEXT_MODEL` and `VISION_MODEL`.
- Study tools for quizzes, flashcards, and summaries.

## Architecture

Frontend:

- React
- Vite
- TypeScript
- Tailwind CSS v4
- Runs on port `5173`
- Proxies `/api` and `/static` to the FastAPI backend

Backend:

- Python
- FastAPI
- Async/await routes and background tasks
- SQLAlchemy async sessions
- SQLite with `aiosqlite`
- Static file serving for `static/uploads`

Metadata DB:

- SQLite stores users, documents, chunks, chat sessions, messages, image URLs, and file hashes.

Vector DB:

- Qdrant on port `6333`
- Collection: `studymate_chunks`
- 384-dimensional cosine vectors

Graph DB:

- Neo4j on port `7687`
- Stores Knowledge Graph relationships for GraphRAG.

Embedding model:

- `sentence-transformers/all-MiniLM-L6-v2`
- 384 dimensions
- Runs locally on CPU

LLM:

- Groq API
- `meta-llama/llama-4-scout-17b-16e-instruct`
- Used for both text and vision via `TEXT_MODEL` and `VISION_MODEL`

Retrieval:

- Qdrant vector search
- BM25 keyword search
- Neo4j graph search
- RRF fusion for vector/BM25 merge
- CPU cross-encoder reranking

## System Flow

### Document Ingestion Flow

```text
User uploads document
-> validate file type
-> read bytes
-> compute SHA-256 file hash
-> reject duplicate with 409 Conflict
-> save file
-> create document record in SQLite
-> extract text
-> chunk text
-> store chunks in SQLite
-> extract graph triplets
-> store triplets in Neo4j when configured
-> generate embeddings with all-MiniLM-L6-v2
-> store vectors in Qdrant
-> add chunks to BM25
-> mark document as ready
```

### Chat Flow

```text
User sends text question
-> query analysis
-> query rewriting
-> query planning if needed
-> Qdrant vector retrieval
-> BM25 keyword retrieval
-> Neo4j graph retrieval
-> RRF fusion for vector/BM25 results
-> cross-encoder reranking
-> context evaluation
-> retry retrieval when context is insufficient
-> answer generation
-> citation verification
-> SSE response
```

### Multimodal Image Chat Flow

```text
User sends image + question
-> vision model extracts 3-5 retrieval keywords
-> search Qdrant/BM25 using extracted keywords
-> search Neo4j graph triplets using extracted keywords
-> combine retrieved vector/BM25/graph context
-> send original image + original question + retrieved context to vision model
-> generate final answer
-> return answer with citations
```

Text-only chat skips the image keyword extraction pass and uses the normal agentic text RAG pipeline.

## Knowledge Graph / GraphRAG

The ingestion pipeline extracts entity-relation triplets from chunks with this shape:

```json
{
  "source": "Apache Spark",
  "relation": "MANAGES",
  "target": "Worker Node"
}
```

Neo4j stores these as:

```cypher
(:Entity)-[:RELATION {chunk_id: "..."}]->(:Entity)
```

Each relationship keeps the source SQLite `chunk_id`. During graph retrieval, Neo4j returns matching relationships and their chunk IDs, then the backend maps those chunk IDs back to original chunks and document filenames for citations.

Neo4j is configured through `.env`:

- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`

If Neo4j is not configured, graph ingestion is logged/skipped without blocking the rest of document ingestion.

## Tech Stack

Backend packages include:

- `fastapi`
- `uvicorn`
- `python-multipart`
- `sqlalchemy[asyncio]`
- `aiosqlite`
- `pymupdf`
- `pymupdf4llm`
- `python-docx`
- `pillow`
- `sentence-transformers`
- CPU `torch`
- `qdrant-client`
- `neo4j`
- `rank-bm25`
- `groq`
- `google-genai`
- `openai`
- `anthropic`
- `pydantic-settings`
- `python-dotenv`

Frontend packages include:

- `react`
- `react-dom`
- `react-router-dom`
- `vite`
- `typescript`
- `tailwindcss`
- `@tailwindcss/vite`
- `axios`
- `lucide-react`
- `react-dropzone`
- `react-markdown`
- `remark-gfm`

The current code still includes Gemini, OpenAI, and Anthropic client support, but the project architecture standardizes new text and vision work on Groq Scout.

## Project Structure

```text
Agentic_StudyMate/
|-- .cursorrules
|-- PROJECT_INSTRUCTIONS.md
|-- README.md
|-- structure.txt
|-- backend/
|   |-- requirements.txt
|   |-- qdrant_storage/
|   `-- app/
|       |-- main.py
|       |-- config.py
|       |-- api/
|       |   `-- routes/
|       |       |-- upload.py
|       |       |-- documents.py
|       |       |-- chat.py
|       |       `-- study_tools.py
|       |-- db/
|       |   |-- session.py
|       |   `-- init_db.py
|       |-- models/
|       |   |-- db_models.py
|       |   `-- schemas.py
|       `-- core/
|           |-- reranker.py
|           |-- agent/
|           |   |-- llm_client.py
|           |   |-- controller.py
|           |   |-- query_analyzer.py
|           |   |-- query_rewriter.py
|           |   |-- query_planner.py
|           |   |-- context_evaluator.py
|           |   |-- answer_generator.py
|           |   |-- citation_verifier.py
|           |   `-- map_reduce.py
|           |-- ingest/
|           |   |-- extractor.py
|           |   |-- chunker.py
|           |   |-- embedder.py
|           |   `-- graph_extractor.py
|           |-- retrieval/
|           |   |-- vector_store.py
|           |   |-- bm25_store.py
|           |   `-- hybrid.py
|           `-- db/
|               `-- neo4j_client.py
`-- frontend/
    |-- package.json
    |-- vite.config.ts
    |-- index.html
    |-- public/
    |   |-- favicon.svg
    |   `-- icons.svg
    `-- src/
        |-- App.tsx
        |-- main.tsx
        |-- index.css
        |-- lib/
        |   `-- api.ts
        |-- stores/
        |   `-- studyToolsStore.tsx
        |-- pages/
        |   |-- Dashboard.tsx
        |   |-- Upload.tsx
        |   |-- Chat.tsx
        |   |-- Library.tsx
        |   `-- StudyTools.tsx
        |-- components/
        |   |-- Layout.tsx
        |   |-- ChatMessage.tsx
        |   |-- DocumentCard.tsx
        |   |-- QuizWidget.tsx
        |   `-- FlashcardViewer.tsx
        `-- assets/
            |-- hero.png
            `-- vite.svg
```

## Setup Instructions

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend runs at `http://localhost:8000`.

### Qdrant

```powershell
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

### Neo4j

```powershell
docker run --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/your_password neo4j:latest
```

Set `NEO4J_PASSWORD=your_password` in `backend/.env`.

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173`.

## Environment Variables

Create `backend/.env` with safe local values. Use placeholders only for secrets.

```env
DATABASE_URL=sqlite+aiosqlite:///./studymate.db

GROQ_API_KEY=your_groq_api_key_here
TEXT_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
VISION_MODEL=meta-llama/llama-4-scout-17b-16e-instruct

QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=studymate_chunks

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password_here

EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

CORS_ORIGINS=["http://localhost:5173","http://localhost:3000"]
UPLOAD_DIR=uploads

GEMINI_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
```

`GEMINI_API_KEY`, `OPENAI_API_KEY`, and `ANTHROPIC_API_KEY` are still present in the current settings/client code, but the intended unified model path is Groq Scout.

## API Endpoints

### Health

- `GET /api/health`

### Uploads And Documents

- `POST /api/upload`
- `GET /api/documents`
- `POST /api/documents/image`
- `GET /api/documents/{document_id}`
- `DELETE /api/documents/{document_id}`

### Chat

- `POST /api/chat`
- `GET /api/chat/sessions`
- `GET /api/chat/sessions/{session_id}`
- `DELETE /api/chat/sessions/{session_id}`

### Study Tools

- `POST /api/study-tools/quiz`
- `POST /api/study-tools/flashcards`
- `POST /api/study-tools/summary`

## Reset / Cleanup Instructions

To fully reset local development data:

1. Stop the backend, frontend, Qdrant, and Neo4j processes.
2. Delete the SQLite database file, usually `backend/studymate.db`.
3. Delete uploaded document files from `backend/uploads` if present.
4. Delete uploaded static image files from `backend/static/uploads` if present.
5. Remove Qdrant local storage:

```powershell
docker volume rm qdrant_storage
```

If you used the checked-out `backend/qdrant_storage` folder instead of a Docker volume, delete that folder only when you intentionally want to clear all local vectors.

6. Reset Neo4j data if a full graph reset is required:

```powershell
docker rm -f neo4j
docker volume prune
```

Only prune Docker volumes when you are sure no other project data is stored there.

## Current Development Status

Implemented:

- FastAPI backend with async SQLAlchemy and SQLite.
- React/Vite frontend.
- PDF, DOCX, TXT text document upload.
- Text-document SHA-256 duplicate detection and `409 Conflict`.
- Frontend duplicate upload handling.
- Image document upload and image chat attachment support.
- Text extraction, chunking, SQLite chunk storage, local embeddings, Qdrant upsert, BM25 indexing.
- Hybrid vector/BM25 retrieval with RRF.
- CPU cross-encoder reranking for text RAG.
- Neo4j triplet ingestion/search when configured.
- Agentic text chat pipeline.
- SSE streaming chat.
- Chat sessions and message history.
- Citation verification for text RAG.
- Two-pass multimodal image chat.
- Quiz, flashcard, and summary generation.

Partially implemented:

- Neo4j is optional at runtime; graph ingestion logs/skips when credentials are missing.
- Qdrant failures are tolerated during ingestion/search, with BM25 available as a fallback.
- Image document uploads are processed and indexed, but the SHA-256 duplicate shield is implemented on the text-document upload route.
- Legacy LLM fallback clients still exist in code, although Groq Scout is the project-standard text/vision model path.

Planned / TODO:

- Authentication and multi-user accounts.
- Production deployment packaging.
- A formal migration path from SQLite if needed.
- Dedicated automated test coverage for duplicate upload, multimodal chat, and GraphRAG flows.

## Notes For Contributors

- Do not commit `.env`.
- Do not commit API keys or credentials.
- Keep embedding and reranking models CPU-friendly.
- Keep Qdrant and Neo4j configurable through environment variables.
- Keep duplicate upload handling safe; duplicates should return `409 Conflict` and must not crash the frontend.
- Keep `TEXT_MODEL` and `VISION_MODEL` aligned with `meta-llama/llama-4-scout-17b-16e-instruct` unless the project architecture is explicitly changed.
- Keep citation metadata intact in SQLite, Qdrant payloads, and graph-backed retrieval.
- Keep README content synchronized with source code when changing endpoints or architecture.

## License

TBD
