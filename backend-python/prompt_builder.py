"""
prompt_builder.py
─────────────────
Assembles the final prompt that gets sent to Mistral.

Structure:
    [System instruction]  — tells Mistral to answer ONLY from context
    [Context block]       — the retrieved chunks, each labelled with source + page
    [Question]            — the user's original question
    [Answer cue]          — "ANSWER:" to start Mistral's response

Why strict grounding matters:
    Without explicit instructions, Mistral will supplement missing context
    with its own training knowledge. For legal/policy documents this is
    dangerous — the model may confidently state outdated or incorrect law.
    The prompt below makes "I could not find this" the correct fallback.
"""


# ── System instruction ────────────────────────────────────────────────────────
# Baked-in knowledge of your six documents so the model knows what it has.

_SYSTEM = """You are GridMind AI, an expert assistant on Kenyan energy legislation and policy.

You have access to the following official Kenyan documents:
  - Energy Act 2019 (No. 1 of 2019) — the primary electricity and energy regulatory framework
  - Petroleum Act (Cap. 308) — upstream and downstream petroleum regulation
  - Green Hydrogen Strategy and Roadmap for Kenya (2023) — national hydrogen policy
  - Kenya Energy Transition Investment Plan (KETIP) 2023-2050 — framework for national energy transition
  - Kenya National Energy Efficiency and Conservation Strategy (KNEECS) Implementation Plan 2022 — roadmap for energy conservation
  - Strategic Plan 2023-2027 — institutional roadmap and strategic objectives

STRICT RULES you must follow:
1. Answer ONLY using the context passages provided below. Do not use any outside knowledge.
2. If the context does not contain enough information to answer, respond with exactly:
   "I could not find this information in the provided Kenyan energy documents."
3. Cite your sources inline using bracketed numerical citations like [1], [2], etc., corresponding directly to context passage [1], passage [2], etc.
4. If multiple passages are relevant, synthesise them and cite each inline using bracket numbers (e.g. [1][2]).
5. Use clear, direct language. Avoid unnecessary legal jargon.
6. Do not speculate, infer, or extrapolate beyond what the context explicitly states.
7. You may be shown earlier turns from this conversation for context (e.g. to
   resolve "what about..." style follow-ups). Use them only to understand what
   the user is asking — never as a source of facts. Every factual claim must
   still come from the CONTEXT PASSAGES for the current question.

FORMATTING RULES (Markdown, rendered in a chat UI):
- Use **bold** for key terms, section/act names, and numbers (fees, penalties, dates).
- Use bullet points ("- ") whenever an answer has multiple parts, conditions, or a list of items.
- Use numbered lists for sequential steps or ordered requirements.
- Keep paragraphs short (2-3 sentences max).
- Include inline citations like [1], [2] directly after statements derived from passage 1, passage 2, etc.
- Do not use headings (#) — this is a chat bubble, not a document."""


# ── Prompt assembly ───────────────────────────────────────────────────────────

def build_prompt(question: str, chunks: list[dict], history: list[dict] | None = None) -> str:
    """
    Build the complete prompt string for the LLM.

    Parameters
    ----------
    question : the user's original question
    chunks   : output of retriever.retrieve()
               each dict has keys: text, doc, filename, page, relevance
    history  : optional recent conversation turns, output of memory.get_history()
               each dict has keys: role ("user"/"assistant"), text

    Returns
    -------
    A single string ready to be sent to the LLM.
    """
    history_block = _format_history(history)

    if not chunks:
        # No relevant context found — short-circuit with a grounded refusal prompt
        return (
            f"{_SYSTEM}\n\n"
            f"{history_block}"
            f"CONTEXT:\n[No relevant passages found in the documents.]\n\n"
            f"QUESTION: {question}\n\n"
            f"ANSWER:"
        )

    # Format each chunk with its source label matching numeric index [1], [2], etc.
    context_parts = []
    for i, chunk in enumerate(chunks, start=1):
        label = f"[{i}] Document: {chunk['doc']}, Page: {chunk['page']}"
        context_parts.append(f"{label}\n{chunk['text']}")

    context_block = "\n\n---\n\n".join(context_parts)

    prompt = (
        f"{_SYSTEM}\n\n"
        f"{history_block}"
        f"CONTEXT PASSAGES:\n\n"
        f"{context_block}\n\n"
        f"---\n\n"
        f"QUESTION: {question}\n\n"
        f"ANSWER:"
    )

    return prompt


def _format_history(history: list[dict] | None) -> str:
    """
    Formats recent conversation turns into a labelled block, or returns
    an empty string if there's no history (keeps single-turn prompts
    identical to before this feature existed).
    """
    if not history:
        return ""

    lines = [f"{t['role'].upper()}: {t['text']}" for t in history]
    return "PREVIOUS CONVERSATION (for context only, not a source of facts):\n" + "\n".join(lines) + "\n\n"


def format_sources(chunks: list[dict]) -> list[dict]:
    """
    Build the parallel sources array returned to the frontend alongside the answer.
    Preserves chunk order (1-indexed) so sources[i].index maps 1:1 with inline [1], [2] citations in the answer text.

    Returns
    -------
    List of dicts matching data contract:
    [
        {
            "index": 1,
            "document": "Energy Act 2019",
            "filename": "Energy Act-2019.pdf",
            "page": 45,
            "excerpt": "...exact retrieved text..."
        },
        ...
    ]
    """
    sources = []

    for i, chunk in enumerate(chunks, start=1):
        sources.append({
            "index":    i,
            "document": chunk.get("doc", "Unknown document"),
            "filename": chunk.get("filename", "unknown.pdf"),
            "page":     chunk.get("page", 0),
            "excerpt":  chunk.get("text", ""),
        })

    return sources
