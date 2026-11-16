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
  focusPath: null,
  treeExpanded: true,
  view: 'semantic',
  parserOn: false,
  parserData: null,
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
  renderOutput();
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
      link.addEventListener('click', () => gotoPath(path));
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
  det.open = S.treeExpanded;
  const summary = document.createElement('summary');
  const twisty = document.createElement('span');
  twisty.className = 'tw';
  twisty.textContent = det.open ? '\u25BE' : '\u25B8';
  twisty.title = 'expand / collapse';
  summary.appendChild(twisty);
  const label = document.createElement('span');
  label.className = 'label';
  const size = Array.isArray(value) ? `[${value.length}]` : `{${Object.keys(value).length}}`;
  label.innerHTML = (keyLabel !== null
    ? `<span class="${/^\[\d+\]$/.test(keyLabel) ? 'idx' : 'k'}">${esc(keyLabel)}</span> `
    : '') + `<span class="idx">${size}</span>`;
  summary.appendChild(label);
  det.appendChild(summary);
  det.addEventListener('toggle', () => {
    twisty.textContent = det.open ? '\u25BE' : '\u25B8';
  });
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

function nodeEl(path) {
  if (!path) return null;
  return document.querySelector(`#tree [data-path="${CSS.escape(path)}"]`);
}

function valueOfNode(path) {
  const el = nodeEl(path);
  return el ? el.dataset.value : '';
}

function renderOutput() {
  renderSemantic();
  renderGraph();
  renderTree();
  applyView();
}

const VIEWS = ['semantic', 'graph', 'json'];

function setView(view, opts = {}) {
  if (!VIEWS.includes(view)) return;
  S.view = view;
  applyView();
  if (opts.reveal && S.path) reveal(S.path);
}

function applyView() {
  for (const view of VIEWS) {
    const host = document.querySelector(`.outview[data-view="${view}"]`);
    if (host) host.classList.toggle('active', view === S.view);
  }
  document.querySelectorAll('.viewbtn').forEach((btn) => {
    btn.classList.toggle('active', btn.dataset.view === S.view);
  });
  const toggle = $('#treeToggle');
  if (toggle) toggle.style.display = S.view === 'json' ? '' : 'none';
  applyStatusClasses();
}

function hostFor(view) {
  return document.querySelector(`.outview[data-view="${view}"]`);
}

function nodeInView(path, view = S.view) {
  if (!path) return null;
  const host = hostFor(view);
  return host ? host.querySelector(`[data-path="${CSS.escape(path)}"]`) : null;
}

function renderSemantic() {
  const host = $('#semantic');
  host.textContent = '';
  const ir = S.item.ir;
  const lines = (ir && ir.lines) || [];
  if (!lines.length) {
    host.textContent = 'no semantic rendering for this output';
    return;
  }
  for (const line of lines) {
    const row = document.createElement('div');
    row.className = 'irline' + (line.kind === 'fallback' ? ' has-fallback' : '');
    const role = document.createElement('span');
    role.className = 'role role-' + line.role.replace(/[^A-Z_]/g, '_');
    role.textContent = line.role;
    row.appendChild(role);
    const body = document.createElement('span');
    body.className = 'irtext';
    appendFragments(body, line.fragments || []);
    row.appendChild(body);
    host.appendChild(row);
  }
}

function appendFragments(host, frags) {
  let prev = '';
  for (const frag of frags) {
    if (prev && !/^[,;:.)\]]/.test(frag.text) && !/[([[]$/.test(prev)) {
      host.appendChild(document.createTextNode(' '));
    }
    const span = document.createElement('span');
    span.className = 'frag' + (frag.kind === 'fallback' ? ' fb' : '');
    span.dataset.path = frag.path;
    span.textContent = frag.text;
    host.appendChild(span);
    prev = frag.text;
  }
}

const GRAPH_LAYER = {
  cost: 0, condition: 0, event: 0, subject: 0,
  verb: 1,
  object: 2, token: 2,
  amount: 3, destination: 3, duration: 3, keyword: 3,
  anaphor: 4,
};

function renderGraph() {
  const host = $('#graph');
  host.textContent = '';
  const graph = (S.item.ir && S.item.ir.graph) || { nodes: [], edges: [] };
  if (!graph.nodes.length) {
    const note = document.createElement('div');
    note.className = 'graphempty';
    note.textContent = 'no semantic graph for this output';
    host.appendChild(note);
    return;
  }
  const NW = 180;
  const NH = 40;
  const GX = 54;
  const GY = 64;
  const PAD = 16;
  const byLayer = new Map();
  for (const node of graph.nodes) {
    const layer = GRAPH_LAYER[node.kind] ?? 2;
    if (!byLayer.has(layer)) byLayer.set(layer, []);
    byLayer.get(layer).push(node);
  }
  const layers = [...byLayer.keys()].sort((a, b) => a - b);
  const rows = Math.max(...layers.map((layer) => byLayer.get(layer).length), 1);
  const width = PAD * 2 + layers.length * (NW + GX) - GX;
  const height = PAD * 2 + rows * GY - (GY - NH);
  const pos = new Map();
  layers.forEach((layer, li) => {
    const nodes = byLayer.get(layer);
    const offset = ((rows - nodes.length) * GY) / 2;
    nodes.forEach((node, ri) => {
      pos.set(node.id, { x: PAD + li * (NW + GX), y: PAD + offset + ri * GY });
    });
  });
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
  svg.setAttribute('width', String(Math.max(width, 320)));
  svg.setAttribute('height', String(Math.max(height, 120)));
  svg.setAttribute('class', 'graphsvg');

  for (const edge of graph.edges) {
    const from = pos.get(edge.from);
    const to = pos.get(edge.to);
    if (!from || !to) continue;
    let x1 = from.x + NW;
    let y1 = from.y + NH / 2;
    let x2 = to.x;
    let y2 = to.y + NH / 2;
    let path;
    if (x2 <= x1) {
      const bulge = Math.max(30, Math.abs(y2 - y1) / 2 + 24);
      path = `M ${x1} ${y1} C ${x1 + bulge} ${y1}, ${x1 + bulge} ${y2}, ${x2} ${y2}`;
    } else {
      const mid = (x1 + x2) / 2;
      path = `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`;
    }
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    line.setAttribute('d', path);
    line.setAttribute('class', 'gedge' + (edge.dashed ? ' dashed' : ''));
    svg.appendChild(line);
    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', String((x1 + x2) / 2));
    label.setAttribute('y', String((y1 + y2) / 2 - 5));
    label.setAttribute('class', 'gelabel');
    label.textContent = edge.role;
    svg.appendChild(label);
  }

  for (const node of graph.nodes) {
    const { x, y } = pos.get(node.id);
    const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    group.setAttribute('class', `gnode kind-${node.kind}`);
    group.setAttribute('data-path', node.path);
    group.setAttribute('transform', `translate(${x},${y})`);
    const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    title.textContent = `${node.label} — ${node.kind} — ${node.path}`;
    group.appendChild(title);
    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('class', 'gbox');
    rect.setAttribute('width', String(NW));
    rect.setAttribute('height', String(NH));
    rect.setAttribute('rx', '5');
    group.appendChild(rect);
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('class', 'glabel');
    text.setAttribute('x', '10');
    text.setAttribute('y', '17');
    text.textContent = node.label.length > 24 ? node.label.slice(0, 23) + '…' : node.label;
    group.appendChild(text);
    const kind = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    kind.setAttribute('class', 'gkind');
    kind.setAttribute('x', '10');
    kind.setAttribute('y', '31');
    kind.textContent = node.kind;
    group.appendChild(kind);
    svg.appendChild(group);
  }
  const tip = document.createElement('div');
  tip.className = 'graphtip';
  tip.textContent = 'conditions / costs ← · → objects / amounts · dashed = anaphora · scroll for wide graphs';
  host.appendChild(tip);
  host.appendChild(svg);
}

function renderTree() {
  const host = $('#tree');
  host.textContent = '';
  if (S.item.output === null || S.item.output === undefined) {
    host.textContent = '(no output)';
    renderTreeControls();
    return;
  }
  host.appendChild(buildNode('$', null, S.item.output, 0));
  const start = S.path || S.focusPath || '$';
  S.focusPath = nodeEl(start) ? start : '$';
  if (S.path) reveal(S.path, true);
  else reveal(S.focusPath, false);
  applyHighlights();
  renderTreeControls();
}

function renderTreeControls() {
  const btn = $('#treeToggle');
  if (!btn) return;
  btn.textContent = S.treeExpanded ? 'collapse all (e)' : 'expand all (e)';
}

function toggleTree(force) {
  const want = force === undefined ? !S.treeExpanded : !!force;
  S.treeExpanded = want;
  document.querySelectorAll('#tree details').forEach((det) => {
    if (det.open !== want) det.open = want;
  });
  renderTreeControls();
  if (want) reveal(S.path || S.focusPath, false);
  S.focusPath = nearestVisible(S.focusPath);
  setFocus(S.focusPath, false);
}

function nearestVisible(path) {
  let candidate = path;
  while (candidate) {
    const el = nodeEl(candidate);
    if (el && isNodeVisible(el)) return candidate;
    candidate = parentPath(candidate);
  }
  return '$';
}

function nodeEl(path) {
  if (!path) return null;
  return document.querySelector(`#tree [data-path="${CSS.escape(path)}"]`);
}

function valueOfNode(path) {
  const el = nodeEl(path) || nodeInView(path);
  return el ? el.dataset.value || '' : '';
}

function reveal(path, scroll = true) {
  const el = nodeInView(path) || nodeInView(path, 'json');
  if (!el) return false;
  let node = el;
  while (node) {
    if (node.tagName === 'DETAILS') node.open = true;
    node = node.parentElement;
  }
  if (scroll) el.scrollIntoView({ block: 'nearest' });
  return true;
}

function applyStatusClasses() {
  document.querySelectorAll('.sel, .focus').forEach((el) => {
    if (el.closest('[data-view]')) el.classList.remove('sel', 'focus');
  });
  for (const view of VIEWS) {
    const sel = nodeInView(S.path, view);
    if (sel) sel.classList.add('sel');
    const focus = nodeInView(S.focusPath, view);
    if (focus && view === 'json') focus.classList.add('focus');
  }
}

function applyHighlights() {
  document.querySelectorAll('.hit').forEach((el) => {
    if (el.closest('[data-view]')) el.classList.remove('hit');
  });
  if (S.hits && S.hits.size) {
    for (const view of VIEWS) {
      for (const path of S.hits) {
        const el = nodeInView(path, view);
        if (el) el.classList.add('hit');
      }
    }
  }
  applyStatusClasses();
}

function setFocus(path, scroll = true) {
  if (!path) return;
  S.focusPath = path;
  const el = nodeEl(path);
  if (el && scroll) el.scrollIntoView({ block: 'nearest' });
  applyStatusClasses();
}

function isNodeVisible(el) {
  if (!el) return false;
  if (typeof el.checkVisibility === 'function') return el.checkVisibility();
  return el.getClientRects().length > 0;
}

function visibleTreeNodes() {
  return [...document.querySelectorAll('#tree [data-path]')].filter(isNodeVisible);
}

function moveFocus(delta) {
  const nodes = visibleTreeNodes();
  if (!nodes.length) return;
  let index = nodes.findIndex((el) => el.dataset.path === S.focusPath);
  if (index < 0) index = 0;
  const next = Math.max(0, Math.min(nodes.length - 1, index + delta));
  setFocus(nodes[next].dataset.path);
}

function parentPath(path) {
  if (!path || path === '$') return null;
  const match = path.match(/^(.*?)(?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])$/);
  return match ? match[1] : null;
}

function expandFocus() {
  const el = nodeEl(S.focusPath);
  if (!el) return;
  if (el.tagName === 'DETAILS') {
    if (!el.open) { el.open = true; return; }
    const first = el.querySelector('[data-path]');
    if (first) setFocus(first.dataset.path);
  }
}

function collapseFocus() {
  const el = nodeEl(S.focusPath);
  if (!el) return;
  if (el.tagName === 'DETAILS' && el.open) { el.open = false; return; }
  const parent = parentPath(S.focusPath);
  if (parent) setFocus(parent);
}

function selectPath(path, valueJson, opts = {}) {
  S.path = path || '';
  S.pathValue = valueJson || '';
  S.focusPath = S.path || S.focusPath;
  if (S.verdict !== 'bug') S.verdict = 'bug';
  S.hits = new Set(path ? [path] : []);
  if (path && opts.json) setView('json');
  if (path && !nodeInView(path)) setView('json');
  if (path) reveal(path);
  applyHighlights();
  renderVerdicts();
  renderSelection();
  renderNote();
}

function gotoPath(path) {
  setView('json');
  reveal(path, true);
  applyStatusClasses();
}

async function toggleParser(force) {
  S.parserOn = force === undefined ? !S.parserOn : !!force;
  const btn = $('#parserBtn');
  if (btn) btn.classList.toggle('on', S.parserOn);
  if (!S.parserOn) {
    $('#parser').textContent = '';
    $('#parserinfo').textContent = '';
    renderSentence();
    return;
  }
  await loadParser();
}

async function loadParser() {
  if (!S.item) return;
  if (S.parserData && S.parserData.id === S.item.id) {
    renderParser();
    return;
  }
  const info = $('#parserinfo');
  info.innerHTML = '<span class="spin"></span> parsing…';
  const res = await api('/api/parser?id=' + encodeURIComponent(S.item.id));
  if (res.error) {
    info.textContent = 'parser failed: ' + res.error;
    return;
  }
  S.parserData = Object.assign({ id: S.item.id }, res);
  renderParser();
}

function renderParser() {
  const data = S.parserData;
  $('#parser').textContent = '';
  if (!data || !S.parserOn) return;
  const info = $('#parserinfo');
  if (!data.available) {
    info.textContent = 'ptree unavailable — ' + (data.error || 'no spans');
    renderSentence();
    return;
  }
  info.textContent = `${data.source} · ${data.ms} ms · ${data.spans.length} spans`;
  renderParserSentence(data.spans);
  const table = document.createElement('table');
  const head = document.createElement('tr');
  for (const name of ['span', 'role', 'verb', 'node', 'flags']) {
    const th = document.createElement('th');
    th.textContent = name;
    head.appendChild(th);
  }
  table.appendChild(head);
  for (const span of data.spans) {
    const tr = document.createElement('tr');
    const flags = [span.predicate ? 'predicate' : '',
                   span.in_condition ? 'in_condition' : ''].filter(Boolean).join(' ');
    const cells = [span.text, span.role || '—', span.verb || '—', span.node || '—',
                   flags || '—'];
    cells.forEach((text, index) => {
      const td = document.createElement('td');
      td.textContent = text;
      if (index === 0) td.className = 'span';
      if (index === 1) td.className = 'role';
      tr.appendChild(td);
    });
    table.appendChild(tr);
  }
  $('#parser').appendChild(table);
}

function renderParserSentence(spans) {
  const host = $('#judged');
  const text = S.item.original_text || '';
  host.textContent = '';
  if (!spans.length) {
    host.textContent = text;
    return;
  }
  const classes = new Array(text.length).fill('role-unknown');
  const sources = new Array(text.length).fill(null);
  const ordered = [...spans].sort((a, b) => (a.end - a.start) - (b.end - b.start));
  for (const span of ordered) {
    const role = span.role
      || (span.predicate ? 'predicate' : span.in_condition ? 'in_condition' : 'unknown');
    for (let i = span.start; i < Math.min(span.end, text.length); i++) {
      classes[i] = 'role-' + role;
      sources[i] = span;
    }
  }
  let i = 0;
  while (i < text.length) {
    let j = i;
    while (j < text.length && classes[j] === classes[i] && sources[j] === sources[i]) j++;
    const piece = document.createElement('span');
    piece.className = 'pspan ' + classes[i];
    piece.textContent = text.slice(i, j);
    const meta = sources[i];
    if (meta) {
      piece.title = [meta.role || 'span', meta.verb, meta.node].filter(Boolean).join(' · ');
    }
    host.appendChild(piece);
    i = j;
  }
}

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
      link.addEventListener('click', () => selectPath(claim.path, claim.value, { json: true }));
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
  S.focusPath = S.path || null;
  S.warnedBugNoAxis = false;
  $('#notetext').value = '';
  $('#notetext').blur();
  renderItem();
  renderStrip();
  if (S.parserOn) {
    S.parserData = null;
    loadParser();
  } else {
    $('#parser').textContent = '';
    $('#parserinfo').textContent = '';
  }
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
    case 'e': toggleTree(); break;
    case 'v': {
      const index = VIEWS.indexOf(S.view);
      setView(VIEWS[(index + 1) % VIEWS.length], { reveal: true });
      break;
    }
    case 'p': toggleParser(); break;
    case 's':
      if (S.focusPath) selectPath(S.focusPath, valueOfNode(S.focusPath));
      break;
    case 'ArrowDown': moveFocus(1); break;
    case 'ArrowUp': moveFocus(-1); break;
    case 'ArrowRight': expandFocus(); break;
    case 'ArrowLeft': collapseFocus(); break;
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
    const twisty = event.target.closest('.tw');
    if (twisty) {
      event.preventDefault();
      event.stopPropagation();
      const det = twisty.closest('details');
      if (det) det.open = !det.open;
      return;
    }
    const summary = event.target.closest('summary');
    if (summary) {
      event.preventDefault();           // the label selects; it must not toggle
      const det = summary.parentElement;
      if (det && det.dataset.path) selectPath(det.dataset.path, det.dataset.value);
      return;
    }
    const el = event.target.closest('[data-path]');
    if (!el) return;
    selectPath(el.dataset.path, el.dataset.value);
  });
  $('#treeToggle').addEventListener('click', () => toggleTree());
  document.querySelectorAll('.viewbtn').forEach((btn) => {
    btn.addEventListener('click', () => setView(btn.dataset.view, { reveal: true }));
  });
  $('#semantic').addEventListener('click', (event) => {
    const frag = event.target.closest('.frag');
    if (!frag) return;
    selectPath(frag.dataset.path, valueOfNode(frag.dataset.path));
  });
  $('#graph').addEventListener('click', (event) => {
    const node = event.target.closest('[data-path]');
    if (!node) return;
    const value = valueAtPath(S.item.output, node.dataset.path);
    selectPath(node.dataset.path, value === undefined ? '' : shortJson(value));
  });
  $('#parserBtn').addEventListener('click', () => toggleParser());
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
