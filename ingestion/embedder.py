"""
embedder.py
───────────
Embeds text chunks using Voyage AI's voyage-3.5 model and
stores them in a local ChromaDB persistent collection.

Prerequisites:
    VOYAGE_API_KEY set in backend-python/.env
    (get a free key at https://dashboard.voyageai.com)

ChromaDB data is stored at:  ./chroma_db/   (relative to project root)
Collection name:  "energy_docs"

Note on dimensions:
    voyage-3.5 outputs 1024-dimensional vectors by default. If you ever
    re-run ingestion with a different EMBED_DIMENSION, you MUST also
    delete the existing chroma_db/ folder first — ChromaDB collections
    are locked to whatever dimension they were created with, and mixing
    dimensions in one collection will break retrieval.
"""

import os
import sys
import chromadb
import voyageai
from dotenv import load_dotenv

# Load backend-python/.env regardless of where this script is run from
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, "backend-python", ".env"))

VOYAGE_API_KEY  = os.getenv("VOYAGE_API_KEY")
EMBED_MODEL     = "voyage-3.5"
EMBED_DIMENSION = 1024   # default for voyage-3.5; keep in sync with retriever.py
CHROMA_API_KEY  = os.getenv("CHROMA_API_KEY")
CHROMA_TENANT   = os.getenv("CHROMA_TENANT")
CHROMA_DATABASE = os.getenv("CHROMA_DATABASE", "chroma-rag")
COLLECTION_NAME = "energy_docs"

# Voyage accepts up to 1000 texts per embed() call, but very large batches
# risk hitting the per-request token cap — 100 is a safe, fast middle ground.
BATCH_SIZE = 100

if not VOYAGE_API_KEY:
    raise RuntimeError(
        "VOYAGE_API_KEY not found. "
        "Add it to backend-python/.env as VOYAGE_API_KEY=your_key"
    )

_client = voyageai.Client(api_key=VOYAGE_API_KEY)


# ── Embedding ─────────────────────────────────────────────────────────────────

def get_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Embed a batch of texts using Voyage's voyage-3.5 model with
    input_type="document" (tells Voyage these are retrieval targets,
    not search queries — Voyage embeds the two differently for better
    retrieval accuracy).

    Returns a list of float lists, one per input text, same order.
    Raises RuntimeError on API failures (bad key, rate limit, etc).
    """
    try:
        result = _client.embed(
            texts,
            model=EMBED_MODEL,
            input_type="document",
            output_dimension=EMBED_DIMENSION,
        )
        return result.embeddings

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


# ── ChromaDB Cloud Client ──────────────────────────────────────────────────────

def get_chroma_client() -> chromadb.ClientAPI:
    """
    Return an authenticated ChromaDB CloudClient using backend-python/.env settings.
    """
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


def get_or_create_collection() -> chromadb.Collection:
    """
    Return the ChromaDB Cloud collection, creating it if it doesn't exist.
    Uses cosine similarity (best for text embeddings).
    """
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def collection_is_populated() -> bool:
    """Return True if the collection already has documents stored in ChromaDB Cloud."""
    client = get_chroma_client()
    try:
        col = client.get_collection(COLLECTION_NAME)
        return col.count() > 0
    except Exception:
        return False


# ── Main ingestion function ───────────────────────────────────────────────────

def embed_and_store(chunks: list[dict]) -> int:
    """
    Embed all chunks and store them in ChromaDB Cloud.

    Parameters
    ----------
    chunks : output of chunker.chunk_pages()

    Returns
    -------
    Number of chunks successfully stored.
    """
    collection = get_or_create_collection()
    total      = len(chunks)
    stored     = 0

    print(f"Embedding {total} chunks using {EMBED_MODEL} (Voyage AI, {EMBED_DIMENSION}-dim)...")
    print("(Batched API calls — this should take well under a minute)")
    print()

    for start in range(0, total, BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]

        ids       = []
        texts     = []
        metadatas = []

        for i, chunk in enumerate(batch):
            global_idx = start + i
            doc_slug   = chunk["metadata"]["filename"].replace(".pdf", "")
            chunk_id   = (
                f"{doc_slug}"
                f"_p{chunk['metadata']['page']}"
                f"_c{chunk['metadata']['chunk_idx']}"
                f"_{global_idx}"
            )

            ids.append(chunk_id)
            texts.append(chunk["text"])
            metadatas.append(chunk["metadata"])

        # One batched API call per BATCH_SIZE chunks, instead of one call per chunk
        embeddings = get_embeddings(texts)

        collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )

        stored += len(batch)
        pct     = int(stored / total * 100)
        bar     = "#" * (pct // 5) + "-" * (20 - pct // 5)
        print(f"  [{bar}] {pct:3d}%  ({stored}/{total} chunks)", end="\r")

    print(f"\n\nDone. {stored} chunks stored in ChromaDB Cloud collection '{COLLECTION_NAME}'")
    return stored
