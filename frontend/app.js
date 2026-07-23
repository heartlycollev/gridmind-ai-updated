/* ─────────────────────────────────────────
   GRIDMIND AI — app.js
   Connects to FastAPI RAG backend at localhost:5000
   API shape:  POST /chat  { question }  →  { answer, sources }
               GET  /health              →  { rag: true }
───────────────────────────────────────── */

const API_BASE = window.location.origin;

/* ── DOM refs ─────────────────────────── */
const msgsEl       = document.getElementById('gm-msgs');
const inputEl      = document.getElementById('gm-input');
const suggsEl      = document.getElementById('gm-suggs');
const chatTitleEl  = document.getElementById('gm-chat-title');
const histListEl   = document.getElementById('gm-hist-list');
const navListEl    = document.getElementById('gm-nav-list');
const ragPill      = document.getElementById('gm-rag-pill');
const hamburger    = document.getElementById('gm-hamburger');
const leftPanel    = document.getElementById('gm-panel');
const docsTrigger  = document.getElementById('gm-docs-trigger');
const docsPanel    = document.getElementById('gm-docs-panel');
const newBtn       = document.getElementById('gm-new-btn');
const rightTrigger = document.getElementById('gm-right-trigger');
const rightPanel   = document.getElementById('gm-right-panel');
const sendBtn      = document.getElementById('gm-send');
const backdrop     = document.getElementById('gm-mobile-backdrop');

/* True on touch/coarse-pointer devices (phones, most tablets).
   Used to bypass hover-based open/close logic, which is unreliable
   on touch — mobile WebKit browsers can require a second tap to fire
   click on elements with :hover-styled children, and mouseleave
   doesn't fire on touch at all. Touch devices get direct tap-toggle
   plus an explicit backdrop instead. */
const isTouchDevice = !window.matchMedia('(hover: hover) and (pointer: fine)').matches;

/* ── Source Excerpt Modal DOM refs ────── */
const modalOverlay = document.getElementById('gm-modal-overlay');
const modalDoc     = document.getElementById('gm-modal-doc');
const modalBadge   = document.getElementById('gm-modal-badge');
const modalFile    = document.getElementById('gm-modal-file');
const modalPage    = document.getElementById('gm-modal-page');
const modalExcerpt = document.getElementById('gm-modal-excerpt');
const modalClose   = document.getElementById('gm-modal-close');

/* ── Modal logic ──────────────────────── */
function openSourceModal(source) {
  if (!source) return;
  const docTitle = source.document || source.doc || (source.filename || source.source || 'Document').replace('.pdf', '').replace(/_/g, ' ');
  const fileName = source.filename || source.source || 'Unknown file';
  const pageNum  = source.page || 1;
  const indexNum = source.index || '?';
  const excerpt  = source.excerpt || 'No text excerpt available for this source.';

  if (modalDoc)     modalDoc.textContent     = docTitle;
  if (modalBadge)   modalBadge.textContent   = `Ref [${indexNum}]`;
  if (modalFile)    modalFile.textContent    = fileName;
  if (modalPage)    modalPage.textContent    = `Page ${pageNum}`;
  if (modalExcerpt) modalExcerpt.textContent = excerpt;

  if (modalOverlay) modalOverlay.style.display = 'flex';
}

function closeModal() {
  if (modalOverlay) modalOverlay.style.display = 'none';
}

if (modalClose) modalClose.addEventListener('click', closeModal);
if (modalOverlay) {
  modalOverlay.addEventListener('click', (e) => {
    if (e.target === modalOverlay) closeModal();
  });
}
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();
});


/* ── Feature 2: Follow-Up Suggestion Generator ──────────────── */
const DEFAULT_SUGGESTIONS = [
  "What are EPRA's regulatory responsibilities?",
  "What incentives exist for solar energy in Kenya?",
  "What licence is needed to distribute electricity?"
];

function generateSuggestions(sources) {
  if (!sources || sources.length === 0) {
    return DEFAULT_SUGGESTIONS;
  }

  const docNames = [...new Set(sources.map(s => s.document || s.doc).filter(Boolean))];
  const primaryDoc = docNames[0] || "the documents";
  const primaryPage = sources[0]?.page || 1;

  const suggestions = [
    `Tell me more about what is inside ${primaryDoc}`,
    `What else is mentioned on page ${primaryPage} of ${primaryDoc}?`,
    `Can you summarize the context you just used?`
  ];

  if (docNames.length > 1) {
    suggestions[2] = `How does ${docNames[0]} compare with ${docNames[1]}?`;
  }

  return suggestions;
}

function updateSuggestions(sources = []) {
  const list = generateSuggestions(sources);
  suggsEl.innerHTML = '';
  list.forEach((text, i) => {
    const btn = document.createElement('button');
    btn.className = 'gm-sugg';
    btn.style.animationDelay = `${i * 0.06}s`;
    btn.textContent = text;
    btn.addEventListener('click', () => useSuggestion(text));
    suggsEl.appendChild(btn);
  });
  suggsEl.style.display = 'flex';
}

function showSuggestions() {
  if (!suggsEl.children.length) {
    updateSuggestions([]);
  }
  suggsEl.style.display = 'flex';
}

function hideSuggestions() {
  suggsEl.style.display = 'none';
}

function useSuggestion(text) {
  inputEl.value = text;
  autoResize();
  hideSuggestions();
  sendMessage();
}


/* ── RAG health check ─────────────────── */
async function checkRagStatus() {
  try {
    const res  = await fetch(`${API_BASE}/health`, { method: 'GET' });
    const data = await res.json();
    if (data.rag === true) {
      ragPill.style.display = 'flex';
    }
  } catch (_) {
    /* service offline — pill stays hidden, app degrades gracefully */
  }
}
checkRagStatus();

/* ── Panel open/close helpers (shared by all three panels) ── */
function closeAllPanels() {
  leftPanel.classList.remove('open');
  hamburger.classList.remove('hovered');
  rightPanel.classList.remove('open');
  rightTrigger.classList.remove('hovered');
  if (docsPanel)   docsPanel.classList.remove('open');
  if (docsTrigger) docsTrigger.classList.remove('hovered');
  if (backdrop) backdrop.classList.remove('open');
}

function openPanel(panelEl, triggerEl) {
  closeAllPanels();
  panelEl.classList.add('open');
  triggerEl.classList.add('hovered');
  if (isTouchDevice && backdrop) backdrop.classList.add('open');
}

/* Tapping the backdrop (mobile only, sits behind whichever panel is open) dismisses it */
if (backdrop) {
  backdrop.addEventListener('click', closeAllPanels);
}

/* ── Left panel (chat history) ────────── */
let leftTimer = null;

function openLeft() {
  clearTimeout(leftTimer);
  openPanel(leftPanel, hamburger);
}

function scheduleCloseLeft() {
  leftTimer = setTimeout(() => {
    leftPanel.classList.remove('open');
    hamburger.classList.remove('hovered');
  }, 120);
}

if (isTouchDevice) {
  /* Touch: single tap opens directly. No hover, no double-tap, no timers. */
  hamburger.addEventListener('click', () => {
    if (leftPanel.classList.contains('open')) {
      closeAllPanels();
    } else {
      openLeft();
    }
  });
} else {
  hamburger.addEventListener('mouseenter', openLeft);
  hamburger.addEventListener('mouseleave', scheduleCloseLeft);
  hamburger.addEventListener('click', () => {
    if (leftPanel.classList.contains('open')) {
      leftPanel.classList.remove('open');
      hamburger.classList.remove('hovered');
    } else {
      openLeft();
    }
  });
  leftPanel.addEventListener('mouseenter', () => clearTimeout(leftTimer));
  leftPanel.addEventListener('mouseleave', scheduleCloseLeft);
}

/* ── Right panel (in-chat navigator) ──── */
let rightTimer = null;

function openRight() {
  clearTimeout(rightTimer);
  openPanel(rightPanel, rightTrigger);
}

function scheduleCloseRight() {
  rightTimer = setTimeout(() => {
    rightPanel.classList.remove('open');
    rightTrigger.classList.remove('hovered');
  }, 120);
}

if (isTouchDevice) {
  rightTrigger.addEventListener('click', () => {
    if (rightPanel.classList.contains('open')) {
      closeAllPanels();
    } else {
      openRight();
    }
  });
} else {
  rightTrigger.addEventListener('mouseenter', openRight);
  rightTrigger.addEventListener('mouseleave', scheduleCloseRight);
  rightPanel.addEventListener('mouseenter', () => clearTimeout(rightTimer));
  rightPanel.addEventListener('mouseleave', scheduleCloseRight);
}

/* ── Source Documents Panel ───────────── */
let docsTimer = null;

function openDocs() {
  clearTimeout(docsTimer);
  if (docsPanel && docsTrigger) openPanel(docsPanel, docsTrigger);
}

function scheduleCloseDocs() {
  docsTimer = setTimeout(() => {
    if (docsPanel) docsPanel.classList.remove('open');
    if (docsTrigger) docsTrigger.classList.remove('hovered');
  }, 160);
}

if (docsTrigger) {
  if (isTouchDevice) {
    docsTrigger.addEventListener('click', () => {
      if (docsPanel.classList.contains('open')) {
        closeAllPanels();
      } else {
        openDocs();
      }
    });
  } else {
    docsTrigger.addEventListener('mouseenter', openDocs);
    docsTrigger.addEventListener('mouseleave', scheduleCloseDocs);
    docsTrigger.addEventListener('click', () => {
      if (docsPanel.classList.contains('open')) {
        docsPanel.classList.remove('open');
        docsTrigger.classList.remove('hovered');
      } else {
        openDocs();
      }
    });
  }
}

if (docsPanel && !isTouchDevice) {
  docsPanel.addEventListener('mouseenter', () => clearTimeout(docsTimer));
  docsPanel.addEventListener('mouseleave', scheduleCloseDocs);
}

/* Bind all .gm-doc-q buttons inside docsPanel to click-to-ask */
document.querySelectorAll('.gm-doc-q').forEach(btn => {
  btn.addEventListener('click', () => {
    const questionText = btn.textContent.trim();
    if (questionText) {
      closeAllPanels();
      useSuggestion(questionText);
    }
  });
});

/* ── New chat button ──────────────────── */
newBtn.addEventListener('click', startNewChat);

function startNewChat() {
  if (currentSessionId) {
    fetch(`${API_BASE}/session/${currentSessionId}`, { method: 'DELETE' }).catch(() => {});
  }

  currentSessionId = Date.now();
  chatTitleEl.textContent = '';
  msgsEl.innerHTML = '';
  showEmptyState();
  updateSuggestions([]);
  renderNav();
}

/* ── Session history (in-memory) ─────── */
const sessions    = [];   /* [{ id, title, msgs: [] }] */
let   currentSessionId = null;

function getCurrentSession() {
  return sessions.find(s => s.id === currentSessionId);
}

function ensureSession(firstQuestion) {
  let session = getCurrentSession();
  if (!session) {
    session = {
      id:    currentSessionId || (currentSessionId = Date.now()),
      title: firstQuestion.length > 42
               ? firstQuestion.slice(0, 42) + '…'
               : firstQuestion,
      msgs:  [],
    };
    sessions.unshift(session);
    renderHistory();
  }
  return session;
}

function renderHistory() {
  histListEl.innerHTML = '';

  if (sessions.length === 0) {
    const empty = document.createElement('div');
    empty.style.cssText = 'padding:12px 14px;font-size:11.5px;color:#444;font-style:italic;';
    empty.textContent = 'No previous chats yet';
    histListEl.appendChild(empty);
    return;
  }

  const todayLabel    = document.createElement('div');
  todayLabel.className = 'gm-hist-group-label';
  todayLabel.textContent = 'Recent';
  histListEl.appendChild(todayLabel);

  sessions.forEach(s => {
    const row = document.createElement('div');
    row.className = 'gm-hist-item' + (s.id === currentSessionId ? ' active' : '');
    row.innerHTML = `<i class="ti ti-message"></i><span class="gm-hist-text">${escHtml(s.title)}</span>`;
    row.addEventListener('click', () => restoreSession(s.id));
    histListEl.appendChild(row);
  });
}

function restoreSession(id) {
  const session = sessions.find(s => s.id === id);
  if (!session) return;

  currentSessionId = id;
  chatTitleEl.textContent = session.title;
  msgsEl.innerHTML = '';
  removeEmptyState();

  let lastBotSources = [];
  session.msgs.forEach(m => {
    if (m.role === 'user') {
      appendUserBubble(m.text, false);
    } else {
      lastBotSources = m.sources || [];
      appendBotBubble(m.text, m.sources, false);
    }
  });

  updateSuggestions(lastBotSources);
  renderNav();
  renderHistory();
}

/* ── Right-side navigator ─────────────── */
function renderNav() {
  navListEl.innerHTML = '';
  const userBlocks = [...msgsEl.querySelectorAll('.gm-msg-block.user')];

  if (!userBlocks.length) {
    const empty = document.createElement('div');
    empty.className = 'gm-nav-empty';
    empty.textContent = 'No questions yet';
    navListEl.appendChild(empty);
    return;
  }

  userBlocks.forEach((block, idx) => {
    const text = block.querySelector('.gm-bubble')?.textContent || '';
    const item = document.createElement('div');
    item.className = 'gm-nav-item';
    item.innerHTML = `<span class="gm-nav-num">${idx + 1}</span><span class="gm-nav-text">${escHtml(text)}</span>`;
    item.addEventListener('click', () => {
      block.scrollIntoView({ behavior: 'smooth', block: 'center' });
      block.classList.add('highlight');
      setTimeout(() => block.classList.remove('highlight'), 1800);
      scheduleCloseRight();
    });
    navListEl.appendChild(item);
  });
}

/* ── Empty state helpers ──────────────── */
function removeEmptyState() {
  const el = document.getElementById('gm-empty');
  if (el) el.remove();
}

function showEmptyState() {
  if (document.getElementById('gm-empty')) return;
  const el = document.createElement('div');
  el.className = 'gm-empty-state';
  el.id = 'gm-empty';
  el.innerHTML = `
    <div class="gm-empty-icon"><i class="ti ti-bolt"></i></div>
    <p class="gm-empty-title">Ask about Kenyan energy law</p>
    <p class="gm-empty-sub">Answers sourced from the Energy Act 2019, EPRA documents, and official policy</p>
  `;
  msgsEl.appendChild(el);
}

/* ── Message rendering ────────────────── */
function appendUserBubble(text, save = true) {
  const row = document.createElement('div');
  row.className = 'gm-msg-block user';
  row.innerHTML = `<span class="gm-msg-label">You</span><div class="gm-bubble">${escHtml(text)}</div>`;
  msgsEl.appendChild(row);
  msgsEl.scrollTop = msgsEl.scrollHeight;

  if (save) {
    const session = ensureSession(text);
    session.msgs.push({ role: 'user', text });
  }

  renderNav();
  return row;
}

function appendBotBubble(text, sources = [], save = true) {
  const notFound = text.toLowerCase().includes('could not find');

  const row = document.createElement('div');
  row.className = 'gm-msg-block bot';

  const bubble = document.createElement('div');
  bubble.className = 'gm-bubble' + (notFound ? ' not-found' : '');

  // 1. Render Markdown
  let htmlContent = renderMarkdown(text);

  // 2. Scan & convert inline citation markers like [1], [2] to clickable badges
  htmlContent = htmlContent.replace(/\[(\d+)\]/g, (match, numStr) => {
    const idx = parseInt(numStr, 10);
    return `<button class="gm-citation-badge" data-index="${idx}">[${idx}]</button>`;
  });

  bubble.innerHTML = htmlContent;

  // 3. Attach click handlers to inline citation badges
  const inlineBadges = bubble.querySelectorAll('.gm-citation-badge');
  inlineBadges.forEach(badge => {
    badge.addEventListener('click', (e) => {
      e.stopPropagation();
      const idx = parseInt(badge.getAttribute('data-index'), 10);
      const sourceObj = sources.find(s => s.index === idx) || sources[idx - 1];
      if (sourceObj) {
        openSourceModal(sourceObj);
      }
    });
  });

  row.innerHTML = `<span class="gm-msg-label">GridMind AI</span>`;
  row.appendChild(bubble);
  msgsEl.appendChild(row);

  /* 4. Render secondary source chips below answer */
  if (sources && sources.length > 0) {
    const citesBlock = buildCitations(sources);
    if (citesBlock) msgsEl.appendChild(citesBlock);
  }

  msgsEl.scrollTop = msgsEl.scrollHeight;

  if (save) {
    const session = getCurrentSession();
    if (session) session.msgs.push({ role: 'bot', text, sources: sources || [] });
  }
}

function buildCitations(sources) {
  if (!sources || sources.length === 0) return null;

  const block = document.createElement('div');
  block.className = 'gm-cites';

  const label = document.createElement('span');
  label.className = 'gm-cites-label';
  label.textContent = 'Sources';
  block.appendChild(label);

  const seen = new Set();
  sources.forEach(s => {
    const docName = s.document || s.doc || (s.filename || s.source || '').replace('.pdf', '').replace(/_/g, ' ');
    const key = `${docName}:${s.page}`;
    if (seen.has(key)) return;
    seen.add(key);

    const chip = document.createElement('span');
    chip.className = 'gm-chip';
    const indexLabel = s.index ? `[${s.index}] ` : '';
    chip.textContent = `${indexLabel}${docName} · p. ${s.page}`;
    chip.title = "Click to view verbatim excerpt";
    chip.addEventListener('click', () => openSourceModal(s));
    block.appendChild(chip);
  });

  return block;
}

function showTyping() {
  const t = document.createElement('div');
  t.className = 'gm-typing-block';
  t.id = 'gm-typing-' + Date.now();
  t.innerHTML = `
    <span class="gm-typing-label">GridMind AI</span>
    <div class="gm-typing-bubble"><span></span><span></span><span></span></div>
  `;
  msgsEl.appendChild(t);
  msgsEl.scrollTop = msgsEl.scrollHeight;
  return t;
}

/* ── Send message ─────────────────────── */
async function sendMessage() {
  const message = inputEl.value.trim();
  if (!message) return;

  removeEmptyState();
  hideSuggestions();

  appendUserBubble(message);
  inputEl.value = '';
  autoResize();

  /* update topbar title to first question if brand new chat */
  const session = getCurrentSession();
  if (session && session.msgs.length === 1) {
    chatTitleEl.textContent = session.title;
    renderHistory();
  }

  const typingEl = showTyping();

  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ question: message, session_id: String(currentSessionId) }),
    });

    typingEl.remove();

    if (!response.ok) {
      throw new Error(`Server responded ${response.status}`);
    }

    const data = await response.json();
    const answerText = data.answer || data.reply || 'No response generated.';
    const sources    = data.sources || [];

    appendBotBubble(answerText, sources);
    updateSuggestions(sources);

  } catch (err) {
    typingEl.remove();

    const errRow = document.createElement('div');
    errRow.className = 'gm-msg-block bot';
    errRow.innerHTML = `
      <span class="gm-msg-label">GridMind AI</span>
      <div class="gm-bubble error">Could not reach the server. Make sure both servers are running.</div>
    `;
    msgsEl.appendChild(errRow);
    msgsEl.scrollTop = msgsEl.scrollHeight;
    updateSuggestions([]);
  }
}

/* ── Input events ─────────────────────── */
function autoResize() {
  inputEl.style.height = 'auto';
  inputEl.style.height = Math.min(inputEl.scrollHeight, 110) + 'px';
}

inputEl.addEventListener('input', () => {
  autoResize();
  inputEl.value.trim() === '' ? showSuggestions() : hideSuggestions();
});

inputEl.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

if (isTouchDevice) {
  /* Touch devices: single tap fires immediately on touchend, preventing hover delays */
  sendBtn.addEventListener('touchend', (e) => {
    e.preventDefault();
    sendMessage();
  });
} else {
  sendBtn.addEventListener('click', sendMessage);
}

/* ── Markdown rendering (bot answers only — user input stays escaped text) ── */
if (window.marked) {
  marked.setOptions({ breaks: true, gfm: true });
}

function renderMarkdown(text) {
  if (!window.marked || !window.DOMPurify) {
    return escHtml(text);
  }
  const rawHtml = marked.parse(text);
  return DOMPurify.sanitize(rawHtml);
}

/* ── Utility ──────────────────────────── */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ── Init ─────────────────────────────── */
renderHistory();
renderNav();
updateSuggestions([]);