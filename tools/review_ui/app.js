'use strict';

/* review-ui: keyboard-first labelling over a review pack. */

const $ = (sel) => document.querySelector(sel);

const S = {
  state: null,
  ids: [],
  cur: 0,
  item: null,
  verdict: '',
  axis: '',
  path: '',
  pathValue: '',
  noteText: '',
  claims: [],
  accepted: new Set(),
  rejected: new Set(),
  claimCur: 0,
  hits: new Set(),
  activeToken: null,
  warnedBugNoAxis: false,
  busy: false,
};

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function shortJson(value) {
  if (value === undefined) return 'undefined';
  let text;
  try { text = JSON.stringify(value); } catch (err) { text = String(value); }
  if (text === undefined) text = String(value);
  return text.length > 200 ? text.slice(0, 199) + '…' : text;
}

function valueType(value) {
  if (value === null) return 'null';
  if (typeof value === 'number') return 'num';
  if (typeof value === 'boolean') return 'bool';
  if (typeof value === 'string') return 'str';
  return 'obj';
}

async function api(path, opts = {}) {
  const init = { method: opts.method || 'GET', headers: {} };
  if (opts.body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(opts.body);
  }
  let res;
  try {
    res = await fetch(path, init);
  } catch (err) {
    return { error: 'request failed: ' + err.message };
  }
  let data;
  try { data = await res.json(); } catch (err) { data = { error: 'malformed response (' + res.status + ')' }; }
  if (!res.ok && !data.error) data.error = 'HTTP ' + res.status;
  return data;
}

function status(msg, kind) {
  const el = $('#status');
  el.textContent = msg || '';
  el.className = 'status' + (kind ? ' ' + kind : '');
}

/* ---------------------------------------------------------------- state UI */

function renderTop() {
  const st = S.state;
  const c = st.counts;
  $('#packname').textContent = st.pack;
  $('#packname').title = st.pack;
  $('#counts').innerHTML =
    `<b>${c.done}</b>/${st.n} · ok ${c.ok} bug ${c.bug} legit ${c.legit}` +
    (c.imported ? ` · imported ${c.imported}` : '');
  $('#progressfill').style.width = (100 * c.done / Math.max(1, st.n)) + '%';
  const banner = $('#banner');
  const warnings = st.warnings || [];
  banner.textContent = '';
  warnings.forEach((text) => {
    const row = document.createElement('div');
    row.textContent = '⚠ ' + text;
    banner.appendChild(row);
  });
  banner.classList.toggle('hidden', warnings.length === 0);
  renderStrip();
}

function renderStrip() {
  const host = $('#batchstrip');
  host.textContent = '';
  const batch = S.state.batch;
  for (let start = 0; start < S.ids.length; start += batch) {
    const group = document.createElement('div');
    group.className = 'batch';
    const label = document.createElement('span');
    label.className = 'blabel';
    label.textContent = String(Math.floor(start / batch) + 1);
    group.appendChild(label);
    for (let i = start; i < Math.min(start + batch, S.ids.length); i++) {
      const entry = S.state.items[i];
      const cell = document.createElement('div');
      cell.className = 'cell ' + (entry.done ? entry.verdict : '') + (i === S.cur ? ' cur' : '');
      cell.title = `${entry.id} — ${entry.card}` + (entry.done ? ` [${entry.verdict}]` : '');
      cell.addEventListener('click', () => loadItem(i));
      group.appendChild(cell);
    }
    host.appendChild(group);
  }
  const cur = host.querySelector('.cell.cur');
  if (cur) cur.scrollIntoView({ block: 'nearest', inline: 'nearest' });
}

function renderItem() {
  const it = S.item;
  if (!it) return;
  document.title = `${it.id} — ${it.card} — review-ui`;
  $('#itemid').textContent = it.id;
  $('#cardname').textContent = it.card;
  const badge = $('#lanebadge');
  badge.className = 'lanebadge';
  badge.textContent = '';
  badge.title = '';
  if (it.lane) {
    badge.classList.add(it.lane);
    badge.textContent = it.lane;
    badge.title = it.lane === 'triage'
      ? 'triage lane: machine claims shown; lane was hidden until this item was labelled'
      : 'blind lane: no machine claims shown (measures the parser alone)';
  }
  renderSentence();
  $('#resolved').textContent = it.resolved_text || '(no substitution)';
  $('#resolvedwrap').hidden = !it.resolved_text || it.resolved_text === it.original_text;
  renderCardText();
  renderAnaphora();
  renderTree();
  renderClaims();
  renderVerdicts();
  renderSelection();
  renderNote();
  $('#tokeninfo').textContent = '';
  S.activeToken = null;
}

function renderSentence() {
  const host = $('#judged');
  host.textContent = '';
  const text = S.item.original_text || '';
  let pos = 0;
  for (const token of S.item.tokens) {
    if (token.start > pos) host.appendChild(document.createTextNode(text.slice(pos, token.start)));
    const span = document.createElement('span');
    span.className = 'tok ' + token.cls;
    span.dataset.start = String(token.start);
    span.textContent = text.slice(token.start, token.end);
    span.title = token.cls === 'function' ? 'function word (allowlist)'
      : token.cls === 'missing' ? 'content unit missing from the output'
        : 'content unit found in the output';
    span.addEventListener('click', () => showToken(token));
    host.appendChild(span);
    pos = token.end;
  }
  if (pos < text.length) host.appendChild(document.createTextNode(text.slice(pos)));
}

function showToken(token) {
  S.activeToken = token;
  document.querySelectorAll('#judged .tok').forEach((el) => {
    el.classList.toggle('active', Number(el.dataset.start) === token.start);
  });
  const host = $('#tokeninfo');
  host.textContent = '';
  if (token.cls === 'function') {
    host.append('function word — allowlisted, not content-tracked');
    S.hits = new Set();
    applyHighlights();
    return;
  }
  S.hits = new Set(token.hits || []);
  applyHighlights();
  if (!token.hits || token.hits.length === 0) {
    const span = document.createElement('span');
    span.className = 'none';
    span.textContent = `"${token.text}" did not land anywhere in the output`;
    host.appendChild(span);
  } else {
    host.append(`"${token.text}" landed at: `);
    token.hits.forEach((path, i) => {
      if (i) host.append('  ');
      const link = document.createElement('span');
      link.className = 'hitlink';
      link.textContent = path;
      link.addEventListener('click', () => reveal(path));
      host.appendChild(link);
    });
  }
}

function renderCardText() {
  const host = $('#cardtext');
  host.textContent = '';
  const it = S.item;
  for (const row of it.cards || []) {
    const line = document.createElement('div');
    const judgedText = it.original_text || '';
    const lineText = row.text || '';
    const isJudged = lineText === judgedText ||
      (judgedText && (lineText.includes(judgedText) || judgedText.includes(lineText)) &&
       lineText.length > 3) ||
      (row.sentence_index === it.sentence_index && !judgedText);
    line.className = 'ctx-line' + (isJudged ? ' judged' : '');
    const idx = document.createElement('span');
    idx.className = 'idx';
    idx.textContent = String(row.sentence_index);
    line.appendChild(idx);
    line.append(row.text);
    host.appendChild(line);
  }
  if (!(it.cards || []).length) host.textContent = '(no other sentences for this card in the artifact)';
}

function renderAnaphora() {
  const host = $('#anaphora');
  host.textContent = '';
  const rows = S.item.anaphora || [];
  $('#anaphorawrap').hidden = rows.length === 0;
  for (const row of rows) {
    const wrap = document.createElement('div');
    wrap.className = 'ana';
    const surface = document.createElement('span');
    surface.className = 'surface';
    surface.textContent = row.surface || '?';
    const rest = document.createElement('span');
    rest.textContent = `→ ${row.antecedent || '?'}`;
    const meta = document.createElement('span');
    meta.className = 'status';
    meta.textContent = [row.status, row.start != null ? `@${row.start}` : ''].filter(Boolean).join(' ');
    wrap.appendChild(surface);
    wrap.appendChild(rest);
    wrap.appendChild(meta);
    wrap.appendChild(document.createElement('span'));
    host.appendChild(wrap);
  }
}

/* ------------------------------------------------------------------- tree */

function buildNode(path, keyLabel, value, depth) {
  const isObj = value !== null && typeof value === 'object';
  if (!isObj) {
    const row = document.createElement('div');
    row.className = 'leaf';
    row.dataset.path = path;
    row.dataset.value = shortJson(value);
    row.innerHTML = (keyLabel !== null
      ? `<span class="k">${esc(keyLabel)}</span>: ` : '') +
      `<span class="v ${valueType(value)}">${esc(shortJson(value))}</span>`;
    return row;
  }
  const det = document.createElement('details');
  det.dataset.path = path;
  det.dataset.value = shortJson(value);
  if (depth < 2) det.open = true;
  const summary = document.createElement('summary');
  const size = Array.isArray(value) ? `[${value.length}]` : `{${Object.keys(value).length}}`;
  summary.innerHTML = (keyLabel !== null
    ? `<span class="${/^\[\d+\]$/.test(keyLabel) ? 'idx' : 'k'}">${esc(keyLabel)}</span> `
    : '') + `<span class="idx">${size}</span>`;
  det.appendChild(summary);
  const kids = document.createElement('div');
  if (Array.isArray(value)) {
    value.forEach((child, i) => kids.appendChild(buildNode(`${path}[${i}]`, `[${i}]`, child, depth + 1)));
  } else {
    for (const [key, child] of Object.entries(value)) {
      kids.appendChild(buildNode(`${path}.${key}`, key, child, depth + 1));
    }
  }
  det.appendChild(kids);
  return det;
}

function renderTree() {
  const host = $('#tree');
  host.textContent = '';
  if (S.item.output === null || S.item.output === undefined) {
    host.textContent = '(no output)';
    return;
  }
  host.appendChild(buildNode('$', null, S.item.output, 0));
  applyHighlights();
  if (S.path) reveal(S.path, false);
}

function reveal(path, scroll = true) {
  const el = document.querySelector(`#tree [data-path="${CSS.escape(path)}"]`);
  if (!el) return false;
  let node = el;
  while (node) {
    if (node.tagName === 'DETAILS') node.open = true;
    node = node.parentElement;
  }
  if (scroll) el.scrollIntoView({ block: 'nearest' });
  document.querySelectorAll('#tree [data-path]').forEach((n) => n.classList.remove('sel'));
  el.classList.add('sel');
  return true;
}

function applyHighlights() {
  document.querySelectorAll('#tree .hit').forEach((el) => el.classList.remove('hit'));
  if (!S.hits || !S.hits.size) return;
  for (const path of S.hits) {
    const el = document.querySelector(`#tree [data-path="${CSS.escape(path)}"]`);
    if (el) el.classList.add('hit');
  }
}

function selectPath(path, valueJson) {
  S.path = path || '';
  S.pathValue = valueJson || '';
  if (S.verdict !== 'bug') S.verdict = 'bug';
  S.hits = new Set(path ? [path] : []);
  applyHighlights();
  reveal(path);
  renderVerdicts();
  renderSelection();
  renderNote();
}

/* ----------------------------------------------------------------- claims */

function renderClaims() {
  const host = $('#claims');
  host.textContent = '';
  const claims = S.claims || [];
  const sources = [...new Set(claims.map((c) => c.source).filter(Boolean))];
  const mode = S.state ? S.state.claims_mode : '';
  $('#claimssrc').textContent = sources.length ? sources.join(', ')
    : (mode === 'none' ? 'unavailable' : mode === 'tsv' ? 'audit TSVs' : '');
  if (!claims.length) {
    const div = document.createElement('div');
    div.className = 'noclaims';
    const mode = S.state ? S.state.claims_mode : '';
    div.textContent = mode === 'none'
      ? 'machine claims unavailable (no claims.json and no audit TSVs)'
      : mode === 'tsv'
        ? 'no machine claims for this item (joined audit TSVs)'
        : 'no machine claims for this item';
    host.appendChild(div);
    return;
  }
  claims.forEach((claim, i) => {
    const card = document.createElement('div');
    const accepted = S.accepted.has(claim.key);
    const rejected = S.rejected.has(claim.key);
    card.className = 'claim' + (i === S.claimCur ? ' focus' : '') +
      (accepted ? ' accepted' : '') + (rejected ? ' rejected' : '');

    const head = document.createElement('div');
    head.className = 'head';
    const kind = document.createElement('span');
    kind.className = 'kind';
    kind.textContent = claim.kind + (claim.severity ? ' · ' + claim.severity : '');
    kind.title = claim.source || '';
    head.appendChild(kind);
    if (claim.path) {
      const link = document.createElement('span');
      link.className = 'pathlink';
      link.textContent = claim.path;
      link.title = 'select this JSON node';
      link.addEventListener('click', () => selectPath(claim.path, claim.value));
      head.appendChild(link);
    }
    const dec = document.createElement('span');
    dec.className = 'dec';
    dec.textContent = accepted ? 'accepted' : rejected ? 'rejected' : (i === S.claimCur ? 'focused  [ ]' : '');
    head.appendChild(dec);
    card.appendChild(head);

    const body = document.createElement('div');
    body.className = 'body';
    body.textContent = claim.text;
    card.appendChild(body);

    const acts = document.createElement('div');
    acts.className = 'acts';
    const accept = document.createElement('button');
    accept.className = 'btn' + (accepted ? ' on' : '');
    accept.textContent = 'accept [y]';
    accept.addEventListener('click', () => setClaim(i, 'accept'));
    const reject = document.createElement('button');
    reject.className = 'btn rej' + (rejected ? ' on' : '');
    reject.textContent = 'reject [n]';
    reject.addEventListener('click', () => setClaim(i, 'reject'));
    acts.appendChild(accept);
    acts.appendChild(reject);
    card.appendChild(acts);

    host.appendChild(card);
  });
}

async function setClaim(index, decision) {
  const claim = S.claims[index];
  if (!claim || !S.item) return;
  const current = S.accepted.has(claim.key) ? 'accept'
    : S.rejected.has(claim.key) ? 'reject' : '';
  const next = current === decision ? 'clear' : decision;
  const res = await api('/api/claim', {
    method: 'POST',
    body: { id: S.item.id, key: claim.key, decision: next },
  });
  if (res.error) { status(res.error, true); return; }
  S.accepted = new Set(res.claim_state.accepted || []);
  S.rejected = new Set(res.claim_state.rejected || []);
  S.claimCur = index;
  renderClaims();
  status(`${claim.kind} ${next === 'clear' ? 'cleared' : next + 'ed'}`, 'good');
}

function focusClaim(delta) {
  if (!S.claims.length) return;
  S.claimCur = (S.claimCur + delta + S.claims.length) % S.claims.length;
  renderClaims();
  const el = document.querySelectorAll('#claims .claim')[S.claimCur];
  if (el) el.scrollIntoView({ block: 'nearest' });
}

/* --------------------------------------------------------------- verdicts */

const AXES = ['target', 'actor', 'zone', 'quantity', 'referent', 'condition', 'timing', 'polarity', 'other'];

function renderVerdicts() {
  const host = $('#verdicts');
  host.textContent = '';
  [['ok', 'o'], ['bug', 'b'], ['legit', 'l']].forEach(([name, key]) => {
    const btn = document.createElement('button');
    btn.className = 'vbtn ' + name + (S.verdict === name ? ' active' : '');
    btn.innerHTML = `${name} <span class="hint">${key}</span>`;
    btn.addEventListener('click', () => { S.verdict = name; afterVerdictChange(); });
    host.appendChild(btn);
  });

  const axes = $('#axes');
  axes.textContent = '';
  axes.classList.toggle('show', S.verdict === 'bug');
  AXES.forEach((axis, i) => {
    const btn = document.createElement('button');
    btn.className = 'abtn' + (S.axis === axis ? ' active' : '');
    btn.textContent = `${i + 1} ${axis}`;
    btn.title = `axis ${i + 1}`;
    btn.addEventListener('click', () => { S.axis = axis; S.verdict = 'bug'; afterVerdictChange(); });
    axes.appendChild(btn);
  });
}

function afterVerdictChange() {
  S.warnedBugNoAxis = false;
  renderVerdicts();
  renderSelection();
  renderNote();
}

function renderSelection() {
  const host = $('#selection');
  host.textContent = '';
  if (S.verdict !== 'bug') {
    host.textContent = 'ok / legit need no node; bug: click a JSON node';
    return;
  }
  if (!S.path) {
    host.textContent = 'no node selected — click a JSON node (or a claim path)';
    return;
  }
  const p = document.createElement('span');
  p.className = 'p';
  p.textContent = S.path;
  host.appendChild(p);
  host.append(` = ${S.pathValue}`);
}

function renderNote() {
  const axis = S.verdict === 'bug' ? S.axis : '';
  const path = S.verdict === 'bug' ? S.path : '';
  const bits = [];
  if (axis) bits.push(axis + ':');
  if (path) bits.push(`${path}: ${S.pathValue}`);
  let preview = bits.join(' ');
  const text = S.noteText.trim();
  if (text) preview = (preview ? preview + ' — ' : '') + text;
  const label = S.item && S.item.label;
  if (label && !text && (label.verdict || '') === S.verdict &&
      (label.axis || '') === axis && (label.path || '') === path) {
    preview = label.note || preview;   // show the stored note verbatim
  }
  if (!preview && label) preview = label.note || '';
  $('#notepreview').textContent = preview ? 'note: ' + preview : 'note: (empty)';
  $('#notetext').placeholder = (S.item && S.item.label)
    ? 'add free-text note (current note above) — Enter commits'
    : 'optional free-text note (Enter commits)';
}

/* ------------------------------------------------------------------ items */

async function loadItem(index) {
  if (!S.ids.length) return;
  S.cur = Math.max(0, Math.min(index, S.ids.length - 1));
  const res = await api('/api/item?id=' + encodeURIComponent(S.ids[S.cur]));
  if (res.error) { status(res.error, true); return; }
  S.item = res;
  const label = res.label || null;
  S.verdict = label ? label.verdict : '';
  S.axis = label && label.axis ? label.axis : '';
  S.path = label && label.path ? label.path : '';
  S.pathValue = S.path ? shortJson(valueAtPath(res.output, S.path)) : '';
  S.noteText = '';
  S.accepted = new Set((res.claim_state && res.claim_state.accepted) || []);
  S.rejected = new Set((res.claim_state && res.claim_state.rejected) || []);
  S.claims = res.claims || [];
  S.claimCur = 0;
  S.hits = new Set(S.path ? [S.path] : []);
  S.warnedBugNoAxis = false;
  $('#notetext').value = '';
  $('#notetext').blur();
  renderItem();
  renderStrip();
  if (label) {
    renderSelection();
    renderNote();
  }
  status(`${res.id} · ${res.card}` + (label ? ` · labelled ${label.verdict}` : ''));
}

function valueAtPath(root, path) {
  if (!path) return undefined;
  let node = root;
  const re = /\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]/g;
  const p = path.replace(/^\$/, '');
  let m;
  let last = 0;
  while ((m = re.exec(p))) {
    if (m.index !== last) return undefined;
    last = re.lastIndex;
    if (m[1] !== undefined) {
      if (node === null || typeof node !== 'object' || !(m[1] in node)) return undefined;
      node = node[m[1]];
    } else {
      const i = Number(m[2]);
      if (!Array.isArray(node) || i >= node.length) return undefined;
      node = node[i];
    }
  }
  return last === p.length ? node : undefined;
}

function isDone(index) {
  const entry = S.state.items[index];
  return !!(entry && entry.done);
}

function nextTarget() {
  const batch = S.state.batch;
  const n = S.ids.length;
  const start = Math.floor(S.cur / batch) * batch;
  const end = Math.min(start + batch, n);
  for (let i = start; i < end; i++) if (i !== S.cur && !isDone(i)) return i;
  for (let i = end; i < n; i++) if (!isDone(i)) return i;
  for (let i = 0; i < start; i++) if (!isDone(i)) return i;
  return -1;
}

async function commit() {
  if (!S.item || S.busy) return;
  if (!S.verdict) { status('pick a verdict first: o / b / l', true); return; }
  if (S.verdict === 'bug' && !S.axis && !S.warnedBugNoAxis) {
    S.warnedBugNoAxis = true;
    status('bug without an axis — press 1-9, or Enter again to commit anyway');
    return;
  }
  S.busy = true;
  const body = {
    id: S.item.id,
    verdict: S.verdict,
    axis: S.verdict === 'bug' ? S.axis : '',
    path: S.verdict === 'bug' ? S.path : '',
    note: S.noteText,
    claims_accepted: [...S.accepted],
    claims_rejected: [...S.rejected],
  };
  const res = await api('/api/label', { method: 'POST', body });
  S.busy = false;
  if (res.error) { status(res.error, true); return; }
  const entry = S.state.items[S.cur];
  entry.done = true;
  entry.verdict = res.record.verdict;
  entry.source = 'ui';
  if (res.record.lane) entry.lane = res.record.lane;
  S.state.counts = res.counts;
  S.item.label = res.record;
  renderTop();
  const summary = `${res.record.id} ${res.record.verdict}` +
    (res.record.axis ? ` [${res.record.axis}]` : '') +
    (res.record.note ? ` — ${res.record.note}` : '');
  const target = nextTarget();
  if (target >= 0) {
    S.hits = new Set();
    await loadItem(target);
    status('saved ' + summary, 'good');
  } else {
    await loadItem(S.cur);
    status('saved ' + summary + ' · all items labelled — press x to export', 'good');
  }
}

async function undo() {
  if (!S.item || S.busy) return;
  S.busy = true;
  const res = await api('/api/undo', { method: 'POST', body: { id: S.item.id } });
  S.busy = false;
  if (res.error) { status(res.error, true); return; }
  const entry = S.state.items[S.cur];
  entry.done = false;
  entry.verdict = '';
  delete entry.lane;
  S.state.counts = res.counts;
  S.verdict = '';
  S.axis = '';
  S.path = '';
  S.pathValue = '';
  S.noteText = '';
  S.accepted = new Set();
  S.rejected = new Set();
  S.hits = new Set();
  $('#notetext').value = '';
  renderTop();
  await loadItem(S.cur);
  status('undone ' + S.item.id, 'good');
}

async function doExport() {
  const res = await api('/api/export', { method: 'POST', body: {} });
  if (res.error) { status(res.error, true); return; }
  status(`exported ${res.rows} labels → ${res.path}`, 'good');
}

async function doImport() {
  const res = await api('/api/import', { method: 'POST', body: {} });
  if (res.error) { status(res.error, true); return; }
  S.state = res.state;
  S.ids = res.state.items.map((it) => it.id);
  renderTop();
  await loadItem(S.cur);
  const extra = res.unknown && res.unknown.length ? ` · unknown: ${res.unknown.slice(0, 3).join(', ')}` : '';
  status(`import: ${res.imported} new, ${res.skipped} unchanged${extra}`, res.imported ? 'good' : '');
}

async function reloadState() {
  const st = await api('/api/state');
  if (st.error) { status(st.error, true); return; }
  S.state = st;
  S.ids = st.items.map((it) => it.id);
  renderTop();
  await loadItem(S.cur);
}

/* ------------------------------------------------------------------- help */

async function buildHelp() {
  const data = await api('/api/help');
  const table = $('#helptable');
  table.textContent = '';
  if (data.error) return;
  for (const [group, entries] of Object.entries(data)) {
    const head = document.createElement('tr');
    head.className = 'grp';
    head.innerHTML = `<td colspan="2">${esc(group)}</td>`;
    table.appendChild(head);
    for (const [key, text] of Object.entries(entries)) {
      const row = document.createElement('tr');
      row.innerHTML = `<td class="k">${esc(key)}</td><td>${esc(text)}</td>`;
      table.appendChild(row);
    }
  }
}

function toggleHelp(force) {
  const overlay = $('#help');
  const show = force === undefined ? overlay.classList.contains('hidden') : force;
  overlay.classList.toggle('hidden', !show);
}

/* ------------------------------------------------------------------ keys */

function move(delta) {
  if (!S.ids.length) return;
  const next = S.cur + delta;
  if (next < 0 || next >= S.ids.length) return;
  loadItem(next);
}

function handleKey(event) {
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  const tag = (event.target.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea') {
    if (event.key === 'Enter' && event.target.id === 'notetext') {
      event.preventDefault();
      commit();
    } else if (event.key === 'Escape') {
      event.target.blur();
    }
    return;
  }
  const helpOpen = !$('#help').classList.contains('hidden');
  if (event.key === '?' || (event.key === 'Escape' && helpOpen)) {
    event.preventDefault();
    toggleHelp();
    return;
  }
  if (helpOpen) return;
  if (event.key === 'Escape') {
    S.path = '';
    S.pathValue = '';
    S.hits = new Set();
    applyHighlights();
    renderVerdicts();
    renderSelection();
    renderNote();
    return;
  }
  switch (event.key) {
    case 'j': move(1); break;
    case 'k': move(-1); break;
    case 'g': loadItem(0); break;
    case 'G': loadItem(S.ids.length - 1); break;
    case 'o': S.verdict = 'ok'; afterVerdictChange(); break;
    case 'b': S.verdict = 'bug'; afterVerdictChange(); break;
    case 'l': S.verdict = 'legit'; afterVerdictChange(); break;
    case 'u': undo(); break;
    case 'y': setClaim(S.claimCur, 'accept'); break;
    case 'n': setClaim(S.claimCur, 'reject'); break;
    case '[': focusClaim(-1); break;
    case ']': focusClaim(1); break;
    case 'i': doImport(); break;
    case 'x': doExport(); break;
    case 'r': reloadState(); break;
    case 'Enter': commit(); break;
    default:
      if (/^[1-9]$/.test(event.key)) {
        S.axis = AXES[Number(event.key) - 1];
        S.verdict = 'bug';
        afterVerdictChange();
      }
      return;
  }
  event.preventDefault();
}

/* ------------------------------------------------------------------- boot */

function wire() {
  document.addEventListener('keydown', handleKey);
  $('#tree').addEventListener('click', (event) => {
    const el = event.target.closest('[data-path]');
    if (!el) return;
    selectPath(el.dataset.path, el.dataset.value);
  });
  $('#notetext').addEventListener('input', (event) => {
    S.noteText = event.target.value;
    renderNote();
  });
  $('#commitBtn').addEventListener('click', commit);
  $('#undoBtn').addEventListener('click', undo);
  $('#exportBtn').addEventListener('click', doExport);
  $('#importBtn').addEventListener('click', doImport);
  $('#helpBtn').addEventListener('click', () => toggleHelp());
  $('#help').addEventListener('click', (event) => {
    if (event.target.id === 'help') toggleHelp(false);
  });
}

async function boot() {
  wire();
  await buildHelp();
  const st = await api('/api/state');
  if (st.error) { status('cannot load state: ' + st.error, true); return; }
  S.state = st;
  S.ids = st.items.map((it) => it.id);
  renderTop();
  let index = st.items.findIndex((it) => !it.done);
  if (index < 0) index = 0;
  await loadItem(index);
  const imported = st.counts.imported;
  if (imported) status(`resumed · ${imported} rows imported from ${st.import.path}`, 'good');
}

boot();
