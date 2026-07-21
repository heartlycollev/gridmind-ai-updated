"""
ingest.py
─────────
Run this ONCE before starting GridMind AI for the first time.
Re-run whenever you add new documents to the documents/ folder, or
whenever you change the embedding model/dimension.

Usage:
    cd gridmind-ai
    venv\\Scripts\\activate          (Windows)
    python ingestion/ingest.py

What it does:
    1. Loads all PDFs from the documents/ folder
    2. Cleans and chunks the text
    3. Calls Voyage AI (voyage-3.5) to embed each chunk
    4. Stores everything in ./chroma_db/

Prerequisites:
    - VOYAGE_API_KEY set in backend-python/.env
    - PDFs are in:        documents/

Note: if you're switching embedding models/providers (e.g. from Ollama to
Voyage, or changing output_dimension), you MUST re-ingest from scratch —
this script will detect the existing collection and offer to wipe it.
"""

import sys
import os

# Allow running from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.pdf_loader import load_all_documents
from ingestion.chunker    import chunk_pages
from ingestion.embedder   import (
    embed_and_store,
    collection_is_populated,
    get_chroma_client,
    COLLECTION_NAME,
)


def main():
    print("=" * 60)
    print("  GridMind AI — Document Ingestion Pipeline (ChromaDB Cloud)")
    print("=" * 60)
    print()

    # ── Guard: warn if already populated ─────────────────────────────────────
    if collection_is_populated():
        print("WARNING: ChromaDB Cloud collection already contains documents.")
        answer = input("Re-ingest and overwrite? (yes/no): ").strip().lower()
        if answer != "yes":
            print("Ingestion cancelled. Existing database unchanged.")
            return

        # Delete existing collection in Chroma Cloud
        client = get_chroma_client()
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"Existing collection '{COLLECTION_NAME}' deleted from ChromaDB Cloud.\n")
        except Exception as e:
            print(f"Note: Could not delete existing collection ({e})\n")

    # ── Step 1: Load PDFs ─────────────────────────────────────────────────────
    print("Step 1/3 — Loading PDFs from documents/")
    print("-" * 40)
    pages = load_all_documents(base_path=".")

    if not pages:
        print("\nNo documents found in documents/")
        print("Put your PDF files in the documents/ folder and try again.")
        return

    total_chars = sum(len(p["text"]) for p in pages)
    print(f"\nLoaded {len(pages)} pages  (~{total_chars:,} characters total)\n")

    # ── Step 2: Chunk ─────────────────────────────────────────────────────────
    print("Step 2/3 — Splitting into chunks")
    print("-" * 40)
    chunks = chunk_pages(pages)

    # Per-document breakdown
    docs_seen = {}
    for c in chunks:
        name = c["metadata"]["doc"]
        docs_seen[name] = docs_seen.get(name, 0) + 1
    for name, count in docs_seen.items():
        print(f"  {name}: {count} chunks")
    print(f"\nTotal chunks to embed: {len(chunks)}\n")

    # ── Step 3: Embed + Store ─────────────────────────────────────────────────
    print("Step 3/3 — Embedding and storing in ChromaDB Cloud")
    print("-" * 40)
    stored = embed_and_store(chunks)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  Ingestion complete!")
    print(f"  {stored} chunks stored in ChromaDB Cloud collection '{COLLECTION_NAME}'")
    print()
    print("  Next steps:")
    print("  1. Start the Python RAG service:")
    print("       cd backend-python")
    print("       uvicorn main:app --reload --port 8000")
    print("  2. Start the Node server:")
    print("       cd backend-node")
    print("       node server.js")
    print("  3. Open http://localhost:5000 in your browser")
    print("=" * 60)


if __name__ == "__main__":
    main()
