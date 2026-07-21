"""
retriever.py
────────────
Converts a user question into a vector embedding, queries ChromaDB,
and returns the top-k most relevant chunks from your Kenyan energy documents.

Flow:
    question (str)
        → voyage-3.5 (Voyage AI API)  →  1024-dim vector
        → ChromaDB cosine similarity search
        → top-k chunks with metadata + relevance scores
"""

import os
import chromadb
import voyageai
from dotenv import load_dotenv

_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_DIR, ".env"))
load_dotenv()

VOYAGE_API_KEY  = os.getenv("VOYAGE_API_KEY")
EMBED_MODEL     = "voyage-3.5"
EMBED_DIMENSION = 1024   # must match ingestion/embedder.py — see its note on dimensions
CHROMA_API_KEY  = os.getenv("CHROMA_API_KEY")
CHROMA_TENANT   = os.getenv("CHROMA_TENANT")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE", "chroma-rag")
COLLECTION_NAME = "energy_docs"

# How many chunks to retrieve per question.
# 5 gives enough variety to cover multi-part questions
# while keeping the prompt concise for the LLM.
DEFAULT_TOP_K = 5

# Relevance threshold: discard chunks with cosine distance > this value.
# Distance 0.0 = identical, 1.0 = completely unrelated.
# 0.75 filters out chunks with only superficial keyword overlap.
MAX_DISTANCE = 0.75

if not VOYAGE_API_KEY:
    raise RuntimeError(
        "VOYAGE_API_KEY not found. "
        "Add it to backend-python/.env as VOYAGE_API_KEY=your_key"
    )

_voyage_client = voyageai.Client(api_key=VOYAGE_API_KEY)


# ── Singleton ChromaDB Cloud client ──────────────────────────────────────────
_client:     chromadb.ClientAPI | None = None
_collection: chromadb.Collection | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    if not CHROMA_API_KEY or not CHROMA_TENANT or not CHROMA_DATABASE:
        missing = [
            var for var, val in [
                ("CHROMA_API_KEY", CHROMA_API_KEY),
                ("CHROMA_TENANT", CHROMA_TENANT),
                ("CHROMA_DATABASE", CHROMA_DATABASE),
            ] if not val
        ]
        raise RuntimeError(
            f"Missing required ChromaDB Cloud credential(s): {', '.join(missing)}. "
            f"Please set them in backend-python/.env"
        )

    try:
        return chromadb.CloudClient(
            tenant=CHROMA_TENANT,
            database=CHROMA_DATABASE,
            api_key=CHROMA_API_KEY
        )
    except Exception as e:
        raise RuntimeError(
            f"Failed to authenticate or connect to ChromaDB Cloud: {e}. "
            f"Please check CHROMA_API_KEY, CHROMA_TENANT, and CHROMA_DATABASE in backend-python/.env"
        )


def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is None:
        _client = get_chroma_client()
        try:
            _collection = _client.get_collection(COLLECTION_NAME)
        except Exception as e:
            raise RuntimeError(
                f"Failed to retrieve collection '{COLLECTION_NAME}' from ChromaDB Cloud: {e}. "
                f"Ensure ingestion/ingest.py has been run to populate the database."
            )
    return _collection


# ── Embedding ─────────────────────────────────────────────────────────────────

def embed_query(text: str) -> list[float]:
    """
    Embed a single question using Voyage's voyage-3.5 model with
    input_type="query" — Voyage embeds queries and documents differently
    under the hood for better retrieval accuracy, so this MUST match the
    input_type="document" used when ingesting (see ingestion/embedder.py).
    Returns a list of 1024 floats.
    """
    try:
        result = _voyage_client.embed(
            [text],
            model=EMBED_MODEL,
            input_type="query",
            output_dimension=EMBED_DIMENSION,
        )
        return result.embeddings[0]

    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "api key" in error_msg.lower():
            raise RuntimeError(
                "Invalid Voyage API key. Check VOYAGE_API_KEY in backend-python/.env"
            )
        if "429" in error_msg or "rate limit" in error_msg.lower():
            raise RuntimeError(
                "Voyage rate limit reached. Wait a moment and try again."
            )
        raise RuntimeError(f"Voyage embedding error: {error_msg}")


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve(question: str, top_k: int = DEFAULT_TOP_K) -> list[dict]:
    """
    Retrieve the most relevant document chunks for a given question.

    Parameters
    ----------
    question : the user's raw question string
    top_k    : number of chunks to return (default 5)

    Returns
    -------
    List of dicts, sorted by relevance (most relevant first):
        {
            "text"      : str,   # the chunk text
            "doc"       : str,   # "Energy Act 2019"
            "filename"  : str,   # "energy_act_2019.pdf"
            "page"      : int,   # source page number
            "relevance" : float  # 0.0–1.0, higher = more relevant
        }

    Returns an empty list if ChromaDB has no documents or
    if no chunks pass the relevance threshold.
    """
    # Embed the question
    query_vector = embed_query(question)

    # Query ChromaDB
    collection = _get_collection()
    results    = collection.query(
        query_embeddings=[query_vector],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for text, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # Skip low-relevance chunks
        if dist > MAX_DISTANCE:
            continue

        chunks.append({
            "text":      text,
            "doc":       meta.get("doc",      "Unknown document"),
            "filename":  meta.get("filename", "unknown.pdf"),
            "page":      meta.get("page",     0),
            "relevance": round(1.0 - dist, 3),
        })

    return chunks


def is_ready() -> bool:
    """
    Returns True if ChromaDB is accessible and has documents.
    Used by the /health endpoint.
    """
    try:
        col = _get_collection()
        return col.count() > 0
    except Exception:
        return False
