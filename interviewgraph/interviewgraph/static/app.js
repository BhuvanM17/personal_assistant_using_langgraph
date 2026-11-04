'use strict';
const $ = (id) => document.getElementById(id);
let topic = 'python';
let session = null;
let busy = false;

function showError(message) {
  $('error').textContent = message;
  $('error').classList.toggle('hidden', !message);
}

async function api(path, options = {}) {
  const response = await fetch(path, { ...options, headers: { 'Content-Type': 'application/json', ...options.headers } });
  const data = await response.json();
  if (!response.ok) {
    const message = typeof data.detail === 'string' ? data.detail : 'Please check your input and try again.';
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return data;
}

function saveSession() {
  try { localStorage.setItem('interviewgraph-session', session.id); } catch (_) { /* Private mode can disable storage. */ }
}

function renderList(id, values, emptyText) {
  const list = $(id);
  list.replaceChildren();
  for (const value of values.length ? values : [emptyText]) {
    const item = document.createElement('li');
    item.textContent = value;
    list.appendChild(item);
  }
}

function renderHistory() {
  $('history').replaceChildren();
  $('history-section').classList.toggle('hidden', !session.history.length);
  for (const entry of [...session.history].reverse()) {
    const details = document.createElement('details');
    const summary = document.createElement('summary');
    summary.textContent = `Question ${entry.question_number} · Attempt ${entry.attempt} — ${entry.score}/10`;
    details.appendChild(summary);
    for (const [label, content] of [['Question', entry.question], ['Your answer', entry.answer], ['Feedback', entry.feedback], ['Reference', entry.reference]]) {
      const heading = document.createElement('h4');
      heading.textContent = label;
      const paragraph = document.createElement('p');
      paragraph.textContent = content;
      details.append(heading, paragraph);
    }
    $('history').appendChild(details);
  }
}

function render() {
  if (!session) return;
  $('setup').classList.add('hidden');
  $('interview').classList.toggle('hidden', session.finished);
  $('finished').classList.toggle('hidden', !session.finished);
  $('question-label').textContent = `QUESTION ${String(session.question_number).padStart(2, '0')} OF ${String(session.total_questions).padStart(2, '0')}${session.attempt ? ' · FOLLOW-UP' : ''}`;
  $('question-topic').textContent = session.topic_label;
  $('question').textContent = session.question || '';
  $('progress').style.width = `${session.finished ? 100 : ((session.question_number - 1) / session.total_questions) * 100}%`;
  $('answer').value = '';
  $('word-count').textContent = '0 words';
  $('empty-feedback').classList.toggle('hidden', !!session.review);
  $('feedback').classList.toggle('hidden', !session.review);
  if (session.review) {
    $('score').textContent = session.review.score;
    $('score-label').textContent = session.mode === 'demo' ? 'keyword coverage' : 'AI feedback';
    $('feedback-text').textContent = session.review.feedback;
    renderList('strengths', session.review.strengths, 'A starting point to build on.');
    renderList('gaps', session.review.gaps, 'Try one concrete example.');
    $('reference').textContent = session.history[session.history.length - 1].reference;
  }
  document.querySelectorAll('[data-node]').forEach((node) => node.classList.toggle('active', session.trace.includes(node.dataset.node)));
  $('trace-caption').textContent = session.trace.length ? `Last run: ${session.trace.join(' → ')} → wait for you${session.finished ? ' (session complete)' : ''}` : 'Submit an answer to see the nodes your session visits.';
  const reportUrl = `/api/sessions/${encodeURIComponent(session.id)}/report`;
  $('download').href = reportUrl;
  $('history-report').href = reportUrl;
  if (session.finished) {
    $('final-score').textContent = `${session.mode === 'demo' ? 'Demo keyword coverage' : 'AI practice score'}: ${session.average_score}/10 average across the latest attempt for each question.`;
  }
  renderHistory();
}

document.querySelectorAll('[data-topic]').forEach((button) => button.addEventListener('click', () => {
  topic = button.dataset.topic;
  document.querySelectorAll('[data-topic]').forEach((item) => {
    const active = item === button;
    item.classList.toggle('active', active);
    item.setAttribute('aria-pressed', String(active));
  });
}));

$('start').addEventListener('click', async () => {
  if (busy) return;
  busy = true;
  $('start').disabled = true;
  showError('');
  $('saved-draft').classList.add('hidden');
  try {
    session = await api('/api/sessions', { method: 'POST', body: JSON.stringify({ topic }) });
    saveSession();
    render();
    $('question').focus();
  } catch (error) { showError(error.message); }
  finally { busy = false; $('start').disabled = false; }
});

$('submit').addEventListener('click', async () => {
  if (busy || !session) return;
  const answer = $('answer').value.trim();
  if (!answer) { showError('Write a short answer first. An honest attempt is enough.'); $('answer').focus(); return; }
  busy = true;
  $('submit').disabled = true;
  $('submit').textContent = 'Reviewing…';
  $('answer').disabled = true;
  showError('');
  try {
    session = await api(`/api/sessions/${encodeURIComponent(session.id)}/answers`, {
      method: 'POST', body: JSON.stringify({ answer, version: session.version }),
    });
    render();
    if (!session.finished) $('question').focus();
  } catch (error) {
    if (error.status === 409) {
      try { session = await api(`/api/sessions/${encodeURIComponent(session.id)}`); render(); } catch (_) { /* Keep original error. */ }
      $('draft-answer').value = answer;
      $('saved-draft').classList.remove('hidden');
    }
    showError(error.message);
  } finally {
    busy = false;
    $('submit').disabled = false;
    $('submit').textContent = 'Review my answer →';
    $('answer').disabled = false;
  }
});

$('answer').addEventListener('input', () => {
  const text = $('answer').value.trim();
  $('word-count').textContent = `${text ? text.split(/\s+/).length : 0} words`;
});

$('again').addEventListener('click', () => {
  session = null;
  try { localStorage.removeItem('interviewgraph-session'); } catch (_) { /* Storage is optional. */ }
  $('setup').classList.remove('hidden');
  $('finished').classList.add('hidden');
  $('interview').classList.add('hidden');
  $('history-section').classList.add('hidden');
  document.querySelectorAll('[data-node]').forEach((node) => node.classList.remove('active'));
  $('trace-caption').textContent = 'Submit an answer to see the nodes your session visits.';
  showError('');
  $('saved-draft').classList.add('hidden');
  $('setup').scrollIntoView({ behavior: 'smooth' });
});

(async function initialize() {
  try {
    const config = await api('/api/config');
    $('mode-badge').textContent = config.mode === 'demo' ? '● Demo mode · no API key' : '● Gemini AI configured';
    $('notice').textContent = config.mode === 'demo'
      ? 'Demo mode uses keyword coverage, not AI grading. Add your Gemini key and set COACH_MODE=gemini for AI feedback.'
      : 'Gemini mode is configured. Your answers are reviewed by AI and may contain mistakes. Use feedback as practice guidance.';
    $('start').disabled = false;
    let stored = null;
    try { stored = localStorage.getItem('interviewgraph-session'); } catch (_) { /* Storage is optional. */ }
    if (stored) {
      try {
        const previous = await api(`/api/sessions/${encodeURIComponent(stored)}`);
        if (previous.mode === config.mode) { session = previous; render(); }
      } catch (error) { if (error.status !== 404) throw error; }
    }
  } catch (error) { showError(`Cannot connect to the coach. ${error.message}`); $('mode-badge').textContent = 'Connection unavailable'; }
})();
