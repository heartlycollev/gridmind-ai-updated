# GridMind AI — Kenyan Energy Policy Intelligence Assistant

A Retrieval-Augmented Generation (RAG) chatbot that answers questions using official Kenyan energy legislation and policy documents.

This project uses **Groq** (Llama 3.3 70B) for grounding answers, and **Voyage AI's voyage-3.5** to generate text embeddings via API, stored in a persistent **ChromaDB** database. Conversation memory is kept per chat session so follow-up questions resolve correctly.

---

## How It Works

```
Your question
     ↓
Node.js gateway server (port 5000)
     ↓
Python RAG service (port 8000)
     ↓
voyage-3.5 (Voyage AI API)  →  ChromaDB similarity search
     ↓
Top 5 relevant passages from your documents
     ↓
Prompt constructor (+ conversation history)  →  Groq (Llama 3.3 70B)
     ↓
Grounded, Markdown-formatted answer + source citations
     ↓
Your browser
```

---

## Document Library

The following official Kenyan energy documents are indexed:

| Document | Description |
|---|---|
| Energy Act 2019 | Primary energy sector legislation |
| Green Hydrogen Strategy 2023 | National hydrogen policy framework |
| KETIP 2023–2050 | Kenya Energy Transition & Investment Plan |
| KNEECS Implementation Plan 2022 | Kenya National Energy Efficiency & Conservation Strategy |
| Petroleum Act Cap 308 | Petroleum sector regulation |
| Strategic Plan 2023–2027 | Energy sector strategic direction |

---

## One-Time Setup (Starting Fresh)

Follow these steps in order to set up the environment from scratch.

### 1. Install System Dependencies

| Dependency | Version | Download |
|---|---|---|
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) — ✅ check "Add Python to PATH" |
| Node.js | LTS | [nodejs.org](https://nodejs.org/) |

No local model runtime is required — embeddings (Voyage AI) and generation (Groq) both run via API, nothing to install or run in the background.

### 2. Get a Voyage AI API Key (embeddings)

1. Go to [dashboard.voyageai.com](https://dashboard.voyageai.com)
2. Sign up and create an API key
3. Copy the key

### 3. Get a Groq API Key (answer generation)

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up and create an API key
3. Copy the key

### 4. Configure Environment Variables

Create (or update) the `.env` file in `backend-python/`:

```env
# backend-python/.env
GROQ_API_KEY=your_groq_api_key_here
VOYAGE_API_KEY=your_voyage_api_key_here
ANONYMOUS_TELEMETRY=False
```

Create (or update) the `.env` file in `backend-node/`:

```env
# backend-node/.env
GROQ_API_KEY=your_groq_api_key_here
PYTHON_URL=http://localhost:8000
```

### 5. Create the Python Virtual Environment

From the **project root** (`c:\gridmind-ai`):

```powershell
python -m venv venv
venv\Scripts\pip install -r backend-python\requirements.txt
```

### 6. Install Node Dependencies

```powershell
cd backend-node
npm install
cd ..
```

### 7. Ingest Your Documents (One-Time Only)

Place any PDF files you want to search into the `documents/` folder, then run:

```powershell
venv\Scripts\python ingestion\ingest.py
```

This will embed all documents into ChromaDB via the Voyage API (typically well under a minute, since it's batched API calls rather than local inference).
The database is saved to `chroma_db/` and persists across restarts — **you only run this once** unless you add new documents or change the embedding model/dimension.

---

## Running the Application

Every time you want to start the app, follow these steps (all from the project root `c:\gridmind-ai`):

### Step 1 — Start the Python RAG Service

Open a **new terminal** and run:
```powershell
cd c:\gridmind-ai\backend-python
..\venv\Scripts\uvicorn main:app --port 8000
```

Wait until you see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Step 2 — Start the Node.js Gateway

Open **another new terminal** and run:
```powershell
cd c:\gridmind-ai\backend-node
node server.js
```

Wait until you see:
```
┌─────────────────────────────────────────┐
│         GridMind AI  —  Node Server     │
├─────────────────────────────────────────┤
│  Frontend  →  http://localhost:5000      │
│  RAG svc   →  http://localhost:8000     │
└─────────────────────────────────────────┘
```

### Step 3 — Open the App

Navigate to **[http://localhost:5000](http://localhost:5000)** in your browser.

---

## Project Structure

```
gridmind-ai/
├── frontend/               # HTML/CSS/JS user interface
│   ├── index.html
│   ├── style.css
│   └── app.js
├── backend-node/           # Node.js gateway (port 5000)
│   ├── server.js
│   ├── package.json
│   └── .env                ← your API key goes here
├── backend-python/         # Python RAG service (port 8000)
│   ├── main.py             # FastAPI app
│   ├── retriever.py        # ChromaDB vector search (Voyage embeddings)
│   ├── llm_client.py       # Groq API wrapper + query contextualizer
│   ├── prompt_builder.py   # Prompt assembly (incl. conversation history)
│   ├── memory.py           # Per-session conversation memory
│   ├── requirements.txt
│   └── .env                ← your API keys go here (Groq + Voyage)
├── ingestion/              # One-time document ingestion scripts
│   ├── ingest.py           # Entry point
│   ├── pdf_loader.py
│   ├── chunker.py
│   └── embedder.py         # Embeds chunks via Voyage AI
├── documents/              # Place your PDFs here
├── chroma_db/              # Auto-generated vector database (do not edit)
└── venv/                   # Python virtual environment (auto-generated)
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `Invalid Groq API key` | Wrong or expired key | Generate a new key at [console.groq.com](https://console.groq.com) |
| `Groq rate limit reached` | Free tier limit hit | Wait a moment and try again, or check your Groq usage dashboard |
| `Invalid Voyage API key` | Wrong or missing key | Generate a new key at [dashboard.voyageai.com](https://dashboard.voyageai.com) |
| `Voyage rate limit reached` | Free tier limit hit | Wait a moment and try again |
| `rag: false` in health check | ChromaDB not found, or wrong embedding dimension | Ensure you ran `ingest.py` from the project root, **not** from inside `backend-python/`. If you changed embedding models/dimensions, delete `chroma_db/` and re-run ingestion |
| `Port already in use (8000)` | Previous uvicorn instance still running | Run `taskkill /F /IM python.exe` in PowerShell, then restart |
| `Collection energy_docs does not exist` | ChromaDB path mismatch, or dimension mismatch after switching embedding models | Delete `chroma_db/` and re-run `ingest.py` |
| `Connection refused` on port 5000 | Node server not running | Start it with `node server.js` inside `backend-node/` |
