# Agentic Research RAG

A seamless, highly advanced Retrieval-Augmented Generation (RAG) system composed of a Python **FastAPI Backend** and an **Angular 20 Frontend** interface.

---

## Technical Features Overview

### Backend Architecture
The backend is a robust API driving the core RAG logic. Below are the key working features implemented:

- **Parent Document Retrieval (PDR) Chunking:** 
  A highly accurate retrieval strategy. The system intelligently breaks documents down into small "child chunks" strictly for semantic similarity search, but stores their corresponding large "parent chunks." When a user asks a query, the model finds the most accurate point, but the LLM receives the full surrounding macro-context.
  
- **Local Embedded Vectors:** 
  Using `sentence-transformers/all-MiniLM-L6-v2` locally to accurately represent content mathematically without sending your documents blindly to an embedding API provider. 

- **Efficient Vector Storage Database:** 
  Using `FAISS` to store embeddings locally in a highly optimized vector space map (`documents.index`) alongside a strongly-typed hierarchical structure JSON mapping (`metadata.json`).

- **OpenRouter LLM Integration:**
  Dynamically integrates with OpenRouter's massive list of AI endpoints (currently configured to hit `stepfun/step-3.5-flash:free`). Full support strictly mapping the `X-OpenRouter-Title` headers for tracking.

- **Fast Streaming:**
  SSE (Server-Sent Events) built directly into the core query functionality meaning the user interface receives the first token in milliseconds as opposed to waiting seconds for an entire generation to complete.

- **Strict Environment Safety:**
  Completely decoupled settings loading structure checking natively for an explicit `.env` file upon startup and crashing fast ensuring API keys are never accidentally hardcoded in generic files.

### Working API Endpoints

Explore these endpoints interactively via the built-in Swagger UI by visiting: `http://127.0.0.1:8000/docs`

**Document Management:**
- `POST /api/documents/upload`: Upload `.txt`, `.md`, or `.pdf` files. Triggers PDR and locally generates FAISS vectors.
- `GET /api/documents/stats`: See indexing counts, source lists, and dimension sizes.
- `DELETE /api/documents/clear`: Perform a hard wipe of the entire local vector datastore.

**Chat & Generation:**
- `POST /api/chat/query`: Submit a query and receive a block JSON response with the final answer & sources.
- `GET /api/chat/query-stream`: Stream a response using server-sent events for a real-time typing effect.

---

## Setup & Running

### 1. Backend

We utilize `uv` to maintain lightning-fast virtual environments and run the necessary backend dependencies.

#### Installation
```cmd
cd backend
uv venv
.\.venv\Scripts\activate
uv pip install -r requirements.txt
```

#### Configuration
In the `backend/` directory, create a `.env` file (you can copy `.env.example`).
Include your required identifiers:
```env
OPENROUTER_API_KEY=your_key_here
PORT=8000
HOST=127.0.0.1
DEBUG=False
CORS_ORIGIN=*
INDEX_PATH=indices
UPLOAD_PATH=uploads
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384
LLM_MODEL=stepfun/step-3.5-flash:free
```

#### Starting the Server
You no longer need to type out massive loading commands. Use our specialized startup scripts depending upon your preferred shell:

**PowerShell (`.ps1`)**:
```powershell
cd backend
.\run_backend.ps1
```

**Command Prompt (`.bat`)**:
```cmd
cd backend
.\run_backend.bat  (or simply double click this file)
```
*Note: Both scripts will safely kill any lingering process holding port 8000, verify the existence of your `.venv`, activate it for you, and automatically spool up the Uvicorn server.*

---

### 2. Frontend

*(The Angular Chat Client Framework)*

```cmd
cd frontend
npm install
ng serve
```