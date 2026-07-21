"""
chunker.py
──────────
Splits cleaned page text into overlapping chunks ready for embedding.

Chunk size = 600 chars  (~120 words)
Overlap    = 100 chars  (~17%)

Why these numbers for your specific documents:
- Energy Act & Petroleum Act use dense legal paragraphs.
  600 chars captures a full sub-section clause without losing context.
- Green Hydrogen Strategy uses longer narrative paragraphs.
  600 chars keeps each chunk focused on one policy point.
- 100-char overlap prevents legal sentences that straddle chunk
  boundaries from losing their connector context.

Input : list of page dicts from pdf_loader.py
Output: list of chunk dicts with text + metadata
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter


CHUNK_SIZE    = 1000  # characters per chunk (preserves tables and lists)
CHUNK_OVERLAP = 200   # characters shared with adjacent chunk
MIN_CHUNK_LEN = 100   # discard chunks shorter than this


_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    # Try to split at: paragraph → newline → sentence → word boundary
    separators=["\n\n", "\n", ". ", " ", ""],
)


def chunk_pages(pages: list[dict]) -> list[dict]:
    """
    Split a list of page records into overlapping text chunks.

    Parameters
    ----------
    pages : output of pdf_loader.load_all_documents()

    Returns
    -------
    List of dicts:
        {
            "text"    : str,
            "metadata": {
                "doc"       : str,   # "Energy Act 2019"
                "filename"  : str,   # "energy_act_2019.pdf"
                "page"      : int,   # source page number
                "chunk_idx" : int    # position within that page
            }
        }
    """
    all_chunks = []

    for page in pages:
        splits = _splitter.split_text(page["text"])

        for idx, split in enumerate(splits):
            text = split.strip()

            if len(text) < MIN_CHUNK_LEN:
                continue  # skip fragments too short to be useful

            all_chunks.append({
                "text": text,
                "metadata": {
                    "doc":       page["doc"],
                    "filename":  page["filename"],
                    "page":      page["page"],
                    "chunk_idx": idx,
                },
            })

    return all_chunks
