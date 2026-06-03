# Agentic StudyMate

Agentic StudyMate is an agentic multimodal RAG study assistant for local development and demos. It lets you upload documents and images, chat with cited answers, generate study tools, inspect service health, explore Neo4j Knowledge Graph triplets, and rebuild graph relationships from existing chunks when GraphRAG data is missing or stale.

## What It Does

- Upload PDF, DOCX, TXT, PNG, JPG, JPEG, and WEBP sources.
- Detect duplicate text-document uploads with SHA-256 hashes and return `409 Conflict`.
- Extract text and image semantics, chunk content, and store metadata in SQLite.
- Store embeddings in Qdrant for vector retrieval.
- Maintain an in-memory BM25 index for keyword retrieval.
- Extract entity-relation triplets into Neo4j for GraphRAG.
- Chat with streaming answers, markdown rendering, citations, and source metadata.
- Ask image questions that use vision understanding plus retrieved document and graph context.
- Generate quizzes, flashcards, and summaries from ready documents.
- Monitor API, database, Qdrant, Neo4j, LLM, embedding, and reranker status.
- Inspect Knowledge Graph triplets and rebuild a document graph without re-uploading.

## Architecture

Frontend:

- React
- Vite
- TypeScript
- Tailwind CSS v4
- Lucide icons
- Runs at `http://localhost:5173`
- Proxies `/api` and `/static` to the FastAPI backend

Backend:

- FastAPI async routes
- SQLAlchemy async sessions
- Background tasks for document processing and graph rebuilds
- SQLite metadata database
- Static uploaded-file serving from `backend/static`

Retrieval and AI:

- Qdrant vector database, default collection `studymate_chunks`
- Neo4j graph database for entity-relation triplets
- Local CPU embeddings with `sentence-transformers/all-MiniLM-L6-v2`
- Cross-encoder reranking with `cross-encoder/ms-marco-MiniLM-L-6-v2`
- BM25 keyword retrieval through `rank-bm25`
- LLM provider priority: Groq, Gemini, OpenAI, Anthropic
- Vision model for image extraction and image questions

## Main Flows

### Document Ingestion

User uploads a document:

1. Check file extension and content.
2. Compute SHA-256 hash for duplicate detection.
3. Store document metadata in SQLite with `processing` status.
4. Extract text from PDF, DOCX, or TXT.
5. Chunk extracted text with page and section metadata.
6. Store chunks in SQLite.
7. Extract Knowledge Graph triplets from chunks.
8. Store triplets in Neo4j linked by existing SQLite `chunk_id`.
9. Generate local embeddings.
10. Store vectors in Qdrant.
11. Add chunks to the BM25 index.
12. Mark the document `ready`, or `failed` if processing fails.

### Image Document Upload

User uploads an image as a source:

1. Persist the image file.
2. Use the vision model to extract text and semantic visual detail.
3. Chunk extracted image text.
4. Store chunks in SQLite.
5. Store vectors in Qdrant and add chunks to BM25.
6. Mark the image document ready for search and citation.

### Text Chat

User asks a question:

1. Analyze and rewrite the question when useful.
2. Retrieve relevant chunks through hybrid vector and BM25 search.
3. Retrieve graph context from Neo4j when configured.
4. Rerank results when available.
5. Stream an answer over SSE.
6. Return citations and response metadata.

### Image Chat

User sends an image and a question:

1. Vision model generates a compact image search query.
2. Retrieve document context from Qdrant/BM25.
3. Retrieve graph context from Neo4j.
4. Synthesize the final answer from image understanding plus retrieved context.
5. Return citations, search query, source counts, and metadata.

### Graph Rebuild

User selects a document in Graph Explorer and clicks `Rebuild Knowledge Graph`:

1. Backend loads the existing SQLite document and chunks.
2. Old Neo4j relationships are deleted only where `relationship.chunk_id` belongs to that document.
3. Existing SQLite chunks are converted back into graph-extraction inputs.
4. Triplets are extracted again with the configured LLM.
5. New Neo4j relationships are written with the original `chunk_id`.
6. Graph Explorer can refresh to show the rebuilt relationships.

## App Pages

- Dashboard: overview, stats, capability cards, and quick actions.
- Upload: document/image dropzone, duplicate upload handling, and recent upload queue.
- Chat: streaming multimodal RAG chat with markdown, citations, source panels, and metadata.
- Library: uploaded source list with status and delete actions.
- Study Tools: quiz, flashcard, and summary generation from ready documents.
- Graph Explorer: searchable Neo4j triplet table/cards, document filter, and graph rebuild action.
- System Status: local API, SQLite, Qdrant, Neo4j, LLM, embedding, reranker, and data counts.

## API Endpoints

Health:

- `GET /api/health`

Upload:

- `POST /api/upload`

Documents:

- `GET /api/documents`
- `POST /api/documents/image`
- `GET /api/documents/{document_id}`
- `DELETE /api/documents/{document_id}`

Chat:

- `POST /api/chat`
- `GET /api/chat/sessions`
- `GET /api/chat/sessions/{session_id}`
- `DELETE /api/chat/sessions/{session_id}`

Study tools:

- `POST /api/study-tools/quiz`
- `POST /api/study-tools/flashcards`
- `POST /api/study-tools/summary`

System:

- `GET /api/system/status`

Graph:

- `GET /api/graph/triplets`
- `POST /api/graph/documents/{document_id}/rebuild`

## Local Setup

### 1. Start Qdrant

Using Docker directly:

```powershell
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

Or with Compose from the project root:

```powershell
docker compose up -d qdrant
```

### 2. Start Neo4j

Using Docker directly:

```powershell
docker run --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/your_password neo4j:latest
```

Or with Compose from the project root:

```powershell
docker compose up -d neo4j
```

Neo4j Browser opens at `http://localhost:7474`.

The backend driver uses `bolt://localhost:7687` or `bolt://127.0.0.1:7687`. Do not open the `bolt://` URI in a browser.

Change the example Neo4j password before using the Compose file for anything beyond a local demo.

### 3. Configure Backend Environment

Copy the example file and fill in your local values:

```powershell
copy backend\.env.example backend\.env
```

Do not commit real `.env` files or API keys.

At minimum, configure:

- `DATABASE_URL`
- one LLM API key such as `GROQ_API_KEY`
- `TEXT_MODEL`
- `VISION_MODEL`
- Qdrant connection values
- Neo4j URI/user/password
- embedding and reranker model names
- `CORS_ORIGINS`

### 4. Install and Run Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend runs at `http://localhost:8000`.

### 5. Install and Run Frontend

Open a second terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173`.

## Environment Example

`backend/.env.example` contains placeholders only. It intentionally does not include real secrets.

Common local defaults:

- `DATABASE_URL=sqlite+aiosqlite:///./studymate.db`
- `QDRANT_HOST=localhost`
- `QDRANT_PORT=6333`
- `QDRANT_COLLECTION=studymate_chunks`
- `NEO4J_URI=bolt://localhost:7687`
- `NEO4J_USER=neo4j`
- `NEO4J_PASSWORD=your_password`

## Troubleshooting

Neo4j Browser:

- Open `http://localhost:7474`.
- Do not open `bolt://localhost:7687` in a browser. That URI is for the backend driver.

Graph Explorer shows `0` triplets:

- The document may have been uploaded before GraphRAG was enabled.
- Neo4j may not have been configured or running during ingestion.
- The document may not contain extractable text relationships.
- Triplet extraction may have failed or returned no relationships.
- Select the document in Graph Explorer and click `Rebuild Knowledge Graph`.

Graph rebuild fails:

- Start Neo4j first.
- Confirm `NEO4J_URI`, `NEO4J_USER`, and `NEO4J_PASSWORD`.
- Confirm at least one LLM provider key is configured.
- Check backend logs for per-chunk extraction errors.

Qdrant is down:

- Vector retrieval may fail or return no context.
- Start Qdrant and check System Status.

Duplicate upload:

- Text document duplicates return `409 Conflict`.
- The frontend shows `File already exists in the library!`.

Upload stays processing:

- Check backend logs.
- Confirm the document parser, Qdrant, LLM provider, and local model downloads are working.
- Large first-time model downloads can make the first ingestion slow.

## Reset Local Data

There is no destructive reset script by default. To reset local demo data manually:

1. Stop backend and frontend.
2. Stop local services:

```powershell
docker compose down
```

3. Delete the SQLite database if you want to clear metadata:

```powershell
Remove-Item backend\studymate.db
```

4. Delete uploaded/static files if you want to clear local files:

```powershell
Remove-Item -Recurse backend\uploads
Remove-Item -Recurse backend\static\uploads
```

5. Remove Qdrant and Neo4j volumes if you want to clear vector and graph data:

```powershell
docker compose down -v
```

Use these commands carefully. They remove local demo data.

## Demo Checklist

1. Start Qdrant.
2. Start Neo4j.
3. Start the backend.
4. Start the frontend.
5. Open `http://localhost:5173`.
6. Upload a PDF, DOCX, or TXT document.
7. Wait for the document to become `ready`.
8. Chat with the document and verify citations.
9. Ask an image question and inspect the response metadata.
10. Open System Status and confirm SQLite, Qdrant, Neo4j, and LLM status.
11. Open Graph Explorer and inspect triplets.
12. If a selected document has `0` triplets, click `Rebuild Knowledge Graph`.

## Notes for Contributors

- Do not commit `.env` files or API keys.
- Keep SQLite, Qdrant, Neo4j, local CPU embeddings, and CPU reranking unless intentionally migrating.
- Keep document upload, duplicate handling, SSE chat streaming, citations, study tools, System Status, Graph Explorer, and graph rebuild behavior intact.
