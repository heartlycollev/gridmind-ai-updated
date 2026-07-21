"""
pdf_loader.py
─────────────
Loads and cleans Kenyan energy legislation PDFs.

Cleaning rules were derived by inspecting the actual documents:
  - Energy Act 2019      (HP Smart scan, 168 pages, cid: font artifacts)
  - Green Hydrogen Strategy 2023 (Adobe InDesign, photo captions, TOC dots)
  - Petroleum Act        (Apache FOP, clean digital text)

Input : path to a PDF file, human-readable document name, filename slug
Output: list of dicts  {page, text, doc, filename}
"""

import re
import pdfplumber


# ── Running header/footer patterns found in your three docs ──────────────────
_STRIP_PATTERNS = [
    r'No\.\s*1\s*(Energy|of)\s*201[89]',     # "No. 1 Energy 2019" header
    r'20\d{2}\s+Energy\s+No\.\s*\d+',        # "2019 Energy No. 1" header
    r'LAWS OF KENYA\s*',
    r'Kenya Gazette Supplement[^\n]*',
    r'GREEN HYDROGEN STRATEGY AND ROADMAP FOR KENYA',
    r'PRINTED AND PUBLISHED BY THE GOVERNMENT PRINTER.*',
    
    # ── KNEECS 2022 patterns ──
    r'Implementation Plan of the Kenya National Energy Efficiency and Conservation Strategy',
    r'Image Source:.*',
    r'www\.(unsplash|freepik)\.com',
    
    # ── Strategic Plan 2023-2027 patterns ──
    r'MINISTRY OF ENERGY AND PETROLEUM',
    r'2023\s*-\s*2027 STRATEGIC PLAN',
    r'(?m)^\s*(?:\d{1,4}|[ivx]{1,5})\s*\|\s*page\s*$',  # matches "12 | Page" or "iii | Page"
    
    # ── KETIP 2023-2050 patterns ──
    r'(?m)^\s*[ivx]{1,5}\s*$',  # matches standalone Roman numeral page numbers like "ii" or "iv"
]

# ── Photo-caption / image-only page signals ───────────────────────────────────
_CAPTION_SIGNALS = [
    'flamingoes', 'flamingo', 'zebra', 'wildebeest', 'dhows',
    'savannah', 'safari', 'on the african',
]


def _clean(text: str) -> str:
    """Remove PDF artifacts, running headers, and normalise whitespace."""

    # 1. Remove (cid:N) font-encoding artifacts (Energy Act scan issue)
    text = re.sub(r'\(cid:\d+\)', ' ', text)

    # 2. Remove form-feed characters
    text = re.sub(r'\f', '', text)

    # 3. Strip running headers / footers
    for pattern in _STRIP_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)

    # 4. Remove standalone page-number lines: "  123  " or "- 12 -"
    text = re.sub(r'(?m)^\s*-?\s*\d{1,4}\s*-?\s*$', '', text)

    # 5. Collapse runs of dots (TOC entries like "Section 45 ......... 23")
    text = re.sub(r'\.{4,}', '', text)

    # 6. Normalise whitespace
    text = re.sub(r'[ \t]{2,}', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)

    # 7. Drop lines that are too short to carry meaning (< 4 chars)
    lines = [ln for ln in text.split('\n') if len(ln.strip()) >= 4]

    return '\n'.join(lines).strip()


def _is_noise_page(text: str) -> bool:
    """
    Return True for pages that are predominantly images, captions, or
    structural boilerplate rather than substantive legal/policy content.
    """
    lower = text.lower()

    # Photo captions in the Green Hydrogen Strategy doc
    if any(sig in lower for sig in _CAPTION_SIGNALS):
        return True

    # Too short after cleaning — probably a chapter divider image page
    if len(text.strip()) < 80:
        return True

    # Page is >30% dots — it's a TOC page
    if text.count('.') > len(text) * 0.30:
        return True

    return False


def load_pdf(path: str, doc_name: str, filename: str) -> list[dict]:
    """
    Load a single PDF and return a list of cleaned page records.

    Parameters
    ----------
    path     : absolute path to the PDF file
    doc_name : human-readable name, e.g. "Energy Act 2019"
    filename : slug used in ChromaDB IDs, e.g. "energy_act_2019.pdf"

    Returns
    -------
    List of dicts:
        {
            "page"    : int,   # 1-based page number
            "text"    : str,   # cleaned text
            "doc"     : str,   # doc_name
            "filename": str    # filename slug
        }
    """
    pages = []

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            raw = page.extract_text()
            if not raw:
                continue

            cleaned = _clean(raw)

            if _is_noise_page(cleaned):
                continue

            pages.append({
                "page":     i + 1,
                "text":     cleaned,
                "doc":      doc_name,
                "filename": filename,
            })

    return pages


# ── Document registry ─────────────────────────────────────────────────────────
# Add new PDFs here as you acquire more Kenyan energy documents.
DOCUMENTS = [
    {
        "path":     "documents/Energy Act-2019.pdf",
        "doc_name": "Energy Act 2019",
        "filename": "energy_act_2019.pdf",
    },
    {
        "path":     "documents/Green Hydrogen Strategy-2023.pdf",
        "doc_name": "Green Hydrogen Strategy 2023",
        "filename": "green_hydrogen_strategy_2023.pdf",
    },
    {
        "path":     "documents/Petroleum Act Cap 308.pdf",
        "doc_name": "Petroleum Act Cap 308",
        "filename": "petroleum_act.pdf",
    },
    {
        "path":     "documents/KETIP 2023-2050.pdf",
        "doc_name": "Kenya Energy Transition and Investment Plan 2023-2050",
        "filename": "ketip_2023_2050.pdf",
    },
    {
        "path":     "documents/KNEECS Implementation Plan-2022.pdf",
        "doc_name": "Kenya National Energy Efficiency and Conservation Strategy (KNEECS) Implementation Plan 2022",
        "filename": "kneecs_implementation_plan.pdf",
    },
    {
        "path":     "documents/Strategic Plan 2023-2027.pdf",
        "doc_name": "Strategic Plan 2023-2027",
        "filename": "strategic_plan_2023_2027.pdf",
    },
]


def load_all_documents(base_path: str = ".") -> list[dict]:
    """
    Load every document in DOCUMENTS registry.
    base_path: the project root (where the documents/ folder lives).
    """
    import os
    all_pages = []

    for doc in DOCUMENTS:
        full_path = os.path.join(base_path, doc["path"])

        if not os.path.exists(full_path):
            print(f"  [SKIP] Not found: {full_path}")
            continue

        pages = load_pdf(full_path, doc["doc_name"], doc["filename"])
        all_pages.extend(pages)
        print(f"  [OK] {doc['doc_name']}: {len(pages)} pages loaded")

    return all_pages
