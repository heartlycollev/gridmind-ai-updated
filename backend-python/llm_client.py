"""
llm_client.py
─────────────
Sends a constructed prompt to Groq Cloud API
and returns the generated text response.

Uses the official `groq` SDK (OpenAI-compatible).
Model: llama-3.3-70b-versatile — fast, accurate, generous free tier.
"""

import os
from groq import Groq
from dotenv import load_dotenv

_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_DIR, ".env"))
load_dotenv()

# ── Configuration ──────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME   = "llama-3.3-70b-versatile"   # best free-tier model on Groq

# Generation config — low temperature for factual legal Q&A
TEMPERATURE      = 0.1
MAX_TOKENS       = 1024

# ── Initialise client ──────────────────────────────────────────
if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY not found. "
        "Add it to backend-python/.env as GROQ_API_KEY=your_key"
    )

_client = Groq(api_key=GROQ_API_KEY.strip())


# ── Main generation function ───────────────────────────────────
def generate(prompt: str) -> str:
    """
    Send a prompt to Groq and return the response text.

    Parameters
    ----------
    prompt : the assembled prompt string from prompt_builder.py

    Returns
    -------
    The model's response as a plain string.
    """
    try:
        response = _client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        error_msg = str(e)

        if "401" in error_msg or "invalid_api_key" in error_msg.lower():
            raise RuntimeError(
                "Invalid Groq API key. "
                "Check GROQ_API_KEY in backend-python/.env"
            )
        if "429" in error_msg or "rate_limit" in error_msg.lower():
            raise RuntimeError(
                "Groq rate limit reached. "
                "Wait a moment and try again."
            )
        raise RuntimeError(f"Groq error: {error_msg}")


# ── Conversation-aware query rewriting ───────────────────────────
def contextualize(question: str, history: list[dict]) -> str:
    """
    Rewrites a follow-up question into a standalone question using the
    recent conversation history, WITHOUT touching the documents.

    Why this exists:
        Retrieval (retriever.retrieve) embeds only the raw question text.
        A follow-up like "what about for solar?" carries no meaning on
        its own — it needs "incentives" and "Kenya" pulled in from the
        prior turn or ChromaDB will return irrelevant chunks.

    If history is empty, the question is returned unchanged (no extra
    API call — keeps single-turn questions fast).
    """
    if not history:
        return question

    convo = "\n".join(f"{t['role'].upper()}: {t['text']}" for t in history)

    rewrite_prompt = (
        "Given this conversation history and a follow-up question, rewrite the "
        "follow-up as a standalone question that contains all the context needed "
        "to understand it on its own. Do not answer it. If the follow-up is "
        "already standalone, return it unchanged. Reply with ONLY the rewritten "
        "question, no preamble.\n\n"
        f"HISTORY:\n{convo}\n\n"
        f"FOLLOW-UP: {question}\n\n"
        "STANDALONE QUESTION:"
    )

    try:
        response = _client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": rewrite_prompt}],
            temperature=0.0,
            max_tokens=120,
        )
        rewritten = response.choices[0].message.content.strip()
        return rewritten or question
    except Exception:
        # Rewriting is a nice-to-have — if it fails, fall back to the
        # raw question rather than breaking the whole request.
        return question


# ── Health check ───────────────────────────────────────────────
def is_available() -> bool:
    """
    Returns True if the Groq API is reachable and the key is valid.
    Used by the /health endpoint.
    """
    try:
        _client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        return True
    except Exception:
        return False