/**
 * server.js  —  GridMind AI  |  Node.js Gateway
 * ─────────────────────────────────────────────
 * What changed from the original:
 *   REMOVED  → OpenAI import and API call
 *   ADDED    → axios forwarding to Python RAG service (port 8000)
 *   ADDED    → GET /health endpoint (frontend uses this for RAG badge)
 *   KEPT     → Express, CORS, JSON middleware, port 5000
 *
 * Request flow:
 *   Browser  →  POST /chat  →  Node (port 5000)
 *                           →  Python RAG service (port 8000)
 *                           →  ChromaDB + Mistral
 *                           ←  { answer, sources }
 *                           ←  forwarded back to browser
 */

require('dotenv').config();
const express = require('express');
const cors    = require('cors');
const axios   = require('axios');
const path    = require('path');

const app = express();

// ── Middleware ────────────────────────────────────────────────────────────────

app.use(cors());
app.use(express.json());

// Serve the frontend files from the frontend/ folder
app.use(express.static(path.join(__dirname, '..', 'frontend')));


// ── Config ────────────────────────────────────────────────────────────────────

const NODE_PORT   = process.env.PORT        || 5000;
const PYTHON_URL  = process.env.RAG_SERVICE_URL || process.env.PYTHON_URL || 'http://localhost:8000';


// ── Routes ────────────────────────────────────────────────────────────────────

/**
 * GET /health
 * Forwards the Python service health check to the frontend.
 * The frontend uses the response to show/hide the RAG badge.
 */
app.get('/health', async (req, res) => {
    try {
        const response = await axios.get(`${PYTHON_URL}/health`, { timeout: 5000 });
        res.json(response.data);
    } catch (err) {
        // Python service is not running — return degraded status gracefully
        res.json({ status: 'degraded', rag: false, llm: false });
    }
});


/**
 * DELETE /session/:id
 * Clears backend conversation memory for a session (called on "New chat").
 */
app.delete('/session/:id', async (req, res) => {
    try {
        await axios.delete(`${PYTHON_URL}/session/${req.params.id}`, { timeout: 5000 });
        res.json({ status: 'cleared' });
    } catch (err) {
        // Non-critical — the frontend already wiped its own UI state
        res.json({ status: 'cleared' });
    }
});


/**
 * POST /chat
 * Main endpoint called by the frontend.
 *
 * Accepts:  { question: string }   (RAG shape)
 *        or { message:  string }   (legacy shape — kept for compatibility)
 *
 * Returns:  { answer: string, sources: Array }
 *        or { reply: string }  on fallback error
 */
app.post('/chat', async (req, res) => {
    try {
        // Accept both 'question' (new RAG shape) and 'message' (old shape)
        const question  = req.body.question || req.body.message;
        const sessionId = req.body.session_id || null;

        if (!question || !question.trim()) {
            return res.status(400).json({ reply: 'Please enter a question.' });
        }

        // Forward to Python RAG service
        const response = await axios.post(
            `${PYTHON_URL}/chat`,
            { question: question.trim(), session_id: sessionId },
            { timeout: 120_000 }   // 2 minutes — Mistral can be slow on first load
        );

        // Forward the full RAG response: { answer, sources }
        res.json(response.data);

    } catch (error) {

        // ── Python service is down ────────────────────────────────────────────
        if (error.code === 'ECONNREFUSED' || error.code === 'ECONNRESET') {
            console.error('[GridMind] Python RAG service not reachable.');
            return res.status(503).json({
                reply: 'The RAG service is not running. '
                     + 'Please start it with:  uvicorn main:app --port 8000'
            });
        }

        // ── Python service returned an error ──────────────────────────────────
        if (error.response) {
            const detail = error.response.data?.detail || 'Unknown error from RAG service.';
            console.error('[GridMind] Python error:', detail);
            return res.status(error.response.status).json({ reply: detail });
        }

        // ── Timeout ───────────────────────────────────────────────────────────
        if (error.code === 'ECONNABORTED') {
            console.error('[GridMind] Request timed out.');
            return res.status(504).json({
                reply: 'The request timed out. Mistral may still be loading — please try again.'
            });
        }

        // ── Unexpected ────────────────────────────────────────────────────────
        console.error('[GridMind] Unexpected error:', error.message);
        res.status(500).json({ reply: 'An unexpected server error occurred.' });
    }
});


// ── Start ─────────────────────────────────────────────────────────────────────

app.listen(NODE_PORT, () => {
    console.log('');
    console.log('  ┌─────────────────────────────────────────┐');
    console.log('  │         GridMind AI  —  Node Server     │');
    console.log('  ├─────────────────────────────────────────┤');
    console.log(`  │  Frontend  →  http://localhost:${NODE_PORT}      │`);
    console.log(`  │  RAG svc   →  ${PYTHON_URL}  │`);
    console.log('  └─────────────────────────────────────────┘');
    console.log('');
});
