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


# ── Mechanism 1: Pre-retrieval Intent Classification ─────────────
_GREETING_KEYWORDS = {
    "hi", "hello", "hey", "greetings", "good morning", "good afternoon",
    "good evening", "thanks", "thank you", "thankyou", "how are you",
    "who are you", "what is your name", "what's your name", "bye", "goodbye",
    "nice to meet you", "cool", "ok", "okay"
}

def classify_intent(question: str, history: list[dict] | None = None) -> str:
    """
    Classifies user question for Mechanism 1 (Pre-retrieval check).

    Returns:
        "GREETING" : Simple greetings or pleasantries (heuristic match)
        "META"     : Questions about conversation history or past turns (LLM match)
        "DOMAIN"   : Domain/factual questions -> proceed to RAG retrieval
    """
    cleaned = question.strip().lower().rstrip("!?.")

    # 1. Fast heuristic for greetings & pleasantries
    if cleaned in _GREETING_KEYWORDS or any(cleaned.startswith(g + " ") for g in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]):
        if len(cleaned.split()) <= 6:
            return "GREETING"

    # 2. Fast LLM classifier fallback for meta-questions vs domain questions
    classify_prompt = (
        "You are a query classifier. Classify the user message into EXACTLY one category:\n"
        "META: The user is explicitly asking about the ongoing chat history, past conversation turns, what was asked earlier, or asking to repeat or summarize prior turns (e.g. 'what was my first question?', 'what did I ask earlier?', 'repeat your previous answer', 'what did you say?').\n"
        "DOMAIN: The user is asking a domain, factual, document, policy, legal, or general knowledge question (e.g. 'what are EPRA responsibilities?', 'what is solar energy?', 'what is the capital of France?').\n\n"
        f"User Message: \"{question}\"\n\n"
        "Respond with ONLY 'META' or 'DOMAIN':"
    )

    try:
        response = _client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": classify_prompt}],
            temperature=0.0,
            max_tokens=10,
        )
        res_text = response.choices[0].message.content.strip().upper()
        if res_text.startswith("META") or "META" in res_text:
            return "META"
    except Exception:
        pass

    return "DOMAIN"


def generate_conversational_response(question: str, history: list[dict] | None = None) -> str:
    """
    Generates a natural conversational reply for greetings or meta-questions,
    using conversation history if available, without querying vector DB.
    """
    system_instruction = (
        "You are GridMind AI, an expert assistant on Kenyan energy legislation and policy.\n"
        "Answer conversational greetings, pleasantries, or questions about the conversation history "
        "naturally, politely, and concisely. If asked about previous questions or turns, use the "
        "PREVIOUS CONVERSATION history to accurately answer. Do not invent facts, and do not cite document numbers."
    )

    convo_history = ""
    if history:
        convo_lines = [f"{t['role'].upper()}: {t['text']}" for t in history]
        convo_history = "PREVIOUS CONVERSATION:\n" + "\n".join(convo_lines) + "\n\n"

    prompt = f"{system_instruction}\n\n{convo_history}USER: {question}\nASSISTANT:"

    try:
        response = _client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "Hello! How can I help you today regarding Kenyan energy policy?"


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