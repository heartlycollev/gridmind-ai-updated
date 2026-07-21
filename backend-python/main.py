"""
main.py
───────
GridMind AI — Python RAG Service

FastAPI application that receives questions from the Node.js server,
runs the full RAG pipeline, and returns grounded answers.

Endpoints:
    POST /chat     — main RAG endpoint
    GET  /health   — service status check (used by frontend badge)

Run with:
    cd backend-python
    uvicorn main:app --reload --port 8000

The Node.js server (port 5000) forwards requests here.
This service must be running before you start the Node server.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import traceback

from retriever      import retrieve, is_ready
from prompt_builder import build_prompt, format_sources
from llm_client     import generate, is_available, contextualize
import memory


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GridMind AI — RAG Service",
    description="Kenyan Energy Policy Intelligence Assistant",
    version="1.0.0",
)

# Allow requests from the Node.js server and the browser directly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000", "http://127.0.0.1:5000",
                   "http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    top_k: int = 5   # number of chunks to retrieve; can be overridden per-request
    session_id: str | None = None   # used to keep conversation memory per chat session


class SourceItem(BaseModel):
    index:    int
    document: str
    filename: str
    page:     int
    excerpt:  str


class ChatResponse(BaseModel):
    answer:  str
    sources: list[SourceItem]


class HealthResponse(BaseModel):
    status:  str
    rag:     bool   # True when ChromaDB has documents
    llm:     bool   # True when Groq (LLM) is reachable


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse)
async def health():
    """
    Returns the service status.
    The frontend uses this to decide whether to show the RAG badge.
    """
    db_ready  = is_ready()
    llm_ready = is_available()

    return HealthResponse(
        status = "ok" if (db_ready and llm_ready) else "degraded",
        rag    = db_ready,
        llm    = llm_ready,
    )


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    Clears conversation memory for a session.
    Called by the frontend when the user starts a new chat.
    """
    memory.clear_session(session_id)
    return {"status": "cleared"}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Main RAG endpoint.

    Pipeline:
        1. Validate the question
        2. Retrieve top-k relevant chunks from ChromaDB
        3. Build the grounded prompt
        4. Send to Groq
        5. Return answer + source citations
    """
    question = req.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    if len(question) > 1000:
        raise HTTPException(status_code=400, detail="Question too long (max 1000 chars).")

    try:
        # ── Step 0: Pull recent conversation history for this session ────────
        history = memory.get_history(req.session_id)

        # ── Step 1: Retrieve relevant chunks ─────────────────────────────────
        # Rewrite the question into a standalone form first, so follow-ups
        # like "what about for solar?" retrieve the right chunks.
        search_question = contextualize(question, history)
        chunks = retrieve(search_question, top_k=req.top_k)

        # ── Step 2: Build the prompt ──────────────────────────────────────────
        prompt = build_prompt(question, chunks, history)

        # ── Step 3: Generate the answer ───────────────────────────────────────
        answer = generate(prompt)

        # ── Step 4: Format sources for the frontend ───────────────────────────
        sources = format_sources(chunks)

        # ── Step 5: Save this turn to conversation memory ─────────────────────
        memory.add_turn(req.session_id, "user", question)
        memory.add_turn(req.session_id, "assistant", answer)

        return ChatResponse(answer=answer, sources=sources)

    except RuntimeError as e:
        # Known errors (Voyage/Groq unreachable, ChromaDB missing)
        raise HTTPException(status_code=503, detail=str(e))

    except Exception as e:
        # Unexpected errors — log full traceback server-side, return clean message
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail="An internal error occurred. Check the Python server terminal for details."
        )


# ── Dev runner ────────────────────────────────────────────────────────────────
# Allows running directly with:  python main.py
# (uvicorn is still preferred for production)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
