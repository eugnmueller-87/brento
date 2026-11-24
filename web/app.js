/* Brento front end. No framework and no build step. Everything shown comes from the server. */
(function () {
  'use strict';

  // This browser's own word. It is kept here and never sent: every question to Brento is signed with it (sign.js). On a
  // phone there is none, a paired phone carries a cookie instead.
  let WORD = null, RUN = '';
  function readWord() { try { const w = JSON.parse(localStorage.getItem(BrentoSign.KEY)); WORD = w && w.id && w.word ? w : null; } catch (e) { WORD = null; } }
  readWord();
  const fetch = async (url, options) => {
    const o = Object.assign({}, options), at = new URL(url, location.href);
    for (let turn = 0; ; turn += 1) {
      const headers = Object.assign({ 'X-Leitstand': '1' }, o.headers), word = WORD, used = RUN;
      if (!word || !at.pathname.startsWith('/api/')) return window.fetch(url, Object.assign({}, o, { headers }));
      const head = BrentoSign.header(word, used, (o.method || 'GET').toUpperCase(), at.pathname + at.search, location.host, o.body || '', Date.now());
      headers['X-Brento-Sign'] = head;
      const r = await window.fetch(url, Object.assign({}, o, { headers }));
      if (r.headers.get('X-Brento-Answer') === BrentoSign.answer(word, head)) return r;
      // Brento was started anew, or another window of this browser came in again: the same once more, signed for that.
      const run = r.headers.get('X-Brento-Run');
      if (r.status === 401 && turn < 3) {
        if (run && run !== used) { RUN = run; continue; }
        if (WORD === word) readWord();
        if (WORD && WORD.word !== word.word) continue;
      }
      if (r.status === 401) return r;
      throw new Error('Something else answers at this address. Open Brento with its icon.');
    }
  };
  // The icon's ticket, or the key from another computer, traded for a word. The address is cleaned first, and the word
  // this browser had before ends with it.
  async function enter() {
    const q = new URLSearchParams(location.search), given = q.get('ticket') ? { ticket: q.get('ticket') } : q.get('key') ? { key: q.get('key') } : null;
    if (!given) return;
    q.delete('ticket'); q.delete('key');
    history.replaceState(null, '', location.pathname + (q.toString() ? '?' + q : '') + location.hash);
    try {
      if (WORD) given.old = WORD.id;
      const r = await window.fetch('/api/enter', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Leitstand': '1' }, body: JSON.stringify(given) });
      if (!r.ok) return;
      const word = await r.json();
      RUN = word.run || '';
      WORD = { id: word.id, word: word.word };
      try { localStorage.setItem(BrentoSign.KEY, JSON.stringify(WORD)); } catch (e) { /* then it holds for this window only */ }
    } catch (e) { /* the page says what it cannot read */ }
  }
  // Another window of this browser came in, or the word was deleted.
  window.addEventListener('storage', (e) => { if (e.key === BrentoSign.KEY || e.key === null) { readWord(); load(); loadTools(); } });
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (v) => String(v == null ? '' : v).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* the page works without it */ } }
  };

  const ICONS = {
    home: '<path d="M4 18 10 8l4 6 2-3 4 7z"/><circle cx="17" cy="6" r="1.8"/>',
    today: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m3.500 6 1 1 2-2M3.500 12l1 1 2-2M3.500 18l1 1 2-2"/>',
    library: '<path d="M5 4.500h4.500v15H5zM9.500 4.500H14v15H9.500z"/><path d="m16 5.500 3.300-.800 3 14.300-3.300.800z"/>',
    projects: '<path d="M3.500 7.500a2 2 0 0 1 2-2h4l2 2.500h7a2 2 0 0 1 2 2v7.500a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/><path d="M8 14h5"/>',
    pipeline: '<rect x="3" y="7.500" width="18" height="12" rx="2.500"/><path d="M9 7.500V6a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v1.500M3 13h18"/>',
    board: '<rect x="3.500" y="4" width="4.600" height="16" rx="1.600"/><rect x="9.700" y="4" width="4.600" height="10" rx="1.600"/><rect x="15.900" y="4" width="4.600" height="13" rx="1.600"/>',
    brain: '<path d="M3 12h4l2.200-5.500 4 11L15.600 12H21"/>',
    ask: '<path d="M12 3.500 13.800 9l5.700 1.800-5.700 1.900L12 18.400l-1.800-5.700-5.700-1.900L10.200 9z"/><path d="M18.500 16.500v3M17 18h3"/>',
    tools: '<rect x="4" y="4" width="6.500" height="6.500" rx="1.500"/><rect x="13.500" y="4" width="6.500" height="6.500" rx="1.500"/><rect x="4" y="13.500" width="6.500" height="6.500" rx="1.500"/><rect x="13.500" y="13.500" width="6.500" height="6.500" rx="1.500"/>',
    search: '<circle cx="11" cy="11" r="6.500"/><path d="m16 16 4.500 4.500"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.300-4.300L4 9"/><path d="M4 4v5h5"/><path d="M4 13a8 8 0 0 0 14.300 4.300L20 15"/><path d="M20 20v-5h-5"/>',
    mail: '<rect x="3" y="5.500" width="18" height="13" rx="2.500"/><path d="m3.500 7.500 8.500 6 8.500-6"/>',
    calm: '<path d="M3 9c2.500-2.500 4.500-2.500 7 0s4.500 2.500 7 0 3-2 4-2"/><path d="M3 15c2.500-2.500 4.500-2.500 7 0s4.500 2.500 7 0 3-2 4-2"/>',
    full: '<path d="M4 16c3-9 6-9 8-4s5 5 8-5"/>',
    left: '<path d="m14.500 5-7 7 7 7"/>',
    right: '<path d="m9.500 5 7 7-7 7"/>',
    arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
    out: '<path d="M8 16 17 7M9 7h8v8"/>',
    chev: '<path d="m9 6 6 6-6 6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    minus: '<path d="M5 12h14"/>'
  };
  const icon = (n) => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.700" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICONS[n] + '</svg>';

  const ROUTES = [
    { id: 'home', label: 'Home', tone: '#ff8a5c' },
    { id: 'today', label: 'Today', tone: '#6cf5bf' },
    { id: 'projects', label: 'Projects', tone: '#ffd166' },
    { id: 'library', label: 'Library', tone: '#f0a6c8' },
    { id: 'pipeline', label: 'Pipeline', tone: '#7fd4ff' },
    { id: 'board', label: 'Board', tone: '#98a5ff' },
    { id: 'brain', label: 'Brain', tone: '#d09dff' },
    { id: 'ask', label: 'Ask', tone: '#7ee8e0' }
  ];
  const routeIndex = (id) => ROUTES.findIndex((r) => r.id === id);
  const WEEK = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const TILES = ['#3d5a98', '#7a4a9e', '#2f7d6b', '#a0553a', '#8a6d1f', '#34708f', '#94466a', '#5a6b3a'];

  let S = null;
  let stateText = '';
  let route = 'home';
  let routeId = null;
  let cur = 0;
  let TOOLS = [];
  let HIDDEN_PAGES = [];
  // Unread messages per tool id. Only the desktop window can count them, from each app's own title.
  let BADGES = {};
  let PAGE_ORDER = [];
  // The pages in the dock, in the order they were dragged into. A page put back in joins at the end.
  const pageRank = (r) => { const i = PAGE_ORDER.indexOf(r.id); return i < 0 ? 100 + routeIndex(r.id) : i; };
  const dockPages = () => ROUTES.filter((r) => !HIDDEN_PAGES.includes(r.id) && !((S && S.pagesOff) || []).includes(r.id)).sort((a, b) => pageRank(a) - pageRank(b));
  let firstHome = true;
  // Board filters live in the URL. A remembered filter hid most of the board without saying so.
  let boardArea = 'All';
  let boardDead = false;
  let projectQuery = '';
  let projectState = 'all';
  let projectSort = { key: 'next', dir: 1 };
  // Which seven days the strip shows, counted in weeks from today. An open day sets it, the arrows move it.
  let stripWeek = 0;

  const hashOf = (text) => { let h = 7; for (let i = 0; i < text.length; i++) h = (Math.imul(h, 31) + text.charCodeAt(i)) >>> 0; return h; };
  const tileColor = (text) => TILES[hashOf(text) % TILES.length];
  const initials = (name) => {
    const words = String(name).replace(/[^\p{L}\p{N} ]/gu, ' ').split(/\s+/).filter(Boolean);
    return ((words[0] || '?')[0] + (words[1] ? words[1][0] : (words[0] || '').slice(1, 2))).toUpperCase();
  };
  const dayMonth = (iso) => (iso ? iso.slice(8, 10) + '.' + iso.slice(5, 7) + '.' : '');
  const weekdayOf = (iso) => WEEK[new Date(iso + 'T12:00:00').getDay()];
  const addDays = (iso, n) => {
    const d = new Date(iso + 'T12:00:00');
    d.setDate(d.getDate() + n);
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  };
  const daysBetween = (a, b) => Math.round((new Date(b + 'T12:00:00') - new Date(a + 'T12:00:00')) / 86400000);
  const inDays = (n) => (n === 0 ? 'Today' : n === 1 ? 'Tomorrow' : n === -1 ? 'Yesterday' : n < 0 ? -n + ' days ago' : 'In ' + n + ' days');
  const openDay = () => (/^\d{4}-\d{2}-\d{2}$/.test(routeId || '') ? routeId : S.today);
  const lastWeek = () => Math.floor((S.agendaDays - 1) / 7);

  // An action, such as Undo, gets a button and a longer stay, so there is time to reach it.
  function toast(text, action) {
    const el = $('#toast');
    el.textContent = text;
    if (action) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = action.label;
      b.onclick = () => { el.classList.remove('on'); Promise.resolve(action.run()).catch((err) => toast(err.message)); };
      el.append(b);
    }
    el.classList.add('on');
    clearTimeout(toast.t);
    toast.t = setTimeout(() => el.classList.remove('on'), action ? 9000 : 4500);
  }

  /* Motion */
  // Always full motion (owner, 08.11.2026: calm was horrible, and the switch was clutter). Windows' own "fewer
  // animations" setting does not decide either.
  const motionFull = () => document.documentElement.dataset.motion === 'full';
  function applyMotion() {
    document.documentElement.dataset.motion = 'full';
  }

  /* One animation loop that sleeps as soon as nothing is moving. */
  const springs = new Set();
  let raf = 0, last = 0;
  function makeSpring(x, on, k, d) { return { x, v: 0, t: x, k: k || 170, d: d || 22, on }; }
  function drive(s, target) {
    s.t = target;
    if (!motionFull()) { s.x = target; s.v = 0; s.on(target); springs.delete(s); return; }
    springs.add(s);
    if (!raf) { last = performance.now(); raf = requestAnimationFrame(tick); }
  }
  function tick(now) {
    const dt = Math.min(0.034, (now - last) / 1000);
    last = now;
    springs.forEach((s) => {
      s.v += (s.k * (s.t - s.x) - s.d * s.v) * dt;
      s.x += s.v * dt;
      if (Math.abs(s.v) < 0.002 && Math.abs(s.t - s.x) < 0.002) { s.x = s.t; s.v = 0; springs.delete(s); }
      s.on(s.x);
    });
    raf = springs.size ? requestAnimationFrame(tick) : 0;
  }

  /* Ambient light behind Home, taken from the current picture. Work pages stay flat. */
  let ambientOn = 'a';
  function setAmbient(canvas, accent) {
    document.documentElement.style.setProperty('--glow', accent);
    if (!canvas) return;
    const next = ambientOn === 'a' ? 'b' : 'a';
    const target = $('#amb-' + next);
    target.getContext('2d').drawImage(canvas, 0, 0, target.width, target.height);
    target.classList.add('on');
    $('#amb-' + ambientOn).classList.remove('on');
    ambientOn = next;
  }
  function ambientOff() { $$('#ambient canvas').forEach((c) => c.classList.remove('on')); }

  /* Frame */
  function tickClock() {
    const d = new Date();
    $('#clock').textContent = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
    $('#date').textContent = WEEK[d.getDay()] + ', ' + MONTHS[d.getMonth()] + ' ' + d.getDate();
  }
  function renderTop() {
    const r = ROUTES[routeIndex(route)];
    // Home stays on every page, in the same place, so the way back never moves.
    let html = '<i>/</i><a class="crumb-home" href="#home"' + (route === 'home' ? ' aria-current="page"' : '') + ' style="--tone:' + ROUTES[0].tone + '">' + icon('home') + '<span>Home</span></a>';
    if (route === 'projects' && routeId && S) {
      const p = S.projects.rows.find((x) => x.id === routeId);
      html += '<i>/</i><a href="#projects">Projects</a><i>/</i><b>' + esc(p ? p.name : routeId) + '</b>';
    } else if (route === 'day' && S) {
      html += '<i>/</i><b>' + weekdayOf(openDay()) + ' ' + dayMonth(openDay()) + '</b>';
    } else if (route !== 'home') {
      html += '<i>/</i><b>' + esc(r ? r.label : route === 'setup' ? 'Welcome' : route === 'settings' ? 'Settings' : '') + '</b>';
    }
    $('#crumb').innerHTML = html;
    document.title = (r ? r.label + ' · ' : route === 'day' ? 'Day · ' : route === 'setup' ? 'Welcome · ' : route === 'settings' ? 'Settings · ' : '') + 'Brento';
    $('#back').hidden = route === 'home';
  }
  /* Back: one page back, like a browser, and Home when nothing came before. Button, Alt+←, Backspace, mouse back. */
  const trail = [location.hash || '#home'];
  window.addEventListener('hashchange', () => {
    const h = location.hash || '#home';
    if (trail.length > 1 && trail[trail.length - 2] === h) trail.pop();
    else if (trail[trail.length - 1] !== h) trail.push(h);
  });
  function goBack() {
    if (trail.length > 1) history.back();
    else if (route !== 'home') navigate('home');
  }
  $('#back').innerHTML = icon('left');
  $('#back').onclick = goBack;
  window.addEventListener('mouseup', (e) => { if (e.button === 3) { e.preventDefault(); goBack(); } });
  function renderStrip() {
    if (!S) return;
    const open = route === 'day' ? openDay() : '';
    let html = '<button class="strip-btn" type="button" id="strip-prev" aria-label="Previous seven days"' + (stripWeek > 0 ? '' : ' disabled') + '>' + icon('left') + '</button>';
    for (let i = 0; i < 7; i++) {
      const iso = addDays(S.today, stripWeek * 7 + i);
      const due = S.agenda.filter((x) => x.date === iso).sort((a, b) => b.mine - a.mine);
      // Further out, the day alone no longer says which month.
      html += '<a class="day' + (iso === S.today ? ' today' : '') + (iso === open ? ' open' : '') + (due.length ? ' has-due' : '') + '" href="#day/' + iso + '" title="' + esc(due.map((x) => x.title).join(', ') || 'Nothing dated') + '"' + (iso === open ? ' aria-current="date"' : '') + '><span>' + weekdayOf(iso) + '</span><b>' + (stripWeek ? dayMonth(iso) : iso.slice(8)) + '</b>'
        + due.slice(0, 1).map((x) => '<span class="due' + (x.mine ? '' : ' theirs') + '">' + esc(x.title.split(':')[0]) + '</span>').join('')
        + (due.length > 1 ? '<span class="due more">+' + (due.length - 1) + '</span>' : '') + '</a>';
    }
    html += '<button class="strip-btn" type="button" id="strip-next" aria-label="Next seven days"' + (stripWeek < lastWeek() ? '' : ' disabled') + '>' + icon('right') + '</button>';
    const mine = S.alerts.length;
    const live = S.sources.filter((s) => s.id !== 'calendar' || s.state !== 'unknown');
    const fresh = live.filter((s) => s.state === 'fresh').length;
    const still = S.liveness.still || 0;
    html += '<a class="status-pill" href="#home" title="Your own deadlines and meetings with other people in the next 7 days"><span class="dot ' + (mine ? 'warn' : 'ok') + '"></span><span><b>Needs you</b><small>' + mine + ' due soon</small></span></a>'
      + '<a class="status-pill" href="#brain" title="' + fresh + ' of ' + live.length + ' sources fresh"><span class="dot ' + (still ? 'warn' : 'ok') + '"></span><span><b>Background</b><small>' + still + ' silent</small></span></a>';
    $('#strip').innerHTML = html;
    $('#strip-prev').onclick = () => { stripWeek = Math.max(0, stripWeek - 1); renderStrip(); };
    $('#strip-next').onclick = () => { stripWeek = Math.min(lastWeek(), stripWeek + 1); renderStrip(); };
  }

  /* Tools. Google, GitHub, Claude and the rest refuse to load inside another page, so a tool
     opens in its own window docked beside this one, signed in as you. */
  const faviconSrc = (host) => 'https://www.google.com/s2/favicons?domain_url=' + encodeURIComponent('https://' + host + '/') + '&amp;sz=64';
  function toolIconHtml(t, cls) {
    if (t.icon) return '<span class="' + cls + '"><img alt="" src="' + faviconSrc(t.icon) + '" data-letters="' + esc(initials(t.name)) + '"></span>';
    return '<span class="' + cls + ' lettered" style="--tile:' + tileColor(t.id) + '">' + esc(initials(t.name)) + '</span>';
  }
  function openTool(t, e) {
    if (!/^https?:/i.test(t.url)) { location.href = t.url; return; }
    if ((S && S.phone) || window.innerWidth <= 760 || (e && (e.ctrlKey || e.metaKey))) { window.open(t.url, '_blank', 'noopener'); return; }
    // Next to this window, not at a share of the screen: on a very wide monitor those are far apart.
    const sx = window.screenX, ow = window.outerWidth, edge = (screen.availLeft || 0) + screen.availWidth;
    const roomRight = edge - (sx + ow), roomLeft = sx - (screen.availLeft || 0);
    let w, left;
    if (roomRight >= 760) { w = Math.min(roomRight, 1400); left = sx + ow; }
    else if (roomLeft >= 760) { w = Math.min(roomLeft, 1400); left = sx - w; }
    else { w = Math.round(ow * 0.46); left = sx + ow - w; }
    const popup = () => {
      const win = window.open(t.url, 'leitstand-' + t.id, 'popup=yes,width=' + w + ',height=' + window.outerHeight + ',left=' + left + ',top=' + window.screenY);
      if (!win) { toast('The browser blocked the window. Allow pop-ups for this page, then click again.'); return; }
      try { win.opener = null; win.focus(); } catch (err) { /* the tool's own page may refuse this */ }
    };
    // Chrome puts an address strip on every pop-up (owner, 08.11.2026: "this is what I don't like"). A tool from the list
    // opens as a Chrome app window instead, started by the server, without the strip. A second click opens a second
    // window; a double click counts once. Where the server cannot, the pop-up still works.
    if (!toolById(t.id) || document.documentElement.classList.contains('in-shell')) { popup(); return; }
    if (Date.now() - (openTool.last[t.id] || 0) < 1500) return;
    openTool.last[t.id] = Date.now();
    fetch('/api/open', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Leitstand': '1' },
      body: JSON.stringify({ id: t.id, x: Math.round(left), y: window.screenY, w: Math.round(w), h: window.outerHeight }) })
      .then((r) => { if (!r.ok) throw new Error(); }).catch(popup);
  }
  openTool.last = {};
  const toolById = (id) => TOOLS.find((t) => t.id === id);
  // Read again with every page refresh, so the app window and a browser tab show the same dock.
  let toolsText = '';
  function takeTools(j) {
    TOOLS = j.tools || [];
    HIDDEN_PAGES = j.hiddenPages || [];
    PAGE_ORDER = j.pageOrder || [];
  }
  async function loadTools(force) {
    try {
      const res = await fetch('/api/tools');
      if (!res.ok) return;
      const text = await res.text();
      // Never under an open menu or an icon being dragged.
      if (!force && (text === toolsText || !$('#dock-menu').hidden || drag)) return;
      toolsText = text;
      takeTools(JSON.parse(text));
      renderDock();
    } catch (err) { /* the dock still has its pages */ }
  }
  async function toolAction(body) {
    const res = await fetch('/api/tools', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Leitstand': '1' }, body: JSON.stringify(body) });
    const j = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(j.error || 'The server answered ' + res.status);
    takeTools(j);
    renderDock();
    paintTools();
  }
  function openToolsPanel() {
    $('#tools').hidden = false;
    $('#tools-error').textContent = '';
    paintTools();
    const first = $('#tools .tool-open');
    if (first) first.focus();
  }
  const closeToolsPanel = () => { $('#tools').hidden = true; };
  function paintTools() {
    // The panel holds only what we built. Outside services live in the dock.
    const own = TOOLS.filter((t) => t.own);
    const groups = [];
    own.forEach((t) => { if (!groups.includes(t.group)) groups.push(t.group); });
    $('#tool-groups').innerHTML = groups.map((g) => '<option value="' + esc(g) + '">').join('');
    $('#tools-list').innerHTML = groups.map((g) => '<h3>' + esc(g) + '</h3><div class="tool-grid">' + own.filter((t) => t.group === g).map((t) => '<div class="tool-card" data-id="' + esc(t.id) + '">'
      + '<button class="tool-open" type="button" title="' + esc(t.url) + '">' + toolIconHtml(t, 'tool-icon') + '<span class="tool-name">' + esc(t.name) + '</span></button>'
      + '<button class="tool-act pin' + (t.pinned ? ' pinned' : '') + '" type="button" aria-pressed="' + !!t.pinned + '" aria-label="' + (t.pinned ? 'Remove ' : 'Put ') + esc(t.name) + (t.pinned ? ' from the dock' : ' in the dock') + '" title="' + (t.pinned ? 'In the dock' : 'Put in the dock') + '">' + (t.pinned ? '★' : '☆') + '</button>'
      + '<button class="tool-act del" type="button" aria-label="Remove ' + esc(t.name) + ' from the list" title="Remove from the list">×</button></div>').join('') + '</div>').join('')
      || '<div class="empty">No tools yet. Add the first one below.</div>';
  }
  $('#tools-list').addEventListener('click', async (e) => {
    const card = e.target.closest('.tool-card');
    if (!card) return;
    const t = toolById(card.dataset.id);
    if (!t) return;
    try {
      if (e.target.closest('.tool-open')) { closeToolsPanel(); openTool(t, e); }
      else if (e.target.closest('.pin')) await toolAction({ action: 'pin', id: t.id, pinned: !t.pinned });
      else if (e.target.closest('.del')) await toolAction({ action: 'remove', id: t.id });
    } catch (err) { $('#tools-error').textContent = err.message; }
  });
  $('#tools-add').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await toolAction({ action: 'add', name: $('#tool-name').value, url: $('#tool-url').value, group: $('#tool-group').value, pinned: $('#tool-dock').checked, own: true });
      $('#tool-name').value = ''; $('#tool-url').value = ''; $('#tools-error').textContent = '';
      $('#tool-name').focus();
    } catch (err) { $('#tools-error').textContent = err.message; }
  });
  $('#tools').addEventListener('mousedown', (e) => { if (e.target.id === 'tools') closeToolsPanel(); });
  $('#tools-close').onclick = closeToolsPanel;

  /* A favicon that cannot load falls back to the tool's initials. */
  document.addEventListener('error', (e) => {
    const img = e.target;
    if (!img || img.tagName !== 'IMG' || !img.dataset.letters) return;
    const holder = img.parentElement;
    holder.classList.add('lettered');
    holder.textContent = img.dataset.letters;
  }, true);

  /* Dock */
  let dockSprings = [];
  function renderDock() {
    const counts = S ? {
      home: S.alerts.length,
      board: S.board.passed,
      brain: S.liveness.still || 0
    } : {};
    // A badge means something needs a decision. Plain counts live on the pages.
    const titles = { home: 'Needs preparing', board: 'Lane cards with a passed date', brain: 'Silent systems' };
    const pages = dockPages().map((r) => {
      const c = counts[r.id];
      return '<a class="dock-item' + (route === r.id ? ' on' : '') + '" href="#' + r.id + '" data-page="' + r.id + '" data-mag aria-label="' + esc(r.label) + '"' + (route === r.id ? ' aria-current="page"' : '') + ' style="--tone:' + r.tone + '">' + icon(r.id)
        + (c ? '<span class="badge" title="' + titles[r.id] + ': ' + c + '">' + c + '</span>' : '') + '<span class="dock-tip">' + esc(r.label) + '</span></a>';
    }).join('');
    const pinned = TOOLS.filter((t) => t.pinned).map((t) => '<button class="dock-item tool' + (t.icon ? '' : ' lettered') + '" type="button" data-tool="' + esc(t.id) + '" data-mag aria-label="Open ' + esc(t.name) + '"' + (t.icon ? '' : ' style="--tile:' + tileColor(t.id) + '"') + '>'
      + (t.icon ? '<img alt="" src="' + faviconSrc(t.icon) + '" data-letters="' + esc(initials(t.name)) + '">' : '<span class="letters">' + esc(initials(t.name)) + '</span>')
      + '<span class="dock-tip">' + esc(t.name) + '</span></button>').join('');
    // "+" is the visible way in: everything not docked, ours or outside, and New app for anything else.
    $('#dock').innerHTML = pages + '<span class="dock-sep"></span>' + pinned
      + '<button class="dock-item add" type="button" id="dock-add" data-mag aria-label="Add to the dock">' + icon('plus') + '<span class="dock-tip">Add to dock</span></button>'
      + '<button class="dock-item" type="button" id="open-tools" data-mag aria-label="All tools">' + icon('tools') + '<span class="dock-tip">All tools</span></button>';
    dockSprings = $$('[data-mag]', $('#dock')).map((el) => makeSpring(1, (v) => el.style.setProperty('--s', v.toFixed(3)), 240, 24));
    $('#open-tools').onclick = openToolsPanel;
    $('#dock-add').onclick = (e) => { e.stopPropagation(); openDockMenu($('#dock-add'), 0, 0); };
    $$('[data-tool]', $('#dock')).forEach((b) => { b.onclick = (e) => { const t = toolById(b.dataset.tool); if (t) openTool(t, e); }; });
    paintBadges();
  }
  // In place, so a new message never redraws the dock under a drag.
  function paintBadges() {
    $$('[data-tool]', $('#dock')).forEach((b) => {
      const n = BADGES[b.dataset.tool] || 0;
      let el = $('.badge.msg', b);
      if (!n) { if (el) el.remove(); return; }
      if (!el) { el = document.createElement('span'); el.className = 'badge msg'; b.insertBefore(el, $('.dock-tip', b)); }
      el.textContent = n > 99 ? '99+' : String(n);
      el.title = n + ' unread';
    });
  }
  if (window.brento) window.brento.onBadges((counts) => { BADGES = counts || {}; paintBadges(); });
  (function dockWave() {
    const dock = $('#dock');
    let rest = null;
    dock.addEventListener('pointerenter', () => { rest = null; });
    dock.addEventListener('pointermove', (e) => {
      if (e.pointerType !== 'mouse' || !motionFull() || (drag && drag.moved)) return;
      // Measured once at rest, so the icons growing does not move the thing they are measured against.
      if (!rest) rest = $$('[data-mag]', dock).map((el) => { const b = el.getBoundingClientRect(); return b.left + b.width / 2; });
      rest.forEach((center, i) => {
        const d = e.clientX - center;
        if (dockSprings[i]) drive(dockSprings[i], 1 + 0.46 * Math.exp(-(d * d) / (2 * 58 * 58)));
      });
    });
    dock.addEventListener('pointerleave', () => { rest = null; dockSprings.forEach((s) => drive(s, 1)); });
  })();

  /* Drag an icon to move it: pages among pages, tools among tools. A press that does not move stays a click. */
  let drag = null, justDragged = false;
  $('#dock').addEventListener('dragstart', (e) => e.preventDefault());
  $('#dock').addEventListener('pointerdown', (e) => {
    const el = e.target.closest('.dock-item[data-page], .dock-item[data-tool]');
    if (el && e.button === 0) drag = { el, id: e.pointerId, x0: e.clientX, moved: false, shift: 0, grab: 0 };
  });
  $('#dock').addEventListener('pointermove', (e) => {
    if (!drag || e.pointerId !== drag.id) return;
    const el = drag.el;
    if (!drag.moved) {
      if (Math.abs(e.clientX - drag.x0) < 6) return;
      drag.moved = true;
      drag.grab = drag.x0 - el.getBoundingClientRect().left;
      el.setPointerCapture(e.pointerId);
      el.classList.add('dragging');
      $('#dock').classList.add('sorting');
      closeDockMenu();
      dockSprings.forEach((s) => drive(s, 1));
    }
    const peers = $$(el.dataset.page ? '.dock-item[data-page]' : '.dock-item[data-tool]', $('#dock'));
    const before = new Map(peers.map((p) => [p, p.getBoundingClientRect().left]));
    // Past the middle of a neighbour, the icon takes its place.
    for (const p of peers) {
      if (p === el) continue;
      const b = p.getBoundingClientRect(), mid = b.left + b.width / 2;
      const left = el.compareDocumentPosition(p) & Node.DOCUMENT_POSITION_PRECEDING;
      if (left && e.clientX < mid) { p.before(el); break; }
      if (!left && e.clientX > mid) p.after(el);
    }
    peers.forEach((p) => {
      const dx = p === el ? 0 : before.get(p) - p.getBoundingClientRect().left;
      if (dx) p.animate([{ translate: dx + 'px 0' }, { translate: '0 0' }], { duration: 170, easing: 'cubic-bezier(.2,.8,.2,1)' });
    });
    drag.shift = e.clientX - drag.grab - (el.getBoundingClientRect().left - drag.shift);
    el.style.translate = drag.shift + 'px 0';
  });
  async function endDrag(cancel) {
    const d = drag;
    drag = null;
    if (!d || !d.moved) return;
    // The drag ends in a click on the icon, and that click must not open it.
    justDragged = true;
    setTimeout(() => { justDragged = false; }, 0);
    d.el.classList.remove('dragging');
    d.el.style.translate = '';
    $('#dock').classList.remove('sorting');
    if (cancel) { renderDock(); return; }
    try {
      await toolAction({ action: 'order', pages: $$('.dock-item[data-page]', $('#dock')).map((x) => x.dataset.page), tools: $$('.dock-item[data-tool]', $('#dock')).map((x) => x.dataset.tool) });
    } catch (err) { toast(err.message); loadTools(true); }
  }
  $('#dock').addEventListener('pointerup', () => endDrag(false));
  $('#dock').addEventListener('pointercancel', () => endDrag(true));
  $('#dock').addEventListener('click', (e) => { if (justDragged) { e.preventDefault(); e.stopPropagation(); } }, true);

  /* Right-click: on an icon it only takes it out, anywhere else on the dock it offers what can come in. */
  const menuBtn = (act, id, ic, label, extra) => '<button type="button" role="menuitem" data-do="' + act + '" data-id="' + esc(id) + '"' + (extra || '') + '>' + ic + '<span>' + esc(label) + '</span></button>';
  function dockMenuHtml(item) {
    const page = item && item.dataset.page ? ROUTES.find((r) => r.id === item.dataset.page) : null;
    const tool = item && item.dataset.tool ? toolById(item.dataset.tool) : null;
    if (page) return page.id === 'home' ? '<p class="ctx-note">Home always stays in the dock.</p>' : menuBtn('page', page.id, icon('minus'), 'Remove from dock', ' data-on="0"');
    if (tool) return menuBtn('tool', tool.id, icon('minus'), 'Remove from dock', ' data-on="0"');
    // Pages and tools alike, ours or not.
    const pagesOut = ROUTES.filter((r) => HIDDEN_PAGES.includes(r.id));
    const toolsOut = TOOLS.filter((t) => !t.pinned);
    // An outside app that is not on any list yet, such as WhatsApp.
    const newApp = '<hr>' + menuBtn('new', '', icon('plus'), 'New app…');
    if (!pagesOut.length && !toolsOut.length) return '<p class="ctx-note">Everything is in the dock.</p>' + newApp;
    return '<h4>Add to dock</h4><div class="ctx-list">'
      + pagesOut.map((r) => menuBtn('page', r.id, icon(r.id), r.label, ' data-on="1" style="--tone:' + r.tone + '"')).join('')
      + toolsOut.map((t) => '<button type="button" role="menuitem" data-do="tool" data-id="' + esc(t.id) + '" data-on="1">' + toolIconHtml(t, 'ctx-icon') + '<span>' + esc(t.name) + '</span><small>' + esc(t.group) + '</small></button>').join('')
      + '</div>' + newApp;
  }
  function newAppForm() {
    const m = $('#dock-menu');
    m.innerHTML = '<form class="ctx-form" id="new-app" autocomplete="off"><h4>New app in the dock</h4>'
      + '<input id="new-app-name" maxlength="40" placeholder="Name, for example WhatsApp" required>'
      + '<input id="new-app-url" placeholder="Address, for example web.whatsapp.com" required>'
      + '<p class="ctx-note" id="new-app-error" hidden></p>'
      + '<div class="ctx-actions"><button class="btn primary" type="submit">Add</button><button class="btn" type="button" data-cancel>Cancel</button></div></form>';
    m.style.top = Math.round(Math.max(8, Number(m.dataset.anchor) - m.offsetHeight - 12)) + 'px';
    $('#new-app-name').focus();
  }
  function openDockMenu(item, x, y) {
    const m = $('#dock-menu');
    m.innerHTML = dockMenuHtml(item);
    m.setAttribute('aria-label', 'Dock');
    m.hidden = false;
    // Above the item it belongs to, so a keyboard opening without a pointer lands in the same place.
    if (item) { const b = item.getBoundingClientRect(); x = b.left + b.width / 2; y = b.top; }
    m.dataset.anchor = y;
    m.style.left = Math.round(Math.max(8, Math.min(x - m.offsetWidth / 2, innerWidth - m.offsetWidth - 8))) + 'px';
    m.style.top = Math.round(Math.max(8, y - m.offsetHeight - 12)) + 'px';
    const first = m.querySelector('button');
    if (first) first.focus();
  }
  // Right-click on a Home card: the same menu, at the pointer, with the one thing a card can do.
  function openCardMenu(c, x, y) {
    const m = $('#dock-menu');
    m.innerHTML = c.id === 'quiet' ? '<p class="ctx-note">Nothing to remove.</p>' : menuBtn('card', c.id, icon('minus'), 'Remove from Home');
    m.setAttribute('aria-label', 'Card');
    m.hidden = false;
    m.style.left = Math.round(Math.max(8, Math.min(x, innerWidth - m.offsetWidth - 8))) + 'px';
    m.style.top = Math.round(Math.max(8, Math.min(y, innerHeight - m.offsetHeight - 8))) + 'px';
    const first = m.querySelector('button');
    if (first) first.focus();
  }
  // Off Home, or back. The server picks the next card to fill the gap, so Home is read again right away.
  async function setCardRemoved(id, removed) {
    const res = await fetch('/api/tools', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Leitstand': '1' }, body: JSON.stringify({ action: 'card', id, removed }) });
    const j = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(j.error || 'The server answered ' + res.status);
    await load();
  }
  async function removeCard(id) {
    await setCardRemoved(id, true);
    toast('Removed from Home. Today lists it if you want it back.', { label: 'Undo', run: () => setCardRemoved(id, false) });
  }
  const closeDockMenu = () => { $('#dock-menu').hidden = true; };
  $('#dock').addEventListener('contextmenu', (e) => { e.preventDefault(); openDockMenu(e.target.closest('.dock-item'), e.clientX, e.clientY); });
  $('#dock-menu').addEventListener('contextmenu', (e) => e.preventDefault());
  $('#dock-menu').addEventListener('click', async (e) => {
    if (e.target.closest('[data-cancel]')) { closeDockMenu(); return; }
    const b = e.target.closest('button[data-do]');
    if (!b) return;
    if (b.dataset.do === 'new') { newAppForm(); return; }
    const id = b.dataset.id;
    closeDockMenu();
    try {
      if (b.dataset.do === 'tool') await toolAction({ action: 'pin', id, pinned: b.dataset.on === '1' });
      else if (b.dataset.do === 'page') await toolAction({ action: 'page', id, docked: b.dataset.on === '1' });
      else if (b.dataset.do === 'card') await removeCard(id);
    } catch (err) { toast(err.message); }
  });
  // A new outside app goes straight into the dock, with its own logo. Ours are added in All tools.
  $('#dock-menu').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = $('#new-app-name').value.trim();
    let url = $('#new-app-url').value.trim();
    if (url && !/^[a-z]+:/i.test(url)) url = 'https://' + url;
    try {
      await toolAction({ action: 'add', name, url, group: 'Daily', pinned: true, own: false });
      closeDockMenu();
      toast(name + ' is in the dock. Drag it to where you want it.');
    } catch (err) {
      const box = $('#new-app-error');
      box.textContent = err.message;
      box.hidden = false;
    }
  });
  document.addEventListener('mousedown', (e) => { if (!$('#dock-menu').hidden && !e.target.closest('#dock-menu')) closeDockMenu(); });
  window.addEventListener('blur', closeDockMenu);
  window.addEventListener('resize', closeDockMenu);
  window.addEventListener('hashchange', closeDockMenu);

  /* Links. A note opens here, in the Library. The vault is the back end and stays out of sight. */
  const noteHref = (path) => '#library/n/' + path.split('/').map(encodeURIComponent).join('/');
  function cardTarget(c) {
    if (c.route) return '#' + c.route;
    if (c.note) return noteHref(c.note);
    return '';
  }
  const routeLabel = (r) => (r.startsWith('board/card:') ? 'card' : r.split('/')[0]);

  /* Photos on the Home cards (web/photos, sources and licences in credits.json). Each urgency level has its own set.
     A card's first choice comes from its id and the date, so the set reshuffles every day; a photo another card
     already took passes to the next free one, so no two cards on Home share a picture. A card without a free photo
     keeps its drawn scene. */
  let PHOTOS = null, photoKey = '', photoPlan = {};
  fetch('/photos/credits.json').then((r) => (r.ok ? r.json() : [])).then((list) => {
    PHOTOS = {};
    list.forEach((p) => { (PHOTOS[p.level] = PHOTOS[p.level] || []).push(p.id); });
    photoKey = '';
    if (S && route === 'home') renderHome();
  }).catch(() => { PHOTOS = {}; });
  function photoOf(c) {
    if (!PHOTOS || !S) return null;
    const cards = S.focus.length ? S.focus : [quietCard()];
    const key = S.today + '|' + cards.map((x) => x.id + ':' + x.level).join('|');
    if (key !== photoKey) {
      photoKey = key;
      photoPlan = {};
      const taken = new Set();
      cards.forEach((x) => {
        const pool = PHOTOS[x.level] || [];
        const start = pool.length ? hashOf(x.id + '|' + S.today) % pool.length : 0;
        for (let k = 0; k < pool.length; k++) {
          const id = pool[(start + k) % pool.length];
          if (!taken.has(id)) { taken.add(id); photoPlan[x.id] = id; break; }
        }
      });
    }
    return photoPlan[c.id] || null;
  }
  function cardPicture(c, w, h) {
    const id = photoOf(c);
    if (!id) return Art.scene({ seed: c.id, kind: c.kind, level: c.level, heat: c.heat, fog: c.fog }, w, h);
    const img = new Image();
    img.className = 'photo';
    img.alt = '';
    img.decoding = 'async';
    img.src = '/photos/' + id + '.webp';
    return img;
  }

  /* Home: the deck */
  function originHtml(c) {
    return '<span class="origin"><span class="dot ' + esc(c.sourceState) + '"></span>' + esc(c.source) + ' · ' + esc(c.sourceAge) + '</span>';
  }
  function cardHtml(c, i, total) {
    const accent = Art.tone(c);
    const target = cardTarget(c);
    const label = c.route ? 'Open ' + routeLabel(c.route) : 'Open note';
    const link = target ? '<a class="open" href="' + esc(target) + '">' + esc(label) + icon('arrow').replace('<svg', '<svg width="16" height="16"') + '</a>' : '';
    const tool = relatedTool(c);
    // A meeting with a video link joins from here. The calendar is not needed for that.
    const join = c.join ? '<a class="open join" href="' + esc(c.join) + '" target="_blank" rel="noopener noreferrer">Join call</a>' : '';
    const actions = (tool || link || join) ? '<div class="card-actions">' + join + (tool ? '<button class="open' + (link || join ? ' ghost' : '') + '" type="button" data-open-tool="' + esc(tool.id) + '">Open ' + esc(tool.name) + '</button>' : '') + (join ? link.replace('class="open"', 'class="open ghost"') : link) + '</div>' : '';
    return '<article class="card" data-i="' + i + '" style="--c:' + accent + '" role="group" aria-roledescription="slide" aria-label="' + (i + 1) + ' of ' + total + '">'
      + '<div class="surface"><div class="art"><div class="scrim"></div><div class="shine"></div></div>'
      + '<div class="copy"><div class="eyebrow"><span class="tag">' + esc(c.eyebrow) + '</span>' + (c.tag ? '<span class="tag ghost">' + esc(c.tag) + '</span>' : '') + '</div>'
      + '<h2' + (c.title.length > 34 ? ' class="long"' : '') + '>' + esc(c.title) + '</h2>' + (c.body ? '<p class="body">' + esc(c.body) + '</p>' : '')
      + '<div class="foot"><span class="why">' + esc(c.why) + '</span>' + originHtml(c) + '</div></div>'
      + '<span class="count">' + String(i + 1).padStart(2, '0') + ' / ' + String(total).padStart(2, '0') + '</span>' + actions
      + '</div><div class="dim"></div></article>';
  }
  /* Home is up to ten slides: what really needs you, then the next real to-dos. The server picks them. */
  let deckCards = [];
  // Sources that are on but could not be read. A calendar nobody connected has its own hint below the cards.
  // One that was read and only carries no date has no note.
  const unread = () => S.sources.filter((s) => s.state === 'unknown' && s.note && (s.id !== 'calendar' || S.calendarConnected));
  const lostNow = () => unread().filter((s) => s.note !== 'still loading');
  // With nothing to read, a calm screen would claim something Brento cannot know.
  const nothingYet = () => !S.calendarConnected && !S.sources.some((s) => s.id !== 'calendar');
  // Only what Brento has looked at.
  function quietWhy() {
    const has = (id) => S.sources.some((s) => s.id === id), parts = [];
    if (S.calendarConnected) parts.push('no meeting');
    if (has('tasks') || has('open-items')) parts.push('no deadline');
    if (has('board')) parts.push('no HIGH or MID card to do');
    const text = parts.length > 1 ? parts.slice(0, -1).join(', ') + ' and ' + parts[parts.length - 1] : parts[0] || 'nothing with a date';
    return text.charAt(0).toUpperCase() + text.slice(1) + '.';
  }
  function quietCard() {
    const notes = !S.pagesOff.includes('library'), missing = 'Connect your calendar, your ' + (notes ? 'tasks' : 'notes') + ' or your board';
    if (nothingYet()) return { id: 'quiet', kind: 'pipeline', level: 'calm', eyebrow: 'Start here', tag: '', title: notes ? 'No dates are connected yet' : 'Nothing is connected yet',
      body: missing + (S.phone ? ' in Brento on the computer.' : ', and this page tells you what needs you.'),
      why: 'Until then there is nothing Brento could read.', source: 'Sources', sourceState: 'unknown', sourceAge: 'none yet', route: S.phone ? 'today' : 'settings', heat: 0, fog: 0.08 };
    const lost = unread();
    if (lost.length || S.vaultProblem) {
      const loading = !S.vaultProblem && lost.every((s) => s.note === 'still loading');
      return { id: 'quiet', kind: 'pipeline', level: 'calm', eyebrow: 'N/A', tag: '', title: loading ? 'Still reading' : 'Not everything could be read',
        body: lost.length ? lost.map((s) => s.label + (s.note ? ': ' + s.note : '')).join('. ') + '.' : S.vaultProblem.charAt(0).toUpperCase() + S.vaultProblem.slice(1) + '.',
        why: 'So Brento cannot say that nothing needs you.', source: 'Sources', sourceState: 'unknown', sourceAge: 'age unknown', route: 'brain', heat: 0, fog: 0.08 };
    }
    const dated = S.deadlines.filter((d) => d.due >= S.today).sort((a, b) => a.due.localeCompare(b.due));
    return { id: 'quiet', kind: 'pipeline', level: 'calm', eyebrow: 'All quiet', tag: '', title: 'Nothing needs preparing',
      body: dated.length ? 'Next date: ' + dated[0].name + ', ' + weekdayOf(dated[0].due) + ' ' + dayMonth(dated[0].due) : '',
      why: quietWhy(), source: 'Today', sourceState: 'fresh', sourceAge: 'live', route: 'today', heat: 0, fog: 0.08 };
  }
  // A tool whose name appears in the title, such as a client's deck for a call with that client.
  function relatedTool(c) {
    const title = (c.title || '').toLowerCase();
    return TOOLS.find((t) => { const word = t.name.split(' ')[0].toLowerCase(); return t.group !== 'Daily' && word.length >= 5 && title.includes(word); }) || null;
  }
  function renderHome() {
    deckCards = S.focus.length ? S.focus : [quietCard()];
    const cards = deckCards, many = cards.length > 1;
    cur = clamp(cur, 0, cards.length - 1);
    $('#view').innerHTML = '<section class="deck' + (firstHome ? ' rise' : '') + '" id="deck" tabindex="0" aria-roledescription="carousel" aria-label="What needs you">'
      + cards.map((c, i) => cardHtml(c, i, cards.length)).join('')
      + (many ? '<button class="deck-btn prev" type="button" aria-label="Previous card">' + icon('left') + '</button>'
      + '<button class="deck-btn next" type="button" aria-label="Next card">' + icon('right') + '</button>' : '') + '</section>'
      + '<div class="deck-foot">' + (many ? '<div class="pips">' + cards.map((c, i) => '<button type="button" data-go="' + i + '" aria-label="Card ' + (i + 1) + '"></button>').join('') + '</div>' : '')
      // No key hints under the cards (owner, 08.11.2026: clutter). Only a broken calendar speaks up, because meetings would be missing.
      + (S.calendarConnected ? '' : '<div class="hints"><span><a href="' + (S.phone ? '#today' : '#setup/3') + '">Calendar not connected, so meetings are missing</a></span></div>')
      + (S.focus.length && (lostNow().length || S.vaultProblem) ? '<div class="hints"><span><a href="#brain">N/A: ' + esc(lostNow().map((s) => s.label).join(', ') || S.vaultProblem) + '</a></span></div>' : '') + '</div>';
    firstHome = false;
    bindDeck();
  }

  let deckApi = null;
  function bindDeck() {
    const deck = $('#deck');
    const els = $$('.card', deck);
    const cards = deckCards;

    function paintCard(i) {
      const el = els[i];
      if (!el || el.dataset.painted) return;
      el.dataset.painted = '1';
      const c = cards[i];
      const wide = window.innerWidth > 760;
      const picture = cardPicture(c, wide ? 1320 : 760, wide ? 760 : 1000);
      // A photo arrives after the card is shown. When it is the card in front, the glow behind the page follows it.
      if (picture.tagName === 'IMG') picture.onload = () => { if (i === cur) setAmbient(picture, Art.tone(c)); };
      $('.art', el).prepend(picture);
    }
    function layout(pos) {
      const width = els[0].offsetWidth;
      els.forEach((el, i) => {
        const o = i - pos, a = Math.abs(o);
        const x = o * (width * 0.86);
        const z = -Math.min(a, 2.4) * 300;
        const ry = clamp(-o * 15, -30, 30);
        el.style.transform = 'translate(-50%,-50%) translate3d(' + x.toFixed(1) + 'px,0,' + z.toFixed(1) + 'px) rotateY(' + ry.toFixed(2) + 'deg)';
        el.style.zIndex = String(100 - Math.round(a * 10));
        el.style.opacity = a > 2.3 ? '0' : '1';
        el.style.visibility = a > 2.6 ? 'hidden' : 'visible';
        el.style.setProperty('--dim-a', clamp(a * 0.62, 0, 0.82).toFixed(3));
      });
    }
    function settle(i, instant) {
      cur = clamp(i, 0, els.length - 1);
      els.forEach((el, n) => {
        el.classList.toggle('active', n === cur);
        el.setAttribute('aria-hidden', n === cur ? 'false' : 'true');
        $$('a,button', el).forEach((link) => { link.tabIndex = n === cur ? 0 : -1; });
      });
      $$('.pips button', deck.parentElement).forEach((b, n) => b.classList.toggle('on', n === cur));
      layout(cur);
      paintCard(cur);
      setAmbient($('canvas, img.photo', els[cur]), Art.tone(cards[cur]));
      // Neighbours are painted right after, so the first card never waits for the others.
      setTimeout(() => { paintCard(cur + 1); paintCard(cur - 1); }, instant ? 0 : 200);
    }

    /* Tilt, on the mouse only */
    let tiltEl = null;
    const tiltApply = () => {
      if (!tiltEl) return;
      tiltEl.style.setProperty('--ry', (tilt.x.x * 7).toFixed(3) + 'deg');
      tiltEl.style.setProperty('--rx', (-tilt.y.x * 5).toFixed(3) + 'deg');
      tiltEl.style.setProperty('--px', tilt.x.x.toFixed(3));
      tiltEl.style.setProperty('--py', tilt.y.x.toFixed(3));
      tiltEl.style.setProperty('--lift', (tilt.on.x * 16).toFixed(2) + 'px');
      tiltEl.style.setProperty('--shine', tilt.on.x.toFixed(3));
    };
    const tilt = { x: makeSpring(0, tiltApply, 120, 16), y: makeSpring(0, tiltApply, 120, 16), on: makeSpring(0, tiltApply, 120, 18) };
    deck.addEventListener('pointermove', (e) => {
      if (e.pointerType !== 'mouse' || dragging || !motionFull()) return;
      const active = els[cur], box = active.getBoundingClientRect();
      const inside = e.clientX >= box.left && e.clientX <= box.right && e.clientY >= box.top && e.clientY <= box.bottom;
      if (!inside) { drive(tilt.x, 0); drive(tilt.y, 0); drive(tilt.on, 0); return; }
      tiltEl = active;
      const nx = (e.clientX - box.left) / box.width - 0.5, ny = (e.clientY - box.top) / box.height - 0.5;
      active.style.setProperty('--mx', ((nx + 0.5) * 100).toFixed(1) + '%');
      active.style.setProperty('--my', ((ny + 0.5) * 100).toFixed(1) + '%');
      drive(tilt.x, nx * 2); drive(tilt.y, ny * 2); drive(tilt.on, 1);
    });
    deck.addEventListener('pointerleave', () => { drive(tilt.x, 0); drive(tilt.y, 0); drive(tilt.on, 0); });

    /* Drag and swipe */
    let dragging = false, downX = 0, downY = 0, moved = 0, lastX = 0, lastT = 0, speed = 0, pointerId = null;
    deck.addEventListener('pointerdown', (e) => {
      if (e.button !== 0 || e.target.closest('a,button')) return;
      pointerId = e.pointerId; downX = lastX = e.clientX; downY = e.clientY; lastT = e.timeStamp; moved = 0; speed = 0;
    });
    deck.addEventListener('pointermove', (e) => {
      if (e.pointerId !== pointerId) return;
      const dx = e.clientX - downX;
      if (!dragging) {
        if (Math.abs(dx) < 7 || Math.abs(e.clientY - downY) > Math.abs(dx)) return;
        dragging = true;
        deck.classList.add('dragging');
        deck.setPointerCapture(pointerId);
        drive(tilt.x, 0); drive(tilt.y, 0); drive(tilt.on, 0);
      }
      moved = dx;
      speed = (e.clientX - lastX) / Math.max(1, e.timeStamp - lastT);
      lastX = e.clientX; lastT = e.timeStamp;
      const width = els[0].offsetWidth * 0.86;
      let pos = cur - dx / width;
      if (pos < 0) pos *= 0.35;
      if (pos > els.length - 1) pos = els.length - 1 + (pos - els.length + 1) * 0.35;
      layout(pos);
      paintCard(Math.round(pos));
    });
    const release = (e) => {
      if (e.pointerId !== pointerId) return;
      pointerId = null;
      if (!dragging) return;
      dragging = false;
      deck.classList.remove('dragging');
      const width = els[0].offsetWidth * 0.86;
      const flick = Math.abs(speed) > 0.45 ? -Math.sign(speed) : 0;
      settle(Math.round(cur - moved / width) === cur ? cur + flick : Math.round(cur - moved / width));
    };
    deck.addEventListener('pointerup', release);
    deck.addEventListener('pointercancel', release);
    deck.addEventListener('click', (e) => {
      if (Math.abs(moved) > 7) { moved = 0; return; }
      const prev = e.target.closest('.deck-btn.prev'), next = e.target.closest('.deck-btn.next');
      if (prev) return settle(cur - 1);
      if (next) return settle(cur + 1);
      const card = e.target.closest('.card');
      if (card && !card.classList.contains('active')) settle(Number(card.dataset.i));
    });
    deck.addEventListener('contextmenu', (e) => {
      const card = e.target.closest('.card');
      if (!card) return;
      e.preventDefault();
      openCardMenu(cards[Number(card.dataset.i)], e.clientX, e.clientY);
    });
    $$('.pips button', deck.parentElement).forEach((b) => { b.onclick = () => settle(Number(b.dataset.go)); });
    let wheelAt = 0;
    deck.addEventListener('wheel', (e) => {
      const delta = Math.abs(e.deltaX) > Math.abs(e.deltaY) ? e.deltaX : e.deltaY;
      if (Math.abs(delta) < 12) return;
      e.preventDefault();
      if (e.timeStamp - wheelAt < 380) return;
      wheelAt = e.timeStamp;
      settle(cur + Math.sign(delta));
    }, { passive: false });

    deckApi = {
      step: (d) => settle(cur + d),
      first: () => settle(0),
      // Enter opens the card, never the call: joining stays a deliberate click.
      open: () => { const link = $('.open:not(.join)', els[cur]); if (link) link.click(); },
      remove: () => { const c = cards[cur]; if (c && c.id !== 'quiet') removeCard(c.id).catch((err) => toast(err.message)); }
    };
    els.forEach((el) => { el.style.transition = 'none'; });
    settle(cur, true);
    requestAnimationFrame(() => requestAnimationFrame(() => els.forEach((el) => { el.style.transition = ''; })));
  }

  /* Shared page parts */
  function pageHead(title, sub, actions) {
    return '<header class="ph"><h1>' + esc(title) + '</h1>' + (actions ? '<div class="ph-actions">' + actions + '</div>' : '') + (sub ? '<p>' + esc(sub) + '</p>' : '') + '</header>';
  }
  function tile(label, value, note, tone) {
    const na = value === null || value === undefined;
    return '<div class="tile ' + (tone || '') + '"><small>' + esc(label) + '</small><strong' + (na ? ' class="na"' : '') + '>' + (na ? 'N/A' : esc(value)) + '</strong>' + (note ? '<em>' + esc(note) + '</em>' : '') + '</div>';
  }
  function srcLine(id) {
    const s = S.sources.find((x) => x.id === id);
    if (!s) return '';
    return '<p class="note"><span class="origin"><span class="dot ' + s.state + '"></span>' + esc(s.path) + ' · ' + (s.ageDays === null ? 'age unknown' : s.ageDays === 0 ? 'read today' : s.ageDays + ' days old') + (s.note ? ' · ' + esc(s.note) : '') + '</span></p>';
  }
  function pageWrap(html) {
    ambientOff();
    $('#view').innerHTML = '<div class="page"><div class="page-inner">' + html + '</div></div>';
  }
  /* A row is a link only when it has somewhere to go. Otherwise it stays still under the pointer. */
  function rowHtml(i, main, end, target) {
    const num = '<span class="num">' + String(i + 1).padStart(2, '0') + '</span><div class="row-main">' + main + '</div>';
    if (!target) return '<div class="row">' + num + '<span class="row-end">' + end + '</span></div>';
    const outward = target.startsWith('http');
    return '<a class="row" href="' + esc(target) + '"' + (outward ? ' target="_blank" rel="noopener noreferrer" title="Opens outside Brento"' : '') + '>' + num + '<span class="row-end">' + end + icon(outward ? 'out' : 'chev') + '</span></a>';
  }
  /* Page data refreshes in the background. The reader keeps their place and whatever they had open. */
  function refreshInPlace() {
    const page = $('.page'), top = page ? page.scrollTop : 0;
    const open = $$('#view details[open]').map((d) => d.dataset.key);
    renderRoute();
    $$('#view details').forEach((d) => { if (open.includes(d.dataset.key)) d.open = true; });
    const next = $('.page');
    if (next) next.scrollTop = top;
  }
  function boardUrl() { return (S.sources.find((s) => s.id === 'board') || {}).url || ''; }
  function agePill(i) {
    if (!i.agesTo) return '';
    if (!i.agesOn) return '<span class="pill">clock starts at the next run</span>';
    return '<span class="pill">to ' + esc(i.agesTo) + (i.agesOn <= S.today ? ' at the next run' : ' on ' + dayMonth(i.agesOn)) + '</span>';
  }
  function ticket(i) {
    return '<details class="ticket' + (i.passed ? ' dead' : '') + '" data-key="' + esc(i.status + i.title) + '" data-card="' + esc(i.id) + '"><summary>' + esc(i.title) + '<div class="pills"><span class="pill">' + esc(i.bereich) + '</span>' + (i.assignees || []).map((a) => '<span class="pill' + (i.mine ? ' ok' : '') + '">@' + esc(a) + '</span>').join('') + (i.passed ? '<span class="pill warn">date passed</span>' : '') + agePill(i) + '</div></summary>'
      + '<div class="ticket-body">' + (i.body ? esc(i.body) : 'No text on this card.') + '</div>'
      + '<a class="ticket-link" href="' + esc(i.url || boardUrl()) + '" target="_blank" rel="noopener noreferrer">Open on GitHub to move it</a></details>';
  }
  function lane(name, list) {
    return '<section class="lane"><h3>' + esc(name) + '<span class="pill">' + list.length + '</span></h3><div class="lane-list">' + (list.map(ticket).join('') || '<div class="note">Empty.</div>') + '</div></section>';
  }

  /* Today: one directive, then the order. */
  function renderToday() {
    const [first, ...rest] = S.cards;
    const waiting = S.open.items.filter((m) => !m.mine);
    const dated = S.open.items.filter((m) => m.due).map((m) => ({ due: m.due, time: '', name: m.name, sub: m.mine ? 'yours' : 'waiting on ' + m.owner }))
      .concat(S.events.map((e) => ({ due: e.date, time: e.time, name: e.title, sub: (e.zone ? 'time in ' + e.zone + ', ' : '') + (e.people > 1 ? 'with ' + (e.people - 1) + (e.people === 2 ? ' other' : ' others') : 'calendar'), join: e.join || '' })))
      .sort((a, b) => (a.due + a.time).localeCompare(b.due + b.time));
    let html = pageHead('Today', 'Fixed rules set this order: your own deadlines first, then what the morning brief names, then what has gone stale. Nothing here moves by itself.');
    const dates = '<aside class="panel"><h3>Dates<span class="pill">' + dated.length + '</span></h3>' + (dated.map((m) => '<div class="date-row"><time>' + weekdayOf(m.due) + ' ' + dayMonth(m.due) + (m.time ? '<br>' + esc(m.time) : '') + '</time><div>' + esc(m.name) + '<small>' + esc(m.sub) + '</small>'
      + (m.join ? '<a class="join-link" href="' + esc(m.join) + '" target="_blank" rel="noopener noreferrer">Join call</a>' : '') + '</div></div>').join('') || '<div class="note">No dates ahead.</div>')
      + calendarBlock() + '</aside>';
    if (first) {
      const target = cardTarget(first);
      html += '<div class="today-grid"><section class="do-next" style="--c:' + Art.accent(first.kind) + '"><div class="label">DO NEXT<span class="pill">' + esc(first.eyebrow) + '</span>' + (first.tag ? '<span class="pill">' + esc(first.tag) + '</span>' : '') + '</div>'
        + '<h2>' + esc(first.title) + '</h2>' + (first.body ? '<p>' + esc(first.body) + '</p>' : '') + '<div class="why">' + esc(first.why) + '</div>'
        + '<div class="next-actions">' + (target ? '<a class="btn primary" href="' + esc(target) + '">' + (first.route ? 'Open ' + esc(routeLabel(first.route)) : 'Open note') + '</a>' : '')
        + '<button class="btn" type="button" data-ask="' + esc('Give me the smallest first step, five minutes at most, for: ' + first.title + '. ' + (first.body || '')) + '">Ask for the smallest first step</button>' + originHtml(first) + '</div></section>' + dates + '</div>';
    } else {
      html += '<div class="today-grid"><div class="empty">Nothing has earned the top spot.</div>' + dates + '</div>';
    }
    html += '<h2 class="section-title">Then <span>' + rest.length + ', in this order</span></h2><div class="rows">'
      + (rest.map((c, i) => rowHtml(i, '<b>' + esc(c.title) + '</b><small>' + esc(c.why) + '</small>', '<span class="pill">' + esc(c.eyebrow) + '</span>', cardTarget(c))).join('') || '<div class="empty">Nothing else.</div>') + '</div>';
    if (waiting.length) {
      html += '<h2 class="section-title">Waiting on others <span>' + waiting.length + '</span></h2><div class="rows">'
        + waiting.map((m, i) => rowHtml(i, '<b>' + esc(m.name) + '</b><small>' + esc(m.next) + '</small>', '<span class="pill">' + esc(m.owner) + (m.due ? ', ' + dayMonth(m.due) : '') + '</span>', m.notePath ? noteHref(m.notePath) : '')).join('') + '</div>';
    }
    html += scheduleHtml();
    // What was taken off Home by hand, so a click by mistake is never a loss.
    if (S.removedCards && S.removedCards.length) {
      html += '<h2 class="section-title">Removed from Home <span>' + S.removedCards.length + ', by you</span></h2><div class="rows">'
        + S.removedCards.map((c, i) => '<div class="row"><span class="num">' + String(i + 1).padStart(2, '0') + '</span><div class="row-main"><b>' + esc(c.title) + '</b><small>Off Home until you put it back or its title changes</small></div>'
          + '<span class="row-end"><button class="btn" type="button" data-putback="' + esc(c.id) + '">Put back</button></span></div>').join('') + '</div>';
    }
    pageWrap(html);
    bindAskButtons();
    bindCalendar();
    $$('#view [data-putback]').forEach((b) => {
      b.onclick = async () => {
        b.disabled = true;
        try { await setCardRemoved(b.dataset.putback, false); toast('Back on Home.'); } catch (err) { b.disabled = false; toast(err.message); }
      };
    });
  }
  /* One day, reached from the strip. Everything here carries this date, and an empty day says so. */
  function renderDay() {
    const iso = openDay();
    const gap = daysBetween(S.today, iso);
    const rows = S.agenda.filter((a) => a.date === iso);
    const after = S.agenda.find((a) => a.date > iso);
    const step = (n, label, name) => {
      const off = n < 0 && gap <= 0;
      return '<a class="btn icon" href="#day/' + addDays(iso, n) + '" aria-label="' + label + '" title="' + label + '"' + (off ? ' aria-disabled="true" tabindex="-1"' : '') + '>' + icon(name) + '</a>';
    };
    const name = new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' });
    let html = pageHead(name, inDays(gap) + (rows.length ? ', ' + rows.length + (rows.length === 1 ? ' thing' : ' things') + ' on this day.' : '.'), step(-1, 'Previous day', 'left') + step(1, 'Next day', 'right'));
    const dayRow = (a, i) => {
      const end = (a.time ? '<span class="pill">' + esc(a.time) + '</span>' : '') + '<span class="pill' + (a.mine ? ' warn' : '') + '">' + esc(a.label) + '</span>';
      const sub = a.sub ? '<small>' + esc(a.sub) + '</small>' : '';
      const target = a.url || cardTarget(a);
      if (!a.join) return rowHtml(i, '<b>' + esc(a.title) + '</b>' + sub, end, target);
      // A call row holds a button, so the row itself is no link. Its note stays one click away on the title.
      return '<div class="row"><span class="num">' + String(i + 1).padStart(2, '0') + '</span><div class="row-main"><b>' + (target ? '<a href="' + esc(target) + '">' + esc(a.title) + '</a>' : esc(a.title)) + '</b>' + sub + '</div>'
        + '<span class="row-end">' + end + '<a class="btn primary" href="' + esc(a.join) + '" target="_blank" rel="noopener noreferrer">Join call</a></span></div>';
    };
    html += rows.length ? '<div class="rows">' + rows.map(dayRow).join('') + '</div>'
      : '<div class="empty">' + (gap < 0 ? 'This day has passed. Only days from today on are listed.' : 'Nothing dated on this day.')
        + (after ? ' Next: <a class="day-next" href="#day/' + after.date + '">' + esc(after.title) + ', ' + weekdayOf(after.date) + ' ' + dayMonth(after.date) + '</a>' : '') + '</div>';
    if (!S.calendarConnected) html += '<section class="panel day-cal"><h3>Calendar not connected<span class="pill warn">meetings are missing here</span></h3>' + calendarBlock() + '</section>';
    html += '<p class="note">Open matters, board cards with a real date, appointments from the application tracker' + (S.calendarConnected ? ' and one-off calendar events. Recurring series are left out' : '') + '. Reaches ' + S.agendaDays + ' days ahead.</p>';
    pageWrap(html);
    bindCalendar();
  }
  function calendarBlock() {
    const src = S.sources.find((s) => s.id === 'calendar') || { state: 'fresh' };
    // A phone only reads. The calendar is connected or disconnected on the computer.
    if (S.phone) return S.calendarConnected ? '' : '<p class="note">No calendar connected yet. Connect it in Brento on your computer.</p>';
    if (S.calendarConnected) return '<p class="note">Calendar ' + (src.state === 'fresh' ? 'connected' : esc(src.note || 'connected')) + '. <button class="link-btn" type="button" id="cal-off">Disconnect</button></p>';
    return '<p class="note">No calendar connected, so meetings are missing. <a class="link-btn" href="#setup/3">Connect your calendar</a></p>';
  }
  function bindCalendar() {
    const off = $('#cal-off');
    if (off) off.onclick = () => post('/api/calendar', { disconnect: true }).then(() => { stateText = ''; load(); if (route === 'settings') renderSettings(); }).catch((err) => toast(err.message));
  }

  /* Projects */
  const STATE = { active: ['Active', 'ok'], quiet: ['Quiet', ''], demo: ['Demo only', 'warn'], down: ['Down', 'bad'], unknown: ['N/A', ''] };
  function progressHtml(p) {
    if (!p.total) return '<span class="na-text" title="No cards on the board for this project">N/A</span>';
    const pct = Math.round(100 * p.done / p.total);
    return '<div class="progress" title="' + p.done + ' of ' + p.total + ' board cards finished"><div class="bar"><i style="width:' + pct + '%"></i></div><span>' + p.done + '/' + p.total + '</span></div>';
  }
  function dateCell(iso) { return iso ? '<span class="t-date">' + dayMonth(iso) + '</span>' : '<span class="t-date na-text">none</span>'; }
  function projectRow(p) {
    const st = STATE[p.state] || STATE.unknown;
    return '<a class="t-row" href="#projects/' + encodeURIComponent(p.id) + '"><div class="t-name"><span class="avatar" style="--tile:' + tileColor(p.id) + '">' + esc(initials(p.name)) + '</span><div><b>' + esc(p.name) + '</b><small>' + esc(p.detail) + '</small></div></div>'
      + '<div class="t-progress">' + progressHtml(p) + '</div><div>' + dateCell(p.next) + '</div><div class="t-change">' + dateCell(p.changed) + '</div>'
      + '<div class="t-state-col"><span class="state"' + (p.stateWhy ? ' title="' + esc(p.stateWhy) + '"' : '') + '><span class="dot ' + st[1] + '"></span>' + st[0] + '</span></div></a>';
  }
  function sortedProjects() {
    const q = projectQuery.trim().toLowerCase();
    const rows = S.projects.rows.filter((p) => (projectState === 'all' || p.state === projectState) && (!q || (p.name + ' ' + p.detail).toLowerCase().includes(q)));
    const { key, dir } = projectSort;
    const value = (p) => (key === 'progress' ? (p.total ? p.done / p.total : null) : p[key]);
    return rows.sort((a, b) => {
      const x = value(a), y = value(b);
      if (x === null || x === undefined) return (y === null || y === undefined) ? a.name.localeCompare(b.name) : 1;
      if (y === null || y === undefined) return -1;
      return (typeof x === 'number' ? x - y : String(x).localeCompare(String(y))) * dir;
    });
  }
  function paintProjectTable() {
    const box = $('#project-table');
    if (!box) return;
    const rows = sortedProjects();
    const head = (key, label) => '<button type="button" data-sort="' + key + '"' + (projectSort.key === key ? ' aria-sort="' + (projectSort.dir > 0 ? 'ascending' : 'descending') + '"' : '') + '>' + label + (projectSort.key === key ? (projectSort.dir > 0 ? ' ↑' : ' ↓') : '') + '</button>';
    box.innerHTML = '<div class="t-row t-head"><div>' + head('name', 'Project') + '</div><div class="t-progress">' + head('progress', 'Finished cards') + '</div><div>' + head('next', 'Next date') + '</div><div class="t-change">' + head('changed', 'Last change') + '</div><div class="t-state-col">' + head('state', 'State') + '</div></div>'
      + (rows.map(projectRow).join('') || '<div class="empty" style="margin:12px">No project matches.</div>');
    $$('[data-sort]', box).forEach((b) => {
      b.onclick = () => {
        const key = b.dataset.sort;
        // Newest first is the useful start for a "last change" column, earliest first for the rest.
        projectSort = projectSort.key === key ? { key, dir: -projectSort.dir } : { key, dir: key === 'changed' ? -1 : 1 };
        paintProjectTable();
      };
    });
    const count = $('#project-count');
    if (count) count.textContent = rows.length + (rows.length === 1 ? ' project' : ' projects');
  }
  function renderProjects() {
    if (routeId) return renderProject(routeId);
    const all = S.projects.rows;
    const chip = (id, label) => { const n = id === 'all' ? all.length : all.filter((p) => p.state === id).length; return n || id === 'all' ? '<button class="chip" type="button" data-state="' + id + '" aria-pressed="' + (projectState === id) + '">' + label + ' <b>' + n + '</b></button>' : ''; };
    const stray = S.projects.unclaimedIdx.map((n) => S.projects.cards[n]);
    pageWrap(pageHead('Projects', 'Measured from the board, the repo and the note. A project with no cards shows N/A, not a guess.', '<span class="pill" id="project-count"></span>')
      + '<div class="chips"><input class="search" id="project-search" type="search" placeholder="Find a project" aria-label="Find a project" value="' + esc(projectQuery) + '">' + chip('all', 'All') + chip('active', 'Active') + chip('quiet', 'Quiet') + chip('demo', 'Demo only') + chip('down', 'Down') + chip('unknown', 'N/A') + '</div>'
      + '<div class="table" id="project-table"></div>'
      + (stray.length ? '<div class="rows" style="margin-top:12px"><details class="fold" data-key="stray"><summary class="row"><span class="num">' + stray.length + '</span><div class="row-main"><b>Open cards no project claims</b><small>Add them to a project in projects.json in your Brento folder, or move them on the board</small></div><span class="row-end">' + icon('chev') + '</span></summary><div class="fold-body"><div class="lane-list">' + stray.map(ticket).join('') + '</div></div></details></div>' : ''));
    paintProjectTable();
    const input = $('#project-search');
    input.oninput = () => { projectQuery = input.value; paintProjectTable(); };
    $$('[data-state]').forEach((b) => {
      b.onclick = () => {
        projectState = b.dataset.state;
        $$('[data-state]').forEach((x) => x.setAttribute('aria-pressed', String(x.dataset.state === projectState)));
        paintProjectTable();
      };
    });
  }
  function renderProject(id) {
    const p = S.projects.rows.find((x) => x.id === id);
    if (!p) { pageWrap('<a class="back" href="#projects">' + icon('left') + 'Projects</a><div class="empty">No project called ' + esc(id) + '.</div>'); return; }
    const st = STATE[p.state] || STATE.unknown;
    const cards = S.projects.cards;
    const open = p.openIdx.map((n) => cards[n]);
    const done = p.doneIdx.map((n) => cards[n]);
    const tool = p.tool ? toolById(p.tool) : null;
    const links = (tool ? '<button class="btn primary" type="button" id="project-tool">Open ' + esc(tool.name) + '</button>' : '')
      + (p.note ? '<a class="btn" href="' + esc(noteHref(p.note)) + '">Note</a>' : '')
      + (p.repo ? '<a class="btn" href="https://github.com/' + esc(encodeURIComponent(S.githubOwner || '')) + '/' + esc(encodeURIComponent(p.repo)) + '" target="_blank" rel="noopener noreferrer">Repo</a>' : '');
    const other = open.filter((c) => !['HIGH', 'MID', 'LOW'].includes(c.status));
    pageWrap('<a class="back" href="#projects">' + icon('left') + 'Projects</a>'
      + pageHead(p.name, p.detail + (p.stateWhy ? '. ' + p.stateWhy : ''), links)
      + '<div class="tiles">' + tile('State', st[0], null, { ok: 'good', warn: 'warn', bad: 'bad' }[st[1]]) + tile('Open cards', p.total ? open.length : null, p.high ? p.high + ' HIGH' : '') + tile('Finished cards', p.total ? p.done : null) + tile('Next date', p.next ? dayMonth(p.next) : null) + tile('Last change', p.changed ? dayMonth(p.changed) : null) + '</div>'
      + (p.total ? '<div class="lanes">' + ['HIGH', 'MID', 'LOW'].map((n) => lane(n, open.filter((c) => c.status === n))).join('') + '</div>'
        + (other.length ? '<h2 class="section-title">No status <span>' + other.length + '</span></h2><div class="lane-list">' + other.map(ticket).join('') + '</div>' : '')
        + (done.length ? '<div class="rows" style="margin-top:12px"><details class="fold" data-key="done-' + esc(p.id) + '"><summary class="row"><span class="num">' + done.length + '</span><div class="row-main"><b>Finished</b><small>Done, Old and Archive</small></div><span class="row-end">' + icon('chev') + '</span></summary><div class="fold-body"><div class="lane-list">' + done.map(ticket).join('') + '</div></div></details></div>' : '')
        : '<div class="empty">No board cards belong to this project. Its work is tracked somewhere else.</div>'));
    if (tool) $('#project-tool').onclick = (e) => openTool(tool, e);
  }

  /* Library: the vault, readable here. */
  let LIB = null, libAt = 0, libTimer = 0;
  const shortDate = (seconds) => { const d = new Date(seconds * 1000); return String(d.getDate()).padStart(2, '0') + '.' + String(d.getMonth() + 1).padStart(2, '0') + '.' + String(d.getFullYear()).slice(2); };
  async function ensureLibrary() {
    if (!LIB || Date.now() - libAt > 60000) {
      const res = await fetch('/api/library');
      if (!res.ok) throw new Error('The server answered ' + res.status);
      LIB = await res.json();
      libAt = Date.now();
    }
    return LIB;
  }
  function renderLibrary() {
    ambientOff();
    $('#view').innerHTML = '<div class="page"><div class="page-inner lib"><aside class="lib-side"><input class="search" id="lib-search" type="search" placeholder="Search all notes" aria-label="Search all notes"><nav id="lib-nav" aria-label="Library sections"></nav></aside><div class="lib-main" id="lib-main"><p class="note">Opening the library…</p></div></div></div>';
    ensureLibrary().then((lib) => {
      if (route !== 'library') return;
      paintLibrary();
      if (lib.problem && !routeId) $('#lib-main').innerHTML = '<div class="empty">N/A: ' + esc(lib.problem) + '.' + (S && S.phone ? '' : ' <a class="day-next" href="#settings">Choose the folder again</a>') + '</div>';
    }).catch((err) => { const m = $('#lib-main'); if (m) m.innerHTML = '<div class="empty">' + esc(err.message) + '</div>'; });
    const box = $('#lib-search');
    box.oninput = () => { clearTimeout(libTimer); libTimer = setTimeout(() => paintSearch(box.value), 160); };
    box.onkeydown = (e) => { if (e.key === 'Escape') { box.value = ''; paintLibrary(); } };
  }
  function paintLibrary() {
    paintLibNav();
    const id = routeId || '', cut = id.indexOf('/');
    const kind = cut < 0 ? id : id.slice(0, cut), arg = cut < 0 ? '' : id.slice(cut + 1);
    if (kind === 'n') paintNote(arg);
    else if (kind === 'f') paintFolder(arg);
    else if (kind === 't') paintTag(arg);
    else paintLibHome();
  }
  const folderHref = (f) => '#library/f/' + f.split('/').map(encodeURIComponent).join('/');
  const tagHref = (t) => '#library/t/' + encodeURIComponent(t);
  function paintLibNav() {
    const nav = $('#lib-nav');
    if (!nav) return;
    const id = routeId || '';
    const inFolder = id.startsWith('n/') || id.startsWith('f/') ? id.slice(2) : null;
    const link = (href, label, count, on) => '<a class="lib-link' + (on ? ' on' : '') + '" href="' + esc(href) + '"' + (on ? ' aria-current="true"' : '') + '><span>' + esc(label) + '</span>' + (count !== null ? '<b>' + count + '</b>' : '') + '</a>';
    nav.innerHTML = link('#library', 'Overview', null, !id)
      + (LIB.rootCount ? link('#library/f/', 'Start', LIB.rootCount, id === 'f/' || (inFolder !== null && inFolder !== '' && !inFolder.includes('/'))) : '')
      // Folders holding a single scaffold file stay searchable but do not earn a place in the list.
      + LIB.sections.filter((s) => s.count > 1).map((s) => link(folderHref(s.folder), s.label, s.count, inFolder !== null && (inFolder === s.folder || inFolder.startsWith(s.folder + '/')))).join('');
  }
  function noteRow(n) {
    return '<a class="note-row" href="' + esc(noteHref(n.path)) + '"><span class="note-row-title">' + esc(n.title) + '</span>'
      + (n.snippet ? '<small>' + esc(n.snippet) + '</small>' : '')
      + '<span class="note-row-end">' + (n.type ? '<span class="pill">' + esc(n.type) + '</span>' : '') + (n.mtime ? '<time>' + shortDate(n.mtime) + '</time>' : '') + '</span></a>';
  }
  function paintLibHome() {
    const main = $('#lib-main');
    const topics = LIB.notes.filter((n) => n.path.startsWith('MOCs/')).sort((a, b) => (b.path.includes('start here') - a.path.includes('start here')) || a.title.localeCompare(b.title));
    const recent = LIB.notes.filter((n) => !/^(outputs|wiki|reports)\//.test(n.path)).sort((a, b) => b.mtime - a.mtime).slice(0, 10);
    main.innerHTML = '<header class="ph"><h1>Library</h1><p>' + LIB.notes.length + ' notes from your vault, readable here.</p></header>'
      + '<h2 class="section-title">Topics <span>' + topics.length + '</span></h2><div class="topic-grid">'
      + topics.map((n) => '<a class="topic" href="' + esc(noteHref(n.path)) + '"><span class="avatar" style="--tile:' + tileColor(n.path) + '">' + esc(initials(n.title)) + '</span><b>' + esc(n.title) + '</b></a>').join('') + '</div>'
      + '<h2 class="section-title">Recently changed</h2><div class="rows">' + recent.map(noteRow).join('') + '</div>'
      + '<h2 class="section-title">Tags</h2><div class="chips">' + LIB.tags.map(([t, c]) => '<a class="chip" href="' + esc(tagHref(t)) + '">' + esc(t) + ' <b>' + c + '</b></a>').join('') + '</div>';
    document.title = 'Library · Brento';
  }
  function sectionLabel(folder) { const s = LIB.sections.find((x) => x.folder === folder); return s ? s.label : folder; }
  function crumbsHtml(path, last) {
    const parts = path ? path.split('/') : [];
    let html = '<a href="#library">Library</a>', walk = '';
    parts.forEach((p, i) => {
      walk += (i ? '/' : '') + p;
      html += '<i>/</i><a href="' + esc(folderHref(walk)) + '">' + esc(i ? p : sectionLabel(p)) + '</a>';
    });
    return '<nav class="lib-crumbs" aria-label="Where you are">' + html + (last ? '<i>/</i><span>' + esc(last) + '</span>' : '') + '</nav>';
  }
  function paintFolder(folder) {
    const main = $('#lib-main');
    const prefix = folder ? folder + '/' : '';
    const under = LIB.notes.filter((n) => n.path.startsWith(prefix));
    const direct = under.filter((n) => !n.path.slice(prefix.length).includes('/'));
    const subs = {};
    under.forEach((n) => { const rest = n.path.slice(prefix.length); if (rest.includes('/')) { const name = rest.split('/')[0]; subs[name] = (subs[name] || 0) + 1; } });
    const names = folder ? Object.keys(subs).sort((a, b) => a.localeCompare(b)) : [];
    const title = folder ? (folder.includes('/') ? folder.split('/').pop() : sectionLabel(folder)) : 'Start';
    main.innerHTML = crumbsHtml(folder ? folder.split('/').slice(0, -1).join('/') : '', title)
      + '<header class="ph"><h1>' + esc(title) + '</h1><p>' + (folder ? under.length : direct.length) + ' notes</p></header>'
      + (names.length ? '<div class="topic-grid folders">' + names.map((n) => '<a class="topic" href="' + esc(folderHref(prefix + n)) + '"><span class="avatar folder" style="--tile:' + tileColor(n) + '">' + icon('projects') + '</span><b>' + esc(n) + '</b><small>' + subs[n] + '</small></a>').join('') + '</div>' : '')
      + (direct.length ? '<div class="rows">' + direct.map(noteRow).join('') + '</div>' : '');
    document.title = title + ' · Brento';
  }
  function paintTag(tag) {
    const list = LIB.notes.filter((n) => n.tags.includes(tag));
    $('#lib-main').innerHTML = '<nav class="lib-crumbs"><a href="#library">Library</a><i>/</i><span>Tag</span></nav><header class="ph"><h1>' + esc(tag) + '</h1><p>' + list.length + ' notes</p></header>'
      + (list.length ? '<div class="rows">' + list.map(noteRow).join('') + '</div>' : '<div class="empty">No note carries this tag.</div>');
  }
  async function paintNote(path) {
    const main = $('#lib-main');
    main.innerHTML = crumbsHtml(path.split('/').slice(0, -1).join('/'), '') + '<p class="note">Opening…</p>';
    let note;
    try {
      const res = await fetch('/api/library/note?path=' + encodeURIComponent(path));
      note = await res.json();
      if (!res.ok) throw new Error(note.error || 'The server answered ' + res.status);
    } catch (err) {
      if (routeId === 'n/' + path) main.innerHTML = crumbsHtml(path.split('/').slice(0, -1).join('/'), '') + '<div class="empty">' + esc(err.message) + '</div>';
      return;
    }
    if (route !== 'library' || routeId !== 'n/' + path) return;
    const props = note.props || {};
    const pills = [];
    if (props.type) pills.push('<span class="pill">' + esc(props.type) + '</span>');
    ['status', 'date', 'created', 'updated'].forEach((k) => { if (props[k] && typeof props[k] === 'string') pills.push('<span class="pill">' + esc(k + ' ' + props[k]) + '</span>'); });
    (Array.isArray(props.tags) ? props.tags : []).forEach((t) => pills.push('<a class="pill tag-link" href="' + esc(tagHref(t)) + '">' + esc(t) + '</a>'));
    if (note.hiddenLines) pills.push('<span class="pill warn">' + note.hiddenLines + (note.hiddenLines === 1 ? ' line' : ' lines') + ' hidden by the privacy list</span>');
    main.innerHTML = crumbsHtml(path.split('/').slice(0, -1).join('/'), '')
      + '<div class="note-grid"><article class="reader"><h1>' + esc(note.title) + '</h1>' + (pills.length ? '<div class="reader-meta">' + pills.join('') + '<time>changed ' + shortDate(note.mtime) + '</time></div>' : '') + note.html + '</article>'
      + '<aside class="note-rail"><h3>Linked from <span>' + note.backlinks.length + '</span></h3>' + (note.backlinks.length ? note.backlinks.map((b) => '<a href="' + esc(noteHref(b.path)) + '">' + esc(b.title) + '</a>').join('') : '<p class="note">No other note links here.</p>') + '</aside></div>';
    document.title = note.title + ' · Brento';
  }
  async function paintSearch(raw) {
    const q = raw.trim();
    if (!q) return paintLibrary();
    const main = $('#lib-main');
    const words = q.toLowerCase().split(/\s+/);
    const titles = LIB.notes.filter((n) => words.every((w) => n.title.toLowerCase().includes(w))).slice(0, 12);
    const draw = (hits) => {
      const seen = new Set(titles.map((n) => n.path));
      const text = hits.filter((h) => !seen.has(h.path));
      main.innerHTML = '<header class="ph"><h1>' + esc(q) + '</h1></header>'
        + (titles.length ? '<h2 class="section-title">Titles <span>' + titles.length + '</span></h2><div class="rows">' + titles.map(noteRow).join('') + '</div>' : '')
        + '<h2 class="section-title">In the text <span>' + (hits === null ? 'searching' : text.length) + '</span></h2>'
        + (text.length ? '<div class="rows">' + text.map(noteRow).join('') + '</div>' : (titles.length ? '' : '<div class="empty">Nothing found.</div>'));
    };
    const res = await fetch('/api/library/search?q=' + encodeURIComponent(q)).then((r) => r.json()).catch(() => ({ hits: [] }));
    const box = $('#lib-search');
    if (route === 'library' && box && box.value.trim() === q) draw(res.hits || []);
  }

  /* Pipeline */
  function renderPipeline() {
    const p = S.pipeline;
    const row = (x, i) => rowHtml(i, '<b>' + esc(x.firm) + '</b><small>' + esc(x.role) + '</small>', '<span class="pill">' + esc(x.status.slice(0, 46) || 'no status') + '</span>', x.notePath ? noteHref(x.notePath) : '');
    pageWrap(pageHead('Pipeline', 'Read from Applications.md. Click a company to open its note.')
      + '<div class="tiles">' + tile('Hot', p.hot.length, 'still live') + tile('Warm', p.warm.length, 'still live') + tile('Finished, still under Hot or Warm', p.ended.length, 'not counted above', p.ended.length ? 'warn' : 'good') + tile('Closed or parked', p.closed)
      + tile('Days since last application', p.daysSince, p.lastSent, p.daysSince > 7 ? 'warn' : 'good') + '</div>'
      + '<h2 class="section-title">Hot <span>' + p.hot.length + '</span></h2><div class="rows">' + (p.hot.map(row).join('') || '<div class="empty">Nothing hot.</div>') + '</div>'
      + '<h2 class="section-title">Warm <span>' + p.warm.length + '</span></h2><div class="rows">' + (p.warm.map(row).join('') || '<div class="empty">Nothing warm.</div>') + '</div>'
      + (p.ended.length ? '<h2 class="section-title">Finished, still under Hot or Warm <span>' + p.ended.length + ', your tracker says these belong in Closed. Moving them stays with you.</span></h2><div class="rows">' + p.ended.map(row).join('') + '</div>' : '')
      + srcLine('pipeline'));
  }

  /* Board */
  function setBoardFilter(area, dead) {
    const parts = [];
    if (dead) parts.push('passed');
    if (area !== 'All') parts.push('area:' + encodeURIComponent(area));
    history.replaceState(null, '', '#board' + (parts.length ? '/' + parts.join('/') : ''));
    routeId = parseHash().id;
    refreshInPlace();
  }
  function renderBoard() {
    const b = S.board;
    const parts = (routeId || '').split('/').filter(Boolean);
    const areaPart = parts.find((x) => x.startsWith('area:'));
    boardDead = parts.includes('passed');
    boardArea = areaPart ? areaPart.slice(5) : 'All';
    if (boardArea !== 'All' && !b.bereiche.includes(boardArea)) boardArea = 'All';
    const inArea = (i) => boardArea === 'All' || i.bereich === boardArea;
    const active = b.items.filter(inArea);
    const shown = active.filter((i) => !boardDead || i.passed);

    /* The cards outside the three lanes: each stage of the aging job, then what no rule touches. */
    const rules = b.aging && b.aging.rules, job = b.aging && b.aging.job;
    const stage = (i, title, sub, list, tone) => {
      const dates = list.map((c) => c.agesOn).filter(Boolean).sort();
      const label = list.length + (list.length === 1 ? ' card' : ' cards') + (dates.length ? ', next ' + dayMonth(dates[0]) : '');
      const main = '<b>' + esc(title) + '</b><small>' + esc(sub) + '</small>';
      const pill = '<span class="pill ' + (tone || '') + '">' + label + '</span>';
      if (!list.length) return rowHtml(i, main, pill, '');
      return '<details class="fold" data-key="stage-' + i + '"><summary class="row"><span class="num">' + String(i + 1).padStart(2, '0') + '</span><div class="row-main">' + main + '</div><span class="row-end">' + pill + icon('chev') + '</span></summary>'
        + '<div class="fold-body"><div class="lane-list">' + list.map(ticket).join('') + '</div></div></details>';
    };
    const norule = active.filter((i) => !i.agesTo && !['HIGH', 'MID', 'LOW'].includes(i.status));
    const jobOk = job && job.conclusion === 'success';
    const jobLine = job ? 'runs daily on GitHub, last run ' + dayMonth(job.date) + ' ' + (job.conclusion || 'still running') : 'runs on GitHub, last run unknown';
    const stagesHtml = '<h2 class="section-title">Archiving rules <span>' + esc(jobLine) + '</span></h2>'
      + (rules ? '<div class="rows">'
        + stage(0, 'News to Old', 'after ' + rules.news + ' days, counted from the date in the title', active.filter((i) => i.agesTo === 'Old' && i.bereich === 'News'))
        + (rules.passed ? stage(1, 'Passed date to Old', rules.passed + ' days after the date in the title, if it was still ahead when the card was made', active.filter((i) => i.agesTo === 'Old' && i.bereich !== 'News')) : '')
        + stage(2, 'Old to Archive', 'after ' + rules.old + ' days', active.filter((i) => i.status === 'Old'))
        + stage(3, 'Done to Archive', 'after ' + rules.done + ' days, counted from "Erledigt am"', active.filter((i) => i.status === 'Done'))
        + stage(4, 'Archive', 'end of the line, nothing leaves it by rule', (b.archived || []).filter(inArea))
        + stage(5, 'No status, no date', 'no rule applies, these stay until someone sorts them', norule, norule.length ? 'warn' : '')
        + '</div><p class="note">' + (rules.passed ? 'A date older than the card is a note, not a deadline, so it stays. Put a moved card back and it stays where you put it.' : 'HIGH, MID and LOW have no rule. A card stays there until someone moves it.') + (job && !jobOk ? ' The last job run did not succeed.' : '') + '</p>'
        : '<div class="empty">The rules of the daily job could not be read.</div>');
    const src = S.sources.find((s) => s.id === 'board') || {};
    const managed = !!(rules || job || (b.aging && b.aging.on));
    const nothing = src.state === 'unknown' ? 'Board not available: ' + (b.error || src.note || 'still loading') : 'No cards yet. Open the board on GitHub and add the first one.';
    const high = b.items.filter((i) => i.status === 'HIGH');
    const dead = high.filter((i) => i.passed).length;
    const filtered = boardDead || boardArea !== 'All';
    /* Fresh news has a date, not a priority: no status, so no lane. It still has to be visible. */
    const news = shown.filter((i) => i.bereich === 'News' && i.status === 'No status');
    const newsHtml = news.length ? '<h2 class="section-title">News <span>' + news.length + ' fresh' + (rules ? ', move to Old after ' + rules.news + ' days' : '') + '</span></h2><div class="lane-list">' + news.map(ticket).join('') + '</div>' : '';
    pageWrap(pageHead('Board', (src.path || 'GitHub Project') + '. Click a card to read it.' + (managed ? ' The daily job moves cards by the rules below.' : ''), '<a class="btn" href="' + esc(boardUrl()) + '" target="_blank" rel="noopener noreferrer">Open on GitHub</a>')
      + (b.items.length || !b.error ? '<div class="tiles">' + tile('HIGH', high.length) + tile('HIGH with a passed date', dead, 'date in the title is over', dead ? 'warn' : 'good') + tile('MID', b.items.filter((i) => i.status === 'MID').length) + tile('LOW', b.items.filter((i) => i.status === 'LOW').length) + tile('Archive', (b.archived || []).length, managed ? 'handled by the rules below' : null) + '</div>' : '')
      + '<div class="chips"><button class="chip" type="button" data-area="All" aria-pressed="' + (boardArea === 'All') + '">All</button>'
      + b.bereiche.map((a) => '<button class="chip" type="button" data-area="' + esc(a) + '" aria-pressed="' + (boardArea === a) + '">' + esc(a) + '</button>').join('')
      + '<button class="chip" type="button" id="only-dead" aria-pressed="' + boardDead + '">Only passed dates</button>'
      + (filtered ? '<button class="chip" type="button" id="clear-filter">Clear filter ×</button>' : '') + '</div>'
      + (b.items.length ? newsHtml + '<h2 class="section-title">Lanes <span>' + (filtered ? 'filtered, ' : '') + shown.filter((i) => ['HIGH', 'MID', 'LOW'].includes(i.status)).length + ' of ' + b.items.filter((i) => ['HIGH', 'MID', 'LOW'].includes(i.status)).length + ' cards</span></h2><div class="lanes">' + ['HIGH', 'MID', 'LOW'].map((n) => lane(n, shown.filter((i) => i.status === n))).join('') + '</div>' + (managed ? stagesHtml : '') : '<div class="empty">' + esc(nothing) + '</div>')
      + srcLine('board'));
    $$('[data-area]').forEach((el) => { el.onclick = () => setBoardFilter(el.dataset.area, boardDead); });
    $('#only-dead').onclick = () => setBoardFilter(boardArea, !boardDead);
    if (filtered) $('#clear-filter').onclick = () => setBoardFilter('All', false);
    // Arrived from a slide or a day: that one card, already open.
    const wanted = parts.find((x) => x.startsWith('card:'));
    const card = wanted && $('#view details[data-card="' + CSS.escape(wanted.slice(5)) + '"]');
    if (card) { card.open = true; card.scrollIntoView({ block: 'center' }); }
  }

  /* Brain */
  function renderBrain() {
    if (!S.sources.some((s) => s.id === 'liveness')) return renderSources();
    const l = S.liveness;
    const fresh = S.sources.filter((s) => s.state === 'fresh').length;
    const ageWord = (age) => (age === 'nie' ? 'never' : age);
    const silence = (r) => (r.age === 'nie' ? r.name + ' has never reported in' : r.name + ' has been silent for ' + r.age);
    pageWrap(pageHead('Brain', 'Every other check starts at healthy and looks for errors. This one starts at dead and looks for signs of life.', (S && S.phone ? '' : '<a class="btn" href="#settings">Sources and setup</a>'))
      + '<div class="tiles">' + tile('Alive', l.alive, null, 'good') + tile('Silent', l.still, null, l.still ? 'warn' : 'good') + tile('Resting on purpose', l.resting) + tile('Sources fresh', fresh + ' / ' + S.sources.length, S.hidden ? S.hidden + ' row hidden by the privacy list' : '') + '</div>'
      + '<h2 class="section-title">Silent <span>click for the reason and the next step</span></h2><div class="rows">'
      + (l.stillRows.map((r, i) => '<details class="fold" data-key="' + esc(r.name) + '"><summary class="row"><span class="num">' + String(i + 1).padStart(2, '0') + '</span><div class="row-main"><b>' + esc(r.name) + '</b><small>limit ' + esc(r.limit) + '</small></div><span class="row-end"><span class="big-right">' + esc(ageWord(r.age)) + '</span>' + icon('chev') + '</span></summary>'
        + '<div class="fold-body"><p>' + esc(r.why) + '</p>' + (r.proof ? '<small>Evidence: ' + esc(r.proof) + '</small>' : '')
        + '<button class="chip" type="button" data-ask="' + esc(silence(r) + ' (limit ' + r.limit + '). What is it for, does it still matter, and what is the smallest next step?') + '">Ask what to do about it</button></div></details>').join('') || '<div class="empty">Nothing silent.</div>') + '</div>'
      + '<h2 class="section-title">What this app is reading <span>age against each source\'s own limit</span></h2><div class="rows">'
      + S.sources.map((s, i) => rowHtml(i, '<b>' + esc(s.label) + '</b><small>' + esc(s.path) + (s.note ? ' · ' + esc(s.note) : '') + '</small>', '<span class="pill ' + ({ fresh: 'ok', stale: 'warn', unknown: 'bad' }[s.state]) + '"><span class="dot ' + s.state + '"></span>' + (s.ageDays === null ? 'N/A' : s.ageDays + 'd, limit ' + s.maxAge + 'd') + '</span>', s.route ? '#' + s.route : (s.notePath ? noteHref(s.notePath) : ''))).join('') + '</div>'
      + '<h2 class="section-title">Alive <span>' + l.aliveRows.length + '</span></h2><div class="chips">' + l.aliveRows.map((r) => '<span class="pill ok">' + esc(r.name) + ' · ' + esc(r.age) + '</span>').join('') + '</div>'
      + srcLine('liveness'));
    bindAskButtons();
  }
  function sourceRows() {
    return S.sources.map((s, i) => rowHtml(i, '<b>' + esc(s.label) + '</b><small>' + esc(s.path) + (s.note ? ' · ' + esc(s.note) : '') + '</small>', '<span class="pill ' + ({ fresh: 'ok', stale: 'warn', unknown: 'bad' }[s.state]) + '"><span class="dot ' + s.state + '"></span>' + (s.ageDays === null ? 'N/A' : s.ageDays + 'd, limit ' + s.maxAge + 'd') + '</span>', s.route ? '#' + s.route : (s.notePath ? noteHref(s.notePath) : ''))).join('');
  }
  function renderSources() {
    const fresh = S.sources.filter((s) => s.state === 'fresh').length;
    pageWrap(pageHead('Brain', 'What Brento reads, and how old each source is against its own limit. A source that cannot be read says N/A.', (S && S.phone ? '' : '<a class="btn primary" href="#settings">Sources and setup</a>'))
      + '<div class="tiles">' + tile('Sources fresh', fresh + ' / ' + S.sources.length, S.hidden ? S.hidden + ' hidden by the privacy list' : '') + '</div>'
      + '<div class="rows">' + (sourceRows() || '<div class="empty">No source is switched on. Open the setup to choose some.</div>') + '</div>');
  }
  // The question is only prefilled. Sending it stays a click, because it uses the plan's limit.
  function bindAskButtons() { $$('[data-ask]').forEach((b) => { b.onclick = () => { ask.draft = b.dataset.ask; navigate('ask'); }; }); }

  /* Ask */
  const ask = { thread: [], busy: false, status: null, abort: null, draft: '' };
  const SUGGEST = ['What should I do right now?', 'Which applications have gone quiet the longest?', 'What did I decide last week?'];
  function miniMd(text) {
    const lines = esc(text).split('\n');
    let html = '', list = false;
    lines.forEach((raw) => {
      const line = raw.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/`([^`]+)`/g, '<code>$1</code>');
      const item = line.match(/^\s*[-*] (.*)$/);
      if (item) {
        if (!list) { html += '<ul>'; list = true; }
        html += '<li>' + item[1] + '</li>';
        return;
      }
      if (list) { html += '</ul>'; list = false; }
      html += line ? line + '<br>' : '<br>';
    });
    return html + (list ? '</ul>' : '');
  }
  function msgHtml(m) {
    if (m.role === 'user') return '<div class="msg user">' + esc(m.text) + '</div>';
    return '<div class="msg bot' + (m.error ? ' err' : '') + '">' + (m.text ? miniMd(m.text) : '')
      + (m.live ? '<div class="status"><span class="spinner"></span>' + esc(m.status || 'Thinking') + '</div>' : '')
      + (m.meta ? '<div class="meta">' + esc(m.meta) + '</div>' : '') + '</div>';
  }
  function paintThread() {
    const t = $('#thread');
    if (!t) return;
    t.innerHTML = ask.thread.map(msgHtml).join('');
    const page = $('.page');
    if (page) page.scrollTop = page.scrollHeight;
    const send = $('#send');
    if (send) send.textContent = ask.busy ? 'Stop' : 'Ask';
  }
  function renderAsk() {
    const st = ask.status;
    const plan = st && st.plan ? st.plan.charAt(0).toUpperCase() + st.plan.slice(1) : 'Claude';
    const sub = st && st.ready ? 'Answers from your notes through Claude Code on your ' + plan + ' plan. It can only read, and only your notes folder.' : 'Answers from your notes through Claude Code. It can only read, and only your notes folder.';
    pageWrap(pageHead('Ask', sub)
      + '<div class="ask-wrap"><div class="thread" id="thread"></div>'
      + (st && !st.ready ? '<div class="msg bot err">' + esc(st.reason) + '</div>' : '')
      + (ask.thread.length ? '' : '<div class="suggest">' + SUGGEST.map((q) => '<button class="chip" type="button" data-q="' + esc(q) + '">' + esc(q) + '</button>').join('') + '</div>')
      + '<form class="composer" id="composer"><textarea id="q" rows="1" placeholder="Ask your vault" aria-label="Your question">' + esc(ask.draft) + '</textarea><button class="send" id="send" type="submit"' + (st && !st.ready ? ' disabled' : '') + '>Ask</button></form></div>');
    paintThread();
    const q = $('#q');
    q.oninput = () => { ask.draft = q.value; q.style.height = 'auto'; q.style.height = q.scrollHeight + 'px'; };
    q.onkeydown = (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#composer').requestSubmit(); } };
    $('#composer').onsubmit = (e) => { e.preventDefault(); if (ask.busy) { if (ask.abort) ask.abort.abort(); } else submitAsk(q.value); };
    $$('[data-q]').forEach((b) => { b.onclick = () => submitAsk(b.dataset.q); });
    if (ask.draft) q.oninput();
    if (window.innerWidth > 760) q.focus();
    if (!st || (!st.ready && Date.now() - ask.at > 15000)) fetch('/api/ask/status').then((r) => r.json()).then((j) => { ask.status = j; ask.at = Date.now(); if (route === 'ask') renderAsk(); }).catch(() => {});
  }
  async function submitAsk(text) {
    text = (text || '').trim();
    if (!text || ask.busy) return;
    const history = ask.thread.filter((m) => !m.error).map((m) => ({ role: m.role, text: m.text }));
    ask.thread.push({ role: 'user', text });
    const bot = { role: 'bot', text: '', live: true, status: 'Reading the vault' };
    ask.thread.push(bot);
    ask.busy = true; ask.draft = '';
    ask.abort = new AbortController();
    if (route === 'ask') renderAsk();
    let endedCleanly = false;
    try {
      const res = await fetch('/api/ask', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Leitstand': '1' }, body: JSON.stringify({ q: text, history }), signal: ask.abort.signal });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(j.error || 'The server answered ' + res.status);
      }
      const reader = res.body.getReader(), decoder = new TextDecoder();
      let buffer = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop();
        lines.forEach((line) => {
          if (!line.trim()) return;
          const ev = JSON.parse(line);
          if (ev.t === 'delta') bot.text += ev.text;
          if (ev.t === 'status') bot.status = ev.text;
          if (ev.t === 'error') throw new Error(ev.text);
          if (ev.t === 'done') { endedCleanly = true; bot.meta = (ev.ms / 1000).toFixed(1) + ' s · ' + ev.turns + ' steps · read only'; }
        });
        paintThread();
      }
      if (!endedCleanly && !bot.text) throw new Error('The answer stopped before it started.');
    } catch (err) {
      if (err.name === 'AbortError') { bot.meta = 'Stopped.'; } else { bot.error = true; bot.text = (bot.text ? bot.text + '\n\n' : '') + err.message; }
    }
    bot.live = false;
    ask.busy = false; ask.abort = null;
    if (route === 'ask') renderAsk();
  }

  /* Palette */
  let paletteItems = [], paletteSel = 0;
  function openPalette() {
    $('#palette').hidden = false;
    const input = $('#palette-input');
    input.value = '';
    input.focus();
    ensureLibrary().then(paintPalette).catch(() => {});
    paintPalette();
  }
  const closePalette = () => { $('#palette').hidden = true; };
  function paintPalette() {
    const q = $('#palette-input').value.trim().toLowerCase();
    const hit = (s) => !q || s.toLowerCase().includes(q);
    const items = [];
    ROUTES.forEach((r) => { if (hit(r.label)) items.push({ label: r.label, hint: 'Page', go: () => navigate(r.id) }); });
    TOOLS.forEach((t) => { if (q && hit(t.name)) items.push({ label: t.name, hint: 'Tool', go: (e) => openTool(t, e) }); });
    (S ? S.projects.rows : []).forEach((p) => { if (q && hit(p.name)) items.push({ label: p.name, hint: 'Project', go: () => navigate('projects/' + encodeURIComponent(p.id)) }); });
    (S ? S.focus : []).forEach((c, i) => { if (q && hit(c.title)) items.push({ label: c.title, hint: 'Card', go: () => { cur = i; if (route === 'home') renderHome(); else navigate('home'); } }); });
    if (q && LIB) {
      LIB.notes.filter((n) => n.title.toLowerCase().includes(q)).slice(0, 30).forEach((n) => items.push({ label: n.title, hint: n.path, go: () => navigate(noteHref(n.path).slice(1)) }));
    }
    paletteItems = items.slice(0, 40);
    paletteSel = clamp(paletteSel, 0, Math.max(0, paletteItems.length - 1));
    $('#palette-list').innerHTML = paletteItems.map((it, i) => '<li role="option" data-i="' + i + '" class="' + (i === paletteSel ? 'sel' : '') + '"' + (i === paletteSel ? ' aria-selected="true"' : '') + '><b>' + esc(it.label) + '</b><small>' + esc(it.hint) + '</small></li>').join('')
      || '<li><b>Nothing found</b></li>';
    const sel = $('#palette-list .sel');
    if (sel) sel.scrollIntoView({ block: 'nearest' });
  }
  function choosePalette(i, e) {
    const it = paletteItems[i];
    closePalette();
    if (it) it.go(e);
  }
  $('#palette-input').addEventListener('input', () => { paletteSel = 0; paintPalette(); });
  $('#palette').addEventListener('mousedown', (e) => {
    if (e.target.id === 'palette') return closePalette();
    const li = e.target.closest('li[data-i]');
    if (li) { e.preventDefault(); choosePalette(Number(li.dataset.i), e); }
  });

  /* Keys */
  document.addEventListener('keydown', (e) => {
    const typing = /^(INPUT|TEXTAREA)$/.test(document.activeElement && document.activeElement.tagName);
    if (drag && drag.moved) { if (e.key === 'Escape') endDrag(true); return; }
    if (!$('#dock-menu').hidden) {
      const items = $$('#dock-menu button'), at = items.indexOf(document.activeElement);
      if (e.key === 'Escape') closeDockMenu();
      // In the new-app form, keys belong to the fields: arrows move the cursor, Tab moves to the next field.
      else if ($('#new-app')) return;
      else if (e.key === 'ArrowDown' && items.length) { e.preventDefault(); items[(at + 1) % items.length].focus(); }
      else if (e.key === 'ArrowUp' && items.length) { e.preventDefault(); items[(at - 1 + items.length) % items.length].focus(); }
      else if (e.key === 'Tab') closeDockMenu();
      return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); return $('#palette').hidden ? openPalette() : closePalette(); }
    if (!$('#palette').hidden) {
      if (e.key === 'Escape') closePalette();
      else if (e.key === 'ArrowDown') { e.preventDefault(); paletteSel = Math.min(paletteSel + 1, paletteItems.length - 1); paintPalette(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); paletteSel = Math.max(paletteSel - 1, 0); paintPalette(); }
      else if (e.key === 'Enter') { e.preventDefault(); choosePalette(paletteSel, e); }
      return;
    }
    if (!$('#tools').hidden) { if (e.key === 'Escape') closeToolsPanel(); return; }
    if (!$('#alert-pop').hidden) { if (e.key === 'Escape') $('#alert-later').click(); return; }
    if (!typing && e.altKey && e.key === 'ArrowLeft') { e.preventDefault(); return goBack(); }
    if (typing || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === 'Backspace' && route !== 'home') { e.preventDefault(); return goBack(); }
    if (route === 'home' && deckApi) {
      if (e.key === 'ArrowLeft') return deckApi.step(-1);
      if (e.key === 'ArrowRight') return deckApi.step(1);
      if (e.key === 'Enter' && !(document.activeElement && document.activeElement.closest('a,button,summary'))) return deckApi.open();
      if (e.key === 'Delete') return deckApi.remove();
    }
    if (route === 'day' && S) {
      if (e.key === 'ArrowLeft' && openDay() > S.today) return navigate('day/' + addDays(openDay(), -1));
      if (e.key === 'ArrowRight') return navigate('day/' + addDays(openDay(), 1));
    }
    if (/^[1-8]$/.test(e.key)) { const p = dockPages()[Number(e.key) - 1]; if (p) navigate(p.id); }
    else if (e.key.toLowerCase() === 't') openToolsPanel();
    else if (e.key.toLowerCase() === 'r') refreshNow();
  });

  /* Schedule check on Today: is every meeting covered and does every urgent card have a date? */
  function scheduleHtml() {
    const sc = S.schedule;
    if (!sc) return '';
    const LABEL = { prep: ['No prep yet', 'warn'], clash: ['Same start', 'bad'], overdue: ['Task overdue', 'bad'], passed: ['Date passed', 'warn'], undated: ['HIGH, no date', ''] };
    const rows = sc.items.map((f, i) => rowHtml(i, '<b>' + esc(f.title) + '</b><small>' + esc(f.why)
      + (f.suggest ? ' Suggested: "' + esc(f.suggest.title) + '" by ' + weekdayOf(f.suggest.due) + ' ' + dayMonth(f.suggest.due) + '.' : '') + '</small>',
      (f.date ? '<span class="pill">' + weekdayOf(f.date) + ' ' + dayMonth(f.date) + (f.time ? ' ' + esc(f.time) : '') + '</span>' : '') + '<span class="pill ' + LABEL[f.kind][1] + '">' + LABEL[f.kind][0] + '</span>',
      f.route ? '#' + f.route : (f.note ? noteHref(f.note) : (f.date ? '#day/' + f.date : ''))));
    const cal = S.sources.find((s) => s.id === 'calendar') || {};
    const quiet = !S.calendarConnected ? 'the calendar is not connected, so meetings are not checked'
      : cal.state === 'unknown' ? (cal.note === 'still loading' ? 'the calendar is being read' : 'N/A, the calendar could not be read')
      : 'every one-off meeting in the next ' + sc.days + ' days has a card, task or note, and every HIGH card has a date';
    return '<h2 class="section-title">On track? <span>' + (sc.items.length ? sc.items.length + ' to look at: meetings in the next ' + sc.days + ' days, tasks and the board' : quiet) + '</span></h2>'
      + (sc.items.length ? '<div class="rows">' + rows.join('') + '</div>' : '');
  }

  /* Setup: the vault, the sources, the board, the calendar and the dock's tools. Brento writes only to its own folder. */
  let SETUP = null;
  const setupOpt = (type, name, value, checked, title, small, disabled) => '<label class="setup-opt' + (disabled ? ' done' : '') + '"><input type="' + type + '" name="' + name + '" value="' + esc(value) + '"'
    + (checked ? ' checked' : '') + (disabled ? ' disabled' : '') + '><b>' + esc(title) + '</b>' + (small ? '<small>' + esc(small) + '</small>' : '') + '</label>';
  const setupStatus = (ok, text) => '<span class="pill ' + (ok ? 'ok' : 'warn') + '"><span class="dot ' + (ok ? 'fresh' : 'stale') + '"></span>' + esc(text) + '</span>';
  const grouped = (list) => list.reduce((out, x) => { let g = out.find((y) => y.name === x.group); if (!g) out.push(g = { name: x.group, items: [] }); g.items.push(x); return out; }, []);
  function renderSettings() {
    if (S && S.phone) { pageWrap(pageHead('Settings', 'The setup lives on your computer. Open Brento there to change it.')); return; }
    pageWrap(pageHead('Settings', 'Choose what Brento reads. It runs on this computer, only reads your notes, board and calendar, and writes only to its own folder.')
      + '<div class="setup" id="setup"><div class="empty">Checking what is installed on this computer…</div></div>');
    fetch('/api/setup').then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status); SETUP = j; paintSetup(); })
      .catch((err) => { const box = $('#setup'); if (box) box.innerHTML = '<div class="empty">' + esc(err.message) + '</div>'; });
  }
  let PHONE = null;
  function phoneHtml(P) {
    if (!P) return '<p class="note">Checking…</p>';
    const win = !!SETUP && SETUP.platform === 'win32', mac = !!SETUP && SETUP.platform === 'darwin';
    if (!P.on) return '<button class="btn" type="button" id="ph-on">Use Brento on my phone</button>'
      + (win ? '<p class="note">Windows then asks about Python. That is Brento: click Allow. On a computer you are not the administrator of, it asks once for the administrator.</p>' : '')
      + (mac ? '<p class="note">If macOS asks whether Brento may accept connections, click Allow.</p>' : '');
    const addr = (a) => '<b class="ph-addr">' + esc(a.ip) + ':' + P.port + '</b>';
    const home = P.addresses.filter((a) => a.kind === 'home'), away = P.addresses.filter((a) => a.kind === 'tailscale');
    let html = P.error ? '<p class="tools-error">' + esc(P.error) + '</p>' : '';
    html += '<ol class="wz-steps"><li>Phone and computer on the same Wi-Fi. On the phone, open Safari (iPhone) or Chrome (Android) and type '
      + (home.length ? home.map(addr).join(' or ') : 'this computer\'s address (Brento found none: is the computer on Wi-Fi?)') + '</li>'
      + '<li>iPhone: tap Share, then "Add to Home Screen". Android: the menu, then "Add to Home screen". Open Brento from the new icon.</li>'
      + '<li>There, type the code ' + (P.code ? '<b class="ph-code">' + esc(P.code.slice(0, 3) + ' ' + P.code.slice(3)) + '</b> (for ' + Math.max(1, Math.ceil(P.codeLeft / 60)) + ' more minutes)' : '(none open)')
      + ' <button class="link-btn" type="button" id="ph-code">New code</button></li></ol>';
    if (away.length) html += '<p class="note">Away from home, with Tailscale on the phone and this computer: ' + away.map(addr).join(' or ') + '</p>';
    return html + '<p class="note">' + (P.phones === 1 ? 'One phone is paired.' : P.phones + ' phones are paired.') + ' A phone reads Brento and can ask, it can never change the setup. '
      + 'Use it at home or over Tailscale, not on public Wi-Fi.</p>'
      + (win ? '<p class="note">The phone cannot open the address? Open Windows Security, Firewall & network protection, Allow an app through firewall, Change settings, and tick the Python in the Brento folder. And set your Wi-Fi to Private network.</p>' : '')
      + '<p class="note">' + (P.phones ? '<button class="link-btn" type="button" id="ph-forget">Remove all phones</button> · ' : '') + '<button class="link-btn" type="button" id="ph-off">Switch off</button></p>';
  }
  function paintPhone() {
    const box = $('#phone-box');
    if (!box) return;
    box.innerHTML = phoneHtml(PHONE);
    const act = (action) => post('/api/phone', { action }).then((j) => { PHONE = j; paintPhone(); }).catch((err) => toast(err.message));
    [['#ph-on', 'on'], ['#ph-off', 'off'], ['#ph-code', 'code'], ['#ph-forget', 'forget']].forEach((x) => { const b = $(x[0]); if (b) b.onclick = () => act(x[1]); });
  }
  function boardFields(probe) {
    const B = SETUP.profile.board;
    const pick = (id, label, value, type, none) => {
      if (!probe || probe.error) return '<div class="setup-field"><label for="' + id + '">' + label + '</label><input id="' + id + '" value="' + esc(value) + '" spellcheck="false"' + (none ? ' placeholder="' + esc(none) + '"' : '') + '></div>';
      const names = probe.fields.filter((f) => f.type === type).map((f) => f.name);
      return '<div class="setup-field"><label for="' + id + '">' + label + '</label><select id="' + id + '">' + (none ? '<option value="">' + esc(none) + '</option>' : '')
        + names.map((n) => '<option' + (n === value ? ' selected' : '') + '>' + esc(n) + '</option>').join('') + '</select></div>';
    };
    let head = '';
    if (probe && probe.error) head = '<p class="tools-error">' + esc(probe.error) + '</p>';
    else if (probe) {
      const lanes = (probe.fields.find((f) => f.name === (B.statusField || 'Status')) || { options: [] }).options;
      const missing = ['HIGH', 'MID', 'LOW'].filter((n) => !lanes.includes(n));
      head = '<p class="setup-check"><span class="pill ok"><span class="dot fresh"></span>Found</span><a href="' + esc(probe.url) + '" target="_blank" rel="noopener noreferrer">' + esc(probe.title) + '</a>'
        + (missing.length ? '<span class="pill warn">Its status has no ' + esc(missing.join(', ')) + '. Cards outside these lanes never reach Home.</span>' : '<span class="pill ok">Lanes HIGH, MID, LOW found</span>') + '</p>';
    }
    return head + '<div class="setup-row">' + pick('su-status', 'Status field (the lanes)', B.statusField || 'Status', 'SINGLE_SELECT')
      + pick('su-area', 'Area field (one project per area)', B.areaField, 'SINGLE_SELECT', 'No area field')
      + pick('su-due', 'Due date field', B.dueField, 'DATE', 'None, dates come from titles')
      + pick('su-done', 'Done date field', B.doneField, 'DATE', 'None') + '</div>';
  }
  function paintSetup() {
    const box = $('#setup');
    if (!box || route !== 'settings' || !SETUP) return;
    const P = SETUP.profile;
    // A first setup starts from the usual sources. Later, the boxes show what is saved.
    const on = (s) => (SETUP.needed ? s.new : !!(P.sources[s.id] || {}).on);
    const step = (n, title, pill, sub, body) => '<section class="setup-step"><h3><span class="num">' + n + '</span>' + esc(title) + (pill || '') + '</h3>' + (sub ? '<p>' + esc(sub) + '</p>' : '') + body + '</section>';
    const listed = SETUP.vaults.some((v) => v.path === P.vault);
    let html = step('1', 'You', '', 'Your first name. Brento uses it to know which rows in an Owner column are yours.',
      '<div class="setup-field"><label for="su-name">First name</label><input id="su-name" maxlength="40" value="' + esc(P.name) + '" autocomplete="given-name"></div>'
      + (SETUP.shared ? '<label class="wz-check"><input type="checkbox" id="su-keep"' + (P.keepBrowsers ? ' checked' : '') + '> Keep this browser let in after a restart</label>'
        + '<p class="note">This computer has more than one account. So after each start Brento opens with its icon first, and bookmarks work from then on. Tick this only if you trust the others, and the programs that run under their accounts.</p>' : ''));
    html += step('2', 'Your Obsidian vault', '', 'Brento reads your notes from this folder and never changes them. These are the vaults Obsidian itself knows on this computer.',
      '<div class="setup-grid">' + SETUP.vaults.map((v) => setupOpt('radio', 'su-vault', v.path, P.vault === v.path || (!P.vault && SETUP.needed && v.open), v.name, v.path + (v.open ? ' · open in Obsidian' : ''))).join('')
      + setupOpt('radio', 'su-vault', '__other', !!P.vault && !listed, 'Another folder', 'Type its full path below')
      + setupOpt('radio', 'su-vault', '', !P.vault && !(SETUP.needed && SETUP.vaults.some((v) => v.open)), 'No vault', 'Calendar and board only. Notes, tasks and Ask stay off.') + '</div>'
      + '<div class="setup-field"><label for="su-vault-path">Folder path</label><input id="su-vault-path" value="' + esc(listed ? '' : P.vault) + '" spellcheck="false" placeholder="Full path of the vault folder"></div>'
      + '<p class="note"><a class="link-btn" href="#setup/1">Choose your notes step by step</a></p>'
      + (SETUP.vaultMissing ? '<p class="tools-error">This folder is not there at the moment: ' + esc(P.vault) + '. It may have been renamed, or its drive is not connected. Brento goes on without your notes until you choose the folder again here.</p>' : ''));
    html += step('3', 'Sources', '', 'Switch on what you use. A source that is on but cannot be read shows N/A on the Brain page, never an empty success.',
      grouped(SETUP.sources).map((g) => '<div class="setup-group">' + esc(g.name) + '</div><div class="setup-grid">' + g.items.map((s) => '<div>' + setupOpt('checkbox', 'su-src', s.id, on(s), s.label, s.about)
        + (s.path ? '<div class="setup-field"><label for="su-path-' + s.id + '">Note in the vault</label><input id="su-path-' + s.id + '" data-path="' + s.id + '" value="' + esc((P.sources[s.id] || {}).path || s.path) + '" spellcheck="false"></div>' : '') + '</div>').join('') + '</div>').join('')
      + '<div class="setup-field"><label for="su-taskhome">Tasks on Home</label><select id="su-taskhome"><option value="all"' + (P.tasks.home !== 'priority' ? ' selected' : '') + '>Every dated task due within a week, or missed</option>'
      + '<option value="priority"' + (P.tasks.home === 'priority' ? ' selected' : '') + '>Only tasks marked medium priority or higher</option></select></div>');
    const B = P.board, gh = SETUP.gh;
    html += step('4', 'GitHub Project board', setupStatus(gh.ready, gh.ready ? 'signed in' + (gh.login ? ' as ' + gh.login : '') : 'not signed in'),
      'Brento reads the board through GitHub\'s own program, with your sign-in. Cards in the lanes HIGH, MID and LOW count; a HIGH card with a date inside a week reaches Home.',
      (gh.ready ? '<p class="note"><a class="link-btn" href="#setup/2">Choose a board, or make a new one, step by step</a></p>' : '<p class="note">' + esc(gh.reason) + ' <a class="link-btn" href="#setup/2">Sign in to GitHub</a></p>')
      + '<div class="setup-row"><div class="setup-field"><label for="su-owner">Owner: your login or an organization</label><input id="su-owner" value="' + esc(B.owner) + '" spellcheck="false"></div>'
      + '<div class="setup-field"><label for="su-kind">The owner is</label><select id="su-kind"><option value="user"' + (B.ownerType !== 'org' ? ' selected' : '') + '>a person</option><option value="org"' + (B.ownerType === 'org' ? ' selected' : '') + '>an organization</option></select></div>'
      + '<div class="setup-field"><label for="su-num">Project number</label><input id="su-num" inputmode="numeric" value="' + esc(B.number || '') + '" placeholder="the number at the end of its address"></div>'
      + '<div class="setup-field"><button class="btn" type="button" id="su-probe">Check the board</button></div></div><div id="su-fields">' + boardFields(null) + '</div>');
    html += step('5', 'Calendar', setupStatus(SETUP.calendarConnected, SETUP.calendarConnected ? 'connected' : 'not connected'), 'A private iCal link, read only. It stays in a file in your Brento folder and never goes back to a page.',
      SETUP.calendarConnected ? '<p class="note">Connected. <button class="link-btn" type="button" id="cal-off">Disconnect</button></p>'
        : '<p class="note"><a class="link-btn" href="#setup/3">Connect your calendar</a>: Google, Outlook or Apple iCloud, in four short steps. Repeating appointments are left out.</p>');
    const C = SETUP.claude;
    html += step('6', 'Ask box', C ? setupStatus(C.ready, C.ready ? 'Claude Code ready' + (C.plan ? ', ' + C.plan : '') : 'not ready') : '<span class="pill">off</span>',
      'Questions about your notes, answered by the claude program on this computer under your own Claude login. Brento never sees or stores the login, and refuses to run on an API key. Questions count against your Claude plan, and what Claude reads for an answer goes to Claude.',
      C && !C.ready ? '<p class="note">' + esc(C.reason) + (/not installed/i.test(C.reason) ? '' : ' <a class="link-btn" href="#setup/6">Sign in to Claude</a>') + '</p>' : '');
    html += step('7', 'Tools for your dock', '', 'Pick the apps you use every day. They join the dock as their own windows. Remove one later with a right-click on it.',
      grouped(SETUP.catalog).map((g) => '<div class="setup-group">' + esc(g.name) + '</div><div class="setup-grid">' + g.items.map((t) => setupOpt('checkbox', 'su-tool', t.id, t.added, t.name, t.added ? 'In your dock' : t.url.replace(/^https?:\/\//, '').replace(/\/$/, ''), t.added)).join('') + '</div>').join(''));
    const SL = P.slack || { digest: '08:00', alerts: true, remind: 10, sources: ['calendar', 'board', 'tasks'] };
    html += step('8', 'Slack', setupStatus(SETUP.slackConnected, SETUP.slackConnected ? 'connected' : 'not connected'), 'A morning summary, a note when something new needs you, a reminder before meetings. Through a webhook you make in your own Slack.',
      (SETUP.slackError ? '<p class="tools-error">' + esc(SETUP.slackError) + '</p>' : '')
      + (SETUP.slackConnected ? '<p class="note"><button class="link-btn" type="button" id="sl-test">Send a test</button> · <button class="link-btn" type="button" id="sl-off">Disconnect</button></p>'
        : '<p class="note"><a href="' + esc(SETUP.slackCreate) + '" target="_blank" rel="noopener noreferrer">Create the Brento app in Slack</a>, then Incoming Webhooks, Add New Webhook, pick a channel, Allow, and paste the link. Or <a class="link-btn" href="#setup/4">step by step</a>.</p><div class="cal-form"><div><input id="sl-url" type="password" placeholder="https://hooks.slack.com/services/…" autocomplete="off"><button class="btn" type="button" id="sl-go">Connect</button></div></div>')
      + '<div class="setup-row"><div class="setup-field"><label for="sl-digest">Morning summary at</label><input id="sl-digest" type="time" value="' + esc(SL.digest) + '"></div>'
      + '<div class="setup-field"><label for="sl-remind">Reminder before meetings</label><select id="sl-remind">' + [0, 5, 10, 15, 30].map((m) => '<option value="' + m + '"' + (Number(SL.remind) === m ? ' selected' : '') + '>' + (m ? m + ' minutes' : 'Off') + '</option>').join('') + '</select></div></div>'
      + '<label class="wz-check"><input type="checkbox" id="sl-alerts"' + (SL.alerts ? ' checked' : '') + '> Tell me when something new needs me</label>'
      + '<div class="setup-group">What may go to Slack</div><div class="setup-grid">' + [['calendar', 'Meetings'], ['board', 'Board cards'], ['tasks', 'Obsidian tasks'], ['open-items', 'Open matters'], ['pipeline', 'Job applications']].map((x) => setupOpt('checkbox', 'sl-src', x[0], SL.sources.includes(x[0]), x[1], '')).join('') + '</div>');
    html += step('9', 'Phone', '', 'Brento on your iPhone or Android phone, through this computer. Nothing to install on the phone, only an icon on its home screen.',
      '<div id="phone-box">' + phoneHtml(PHONE) + '</div>');
    html += '<div class="setup-actions"><button class="btn primary" type="button" id="su-save">' + (SETUP.needed ? 'Save and open Brento' : 'Save') + '</button><p class="tools-error" id="su-error" role="alert"></p><span class="note">Settings: ' + esc(SETUP.home) + '</span></div>';
    box.innerHTML = html;
    bindCalendar();
    fetch('/api/phone').then((r) => r.json()).then((j) => { if (!j.error) { PHONE = j; paintPhone(); } }).catch(() => {});
    const slack = (body, done) => post('/api/slack', body).then(() => { toast(done); renderSettings(); }).catch((err) => toast(err.message));
    const slGo = $('#sl-go'), slTest = $('#sl-test'), slOff = $('#sl-off');
    if (slGo) slGo.onclick = () => slack({ url: $('#sl-url').value }, 'Slack connected. A test message is in your channel.');
    if (slTest) slTest.onclick = () => slack({ test: true }, 'Test sent. Check Slack.');
    if (slOff) slOff.onclick = () => slack({ disconnect: true }, 'Slack disconnected.');
    const path = $('#su-vault-path');
    path.oninput = () => { const other = $('input[name="su-vault"][value="__other"]'); if (other && path.value.trim()) other.checked = true; };
    $('#su-probe').onclick = async () => {
      const b = $('#su-probe');
      b.disabled = true;
      try {
        const r = await fetch('/api/setup/board', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Leitstand': '1' },
          body: JSON.stringify({ owner: $('#su-owner').value.trim(), ownerType: $('#su-kind').value, number: Number($('#su-num').value) || 0 }) });
        const j = await r.json();
        $('#su-fields').innerHTML = boardFields(r.ok ? j : { error: j.error });
      } catch (err) { $('#su-fields').innerHTML = boardFields({ error: 'Brento is not answering.' }); } finally { b.disabled = false; }
    };
    $('#su-save').onclick = async () => {
      const pick = ($('input[name="su-vault"]:checked') || {}).value || '';
      const vault = pick === '__other' ? typedPath(path) : pick;
      const srcs = {};
      SETUP.sources.forEach((s) => {
        const box = $('input[name="su-src"][value="' + s.id + '"]');
        srcs[s.id] = { on: !!(box && box.checked) && (!s.vault || !!vault) };
        const p = $('[data-path="' + s.id + '"]');
        if (p) srcs[s.id].path = p.value.trim();
      });
      const board = { owner: $('#su-owner').value.trim(), ownerType: $('#su-kind').value, number: Number($('#su-num').value) || 0,
        statusField: $('#su-status').value.trim(), areaField: $('#su-area').value.trim(), dueField: $('#su-due').value.trim(), doneField: $('#su-done').value.trim() };
      const chosen = $$('input[name="su-tool"]:checked:not(:disabled)').map((x) => x.value);
      const b = $('#su-save');
      b.disabled = true;
      $('#su-error').textContent = '';
      try {
        const r = await fetch('/api/setup', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Leitstand': '1' },
          body: JSON.stringify({ profile: { name: $('#su-name').value.trim(), vault, sources: srcs, board, tasks: { home: $('#su-taskhome').value }, keepBrowsers: SETUP.shared ? $('#su-keep').checked : !!P.keepBrowsers,
            slack: { digest: $('#sl-digest').value || '', remind: Number($('#sl-remind').value), alerts: $('#sl-alerts').checked, sources: $$('input[name="sl-src"]:checked').map((x) => x.value) } }, tools: chosen }) });
        const j = await r.json();
        if (!r.ok) throw new Error(j.error);
        SETUP = j;
        ask.status = null;
        toast('Saved.' + (j.added && j.added.length ? ' Added to the dock: ' + j.added.join(', ') + '.' : ''));
        stateText = '';
        await load();
        loadTools(true);
        paintSetup();
      } catch (err) { $('#su-error').textContent = err.message; } finally { b.disabled = false; }
    };
  }

  /* First start: a wizard, one question per screen. It guesses what it can, and where something has to happen
     outside Brento (install, sign in), a button opens the official program and the page notices when it is done. */
  const WZ = { step: 0, data: null, name: '', vault: '', other: false, stats: null, board: null, boardBusy: '', calOk: false, calEvents: null,
    provider: 'google', slackOn: false, slack: null, tools: null, timer: 0, msg: '' };
  const WZ_STEPS = ['welcome', 'notes', 'board', 'calendar', 'slack', 'tools', 'done'];
  const CAL_HELP = {
    google: { name: 'Google', open: 'https://calendar.google.com/calendar/r/settings', steps: ['Open your Google Calendar settings.', 'On the left, under "Settings for my calendars", click your calendar.', 'Click "Integrate calendar".', 'Copy "Secret address in iCal format" and paste it below.'] },
    outlook: { name: 'Outlook', open: 'https://outlook.office.com/calendar/', steps: ['Open your Outlook calendar.', 'Open Settings, then "Shared calendars".', 'Under "Publish a calendar", pick your calendar and the detail level, then click "Publish".', 'Copy the ICS link and paste it below.'] },
    apple: { name: 'Apple iCloud', open: 'https://www.icloud.com/calendar/', steps: ['Open iCloud Calendar.', 'Point at your calendar on the left and click its info button.', 'Turn on "Public Calendar" and click "Copy". Anyone who has this link can read the calendar, so keep it to yourself.', 'Paste the link below.'] }
  };
  const post = (url, body) => fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Leitstand': '1' }, body: JSON.stringify(body || {}) })
    .then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status); return j; });
  function renderWizard() {
    clearInterval(WZ.timer);
    if (S && S.phone) { pageWrap(pageHead('Welcome', 'Brento is set up on your computer. Open it there to change anything.')); return; }
    pageWrap('<div class="wz" id="wz"><section class="wz-card"><p class="wz-lead">Looking around this computer…</p></section></div>');
    fetch('/api/wizard').then(async (r) => { const j = await r.json(); if (!r.ok) throw new Error(j.error || 'HTTP ' + r.status); return j; }).then((d) => {
      // In the middle of the first setup nothing is saved yet, so what was typed and chosen stays.
      const keep = !!WZ.data && WZ.data.needed && d.needed && !WZ.over;
      WZ.data = d;
      WZ.over = false;
      WZ.calOk = d.calendarConnected;
      WZ.slackOn = d.slackConnected;
      const T = d.team;
      if (!keep) {
        WZ.name = d.name || '';
        const open = d.vaults.find((v) => v.open) || d.vaults[0];
        WZ.vault = d.profile.vault || (d.needed && open ? open.path : '');
        WZ.other = !!d.profile.vault && !d.vaults.some((v) => v.path === d.profile.vault);
        const b = d.profile.board;
        WZ.board = b.owner && b.number ? Object.assign({ title: 'Board ' + b.number, lanesFound: true }, b) : null;
        WZ.tools = WZ.sources = null;
        WZ.msg = '';
        WZ.reached = 0;
        WZ.askOn = !d.needed && !!(d.profile.sources.ask || {}).on;
        WZ.slack = Object.assign({ digest: '08:00', alerts: true, remind: 10 }, (T && T.slack) || {}, d.profile.slack && d.profile.slack.digest !== undefined && !d.needed ? d.profile.slack : {});
      }
      if (T && T.calendar) WZ.provider = T.calendar;
      WZ.teamTried = false;
      // #setup/3 opens a given step for someone who has finished the setup. Before that, no question is jumped over.
      if (d.needed) WZ.step = clamp(routeId === null ? (keep ? WZ.step : 0) : Number(routeId) || 0, 0, WZ.reached);
      else WZ.step = clamp(Number(routeId) || 0, 0, WZ_STEPS.length - 1);
      if (WZ.vault) vaultStats();
      paintWizard();
    }).catch((err) => { const box = $('#wz'); if (box) box.innerHTML = '<section class="wz-card"><p class="tools-error">' + esc(err.message) + '</p></section>'; });
  }
  // Only the line with the result is painted anew, so nothing that is being typed is lost.
  function vaultStats() {
    const asked = WZ.vault;
    WZ.stats = null;
    paintFound();
    return fetch('/api/wizard/vault?path=' + encodeURIComponent(asked)).then((r) => r.json()).then((j) => { if (asked === WZ.vault) { WZ.stats = j; paintFound(); } return j; }).catch(() => null);
  }
  function wzFound() {
    if (!WZ.vault) return '';
    if (!WZ.stats) return '<p class="wz-lead">Counting notes…</p>';
    return WZ.stats.error ? wzWarn(esc(WZ.stats.error)) : wzOk('Found ' + WZ.stats.notes.toLocaleString('en-GB') + ' notes' + (WZ.stats.tasks === null ? '. Brento looks for tasks in them while you go on.' : ' and ' + WZ.stats.tasks + (WZ.stats.tasks === 1 ? ' task' : ' tasks') + ' with a date.'))
      + (WZ.stats.missing ? '<p class="note">' + esc(WZ.stats.missing.charAt(0).toUpperCase() + WZ.stats.missing.slice(1)) + '. Brento tries again by itself.</p>' : '');
  }
  function paintFound() { const box = $('#wz-found'); if (box) box.innerHTML = wzFound(); }
  // Windows puts quotes around a path that was copied.
  const typedPath = (el) => (el ? el.value.trim().replace(/^(["'])(.*)\1$/, '$2').trim() : '');
  function wzGo(delta) {
    clearInterval(WZ.timer);
    WZ.msg = '';
    WZ.step = clamp(WZ.step + delta, 0, WZ_STEPS.length - 1);
    WZ.reached = Math.max(WZ.reached || 0, WZ.step);
    paintWizard();
  }
  // While a sign-in runs, ask every few seconds whether it is done, so nobody has to press anything here.
  function wzPoll() {
    clearInterval(WZ.timer);
    WZ.timer = setInterval(() => {
      if (route !== 'setup') { clearInterval(WZ.timer); return; }
      fetch('/api/wizard/gh').then((r) => r.json()).then((j) => {
        if (j.install && j.install.error && !j.gh.ready) { clearInterval(WZ.timer); WZ.msg = j.install.error; paintWizard(); return; }
        const was = WZ.data.gh.ready && !!WZ.data.gh.login;
        WZ.data.gh = j.gh; WZ.data.projects = j.projects; WZ.data.projectsError = j.projectsError; WZ.data.orgs = j.orgs; WZ.data.signin = j.signin;
        const seen = j.gh.reason + JSON.stringify(j.signin);
        if (j.gh.ready && !was) { clearInterval(WZ.timer); WZ.msg = ''; paintWizard(); }
        else if (!j.gh.ready && seen !== WZ.lastSeen) { WZ.lastSeen = seen; paintWizard(); }
      }).catch(() => {});
    }, 3000);
  }
  function wzPickBoard(body, wait) {
    WZ.boardBusy = wait; paintWizard();
    post('/api/wizard/board', body).then((j) => {
      const T = WZ.data.team;
      // On the team's own board, the lead's field names win over the guess.
      if (T && T.board.owner === j.owner && Number(T.board.number) === Number(j.number)) {
        ['statusField', 'areaField', 'dueField', 'doneField', 'homeAreas'].forEach((k) => { if (T.board[k]) j[k] = T.board[k]; });
        j.team = true;
      }
      WZ.board = j;
    }).catch((err) => { WZ.msg = err.message; }).finally(() => { WZ.boardBusy = ''; paintWizard(); });
  }
  // The Ask box, only ever on the owner's click: what it reads for an answer goes to Claude.
  function wzAskOn() {
    return post('/api/setup', { profile: { sources: { ask: { on: true } } } }).then((j) => {
      WZ.askOn = !!(j.profile.sources.ask || {}).on;
      ask.status = null;
      stateText = '';
      return load();
    }).then(wzDonePaint).catch((err) => toast(err.message));
  }
  function wzDonePaint() { if (WZ_STEPS[WZ.step] === 'done') paintWizard(); }
  // The same polling for the Claude sign-in. It was started for the Ask box, so that is switched on once it is done, also
  // when the owner has gone on to another page in the meantime.
  function wzPollClaude() {
    clearInterval(WZ.claudeTimer);
    const timer = setInterval(() => {
      fetch('/api/wizard/claude').then((r) => r.json()).then((c) => {
        if (WZ.claudeTimer !== timer) return;
        if (WZ.data) WZ.data.claude = c;
        const s = c.signin || {};
        if (!c.ready && s.running) return;
        clearInterval(timer);
        WZ.claudeTimer = 0;
        if (WZ_STEPS[WZ.step] === 'done') WZ.msg = c.ready ? '' : s.error || '';
        if (c.ready) wzAskOn();
        else wzDonePaint();
      }).catch(() => {});
    }, 4000);
    WZ.claudeTimer = timer;
  }
  function wzOpen(action, waitText) {
    WZ.msg = waitText;
    paintWizard();
    post('/api/wizard/open', { action }).then((j) => {
      WZ.data.signin = j.signin;
      paintWizard();
      if (action.startsWith('gh')) wzPoll(); else wzPollClaude();
    }).catch((err) => { WZ.msg = err.message; paintWizard(); });
  }
  // GitHub's one-time code, large, with the button that copies it and opens the page it belongs on.
  function wzCode(again) {
    const s = WZ.data.signin || {};
    if (!/^gh/.test(s.action || '')) return '';
    if (s.error) return wzWarn(esc(s.error));
    if (!s.running || !s.code) return '';
    return '<div class="wz-extra"><p>Your one-time code for GitHub:</p><b class="wz-code" id="wz-code">' + esc(s.code) + '</b>'
      + '<a class="btn primary" id="wz-code-go" href="' + esc(s.url) + '" target="_blank" rel="noopener noreferrer">Copy the code and open GitHub</a>'
      + '<ol class="wz-steps"><li>Sign in there, or make a free account.</li><li>Paste the code and click Continue.</li><li>Click Authorize. Then come back, this page moves on by itself.</li></ol>'
      + '<p><button class="link-btn" type="button" data-open="' + again + '">I need a new code</button></p></div>';
  }
  const wzOk = (text) => '<p class="wz-ok"><span class="dot fresh"></span>' + text + '</p>';
  const wzWarn = (text) => '<p class="wz-warn">' + text + '</p>';
  const wzChoice = (attrs, title, small, on) => '<button type="button" class="wz-choice' + (on ? ' on' : '') + '" ' + attrs + '><b>' + esc(title) + '</b>' + (small ? '<small>' + esc(small) + '</small>' : '') + '</button>';
  function wzNotes() {
    const d = WZ.data;
    let html = '<h2>Your notes</h2><p class="wz-lead">Brento reads your Obsidian notes and the tasks in them that carry a date. It never changes a note.</p><div class="wz-choices">';
    html += d.vaults.map((v) => wzChoice('data-vault="' + esc(v.path) + '"', v.name, v.path, !WZ.other && WZ.vault === v.path)).join('');
    html += wzChoice('data-vault="__other"', 'Another folder', 'Show Brento where it is', WZ.other) + wzChoice('data-vault=""', 'I don\'t use Obsidian', 'Calendar and board only', !WZ.vault && !WZ.other) + '</div>';
    if (WZ.other) html += '<div class="setup-field"><label for="wz-path">Where the folder is</label><input id="wz-path" value="' + esc(WZ.vault) + '" spellcheck="false" placeholder="Paste it here"></div>'
      + (d.platform === 'win32' ? '<p class="note">In the Explorer, right-click the folder, choose <b>Copy as path</b> and paste it here. On Windows 10 hold Shift while you right-click.</p>'
        : d.platform === 'darwin' ? '<p class="note">In the Finder, hold <b>Control</b> and click the folder, then hold <b>Option</b> as well, choose <b>Copy … as Pathname</b> and paste it here.</p>' : '');
    html += '<div id="wz-found">' + wzFound() + '</div>';
    if (d.platform === 'darwin' && /\/(Documents|Desktop|Downloads|Library\/(Mobile Documents|CloudStorage))(\/|$)/.test(WZ.vault)) html += '<p class="note">macOS may ask whether Brento may read this folder. Click Allow, or OK.</p>';
    return html;
  }
  // Said before the click: GitHub's own page asks for more than Brento uses, and in another program's name.
  const WZ_GITHUB = '<p class="note">GitHub then asks you to authorize <b>GitHub CLI</b>. That is GitHub\'s own program, which Brento uses. It always asks for your repositories and gists, to read and to write, and to see your organizations. Brento adds your project boards. '
    + 'It reads your boards and your list of repositories, and writes only when you click for it: a new board, or the lanes on one. You can take it back any time under <a href="https://github.com/settings/applications" target="_blank" rel="noopener noreferrer">github.com/settings/applications</a>.</p>';
  function wzBoard() {
    const d = WZ.data, gh = d.gh;
    let html = '<h2>Your to-do board</h2><p class="wz-lead">Brento reads a free GitHub Project board with three lanes: HIGH, MID and LOW. A HIGH card with a date reaches your home screen in time.</p>';
    const busy = WZ.msg && !(WZ.data.signin && (WZ.data.signin.code || WZ.data.signin.error)) ? '<p class="wz-wait">' + esc(WZ.msg) + '</p>' : '';
    const running = !!(WZ.data.signin && WZ.data.signin.running && WZ.data.signin.code);
    if (!gh.ready && /not installed/i.test(gh.reason)) {
      html += '<p>First, the free GitHub program for this computer.</p>' + (d.canInstall ? '<button class="btn primary" type="button" data-open="gh-install">Install it for me</button>' : '<p class="note">Install it from <a href="https://cli.github.com/" target="_blank" rel="noopener noreferrer">cli.github.com</a>, then come back.</p>') + busy;
      return html;
    }
    if (!gh.ready && /not signed in/i.test(gh.reason)) {
      return html + (running ? '' : '<p>Sign in to GitHub once. A free account is enough.</p><button class="btn primary" type="button" data-open="gh-login">Sign in to GitHub</button>' + WZ_GITHUB) + wzCode('gh-login') + busy;
    }
    if (!gh.ready) return html + (running ? '' : '<p>GitHub still has to allow the access to your boards.</p><button class="btn primary" type="button" data-open="gh-scope">Allow it</button>' + WZ_GITHUB) + wzCode('gh-scope') + busy;
    if (WZ.boardBusy) return html + '<p class="wz-wait">' + esc(WZ.boardBusy) + '</p>';
    const T = d.team;
    if (T && T.board.owner && T.board.number && !WZ.board && !WZ.teamTried) {
      // The team lead fixed the board. Read it once; the owner only confirms.
      WZ.teamTried = true;
      setTimeout(() => wzPickBoard({ action: 'pick', owner: T.board.owner, ownerType: T.board.ownerType, number: T.board.number }, 'Reading your team\'s board…'), 0);
      return html + '<p class="wz-wait">Reading your team\'s board…</p>';
    }
    if (WZ.board) {
      html += wzOk('Connected: <b>' + esc(WZ.board.title) + '</b>' + (WZ.board.url ? ' · <a href="' + esc(WZ.board.url) + '" target="_blank" rel="noopener noreferrer">open on GitHub</a>' : ''));
      if (!WZ.board.lanesFound) html += wzWarn('This board has no lanes HIGH, MID and LOW yet.') + '<button class="btn primary" type="button" id="wz-lanes">Add the lanes for me</button> ';
      return html + '<button class="btn" type="button" id="wz-reboard">Choose another board</button>';
    }
    html += '<div class="wz-choices">' + wzChoice('id="wz-create"', 'Create a new board for me', 'Called "Brento", with the lanes, an area and a due date', false)
      + (d.orgs || []).map((o) => wzChoice('data-org="' + esc(o) + '"', 'Create a team board in ' + o, 'Shared by everyone in ' + o + '. Each person\'s Home shows their own cards.', false)).join('')
      + (d.projects || []).map((p) => wzChoice('data-board="' + p.number + '" data-owner="' + esc(p.owner) + '" data-kind="' + p.ownerType + '"', p.title, p.cards + (p.cards === 1 ? ' card' : ' cards'), false)).join('') + '</div>';
    return html + (d.projectsError ? wzWarn(esc(d.projectsError)) : '') + busy;
  }
  function wzCalendar() {
    const help = CAL_HELP[WZ.provider];
    let html = '<h2>Your calendar</h2><p class="wz-lead">Brento reads your appointments through a link, read only. Meetings where people wait for you reach your home screen, with the join button. Repeating appointments are left out.</p>';
    if (WZ.calOk) return html + wzOk(WZ.calEvents === null ? 'Calendar connected.' : 'Connected: ' + WZ.calEvents + (WZ.calEvents === 1 ? ' appointment' : ' appointments') + ' in the next three months.') + '<button class="btn" type="button" id="wz-calagain">Use another calendar</button>';
    html += '<div class="wz-tabs">' + Object.keys(CAL_HELP).map((k) => '<button type="button" class="wz-tab' + (k === WZ.provider ? ' on' : '') + '" data-provider="' + k + '">' + CAL_HELP[k].name + '</button>').join('') + '</div>';
    html += '<ol class="wz-steps">' + help.steps.map((s, i) => '<li>' + esc(s) + (i === 0 ? ' <a href="' + help.open + '" target="_blank" rel="noopener noreferrer">Open it</a>' : '') + '</li>').join('') + '</ol>';
    return html + '<div class="wz-paste"><input id="wz-cal" type="password" placeholder="Paste the link here" autocomplete="off" spellcheck="false"><button class="btn primary" type="button" id="wz-calgo">Connect</button></div>' + (WZ.msg ? wzWarn(esc(WZ.msg)) : '');
  }
  function wzSlack() {
    let html = '<h2>Slack <span class="pill">optional</span></h2><p class="wz-lead">A short message every morning with what needs you, a note when something new comes up, and a reminder before meetings.</p>';
    if (WZ.slackOn) {
      html += wzOk('Slack connected. A test message is in your channel.');
      return html + '<div class="setup-row"><div class="setup-field"><label for="wz-digest">Morning summary at</label><input id="wz-digest" type="time" value="' + esc(WZ.slack.digest) + '"></div>'
        + '<div class="setup-field"><label for="wz-remind">Reminder before meetings</label><select id="wz-remind">' + [0, 5, 10, 15, 30].map((m) => '<option value="' + m + '"' + (Number(WZ.slack.remind) === m ? ' selected' : '') + '>' + (m ? m + ' minutes' : 'Off') + '</option>').join('') + '</select></div></div>'
        + '<label class="wz-check"><input type="checkbox" id="wz-alerts"' + (WZ.slack.alerts ? ' checked' : '') + '> Tell me when something new needs me</label>';
    }
    html += '<ol class="wz-steps"><li>Click <a href="' + esc(WZ.data.slackCreate) + '" target="_blank" rel="noopener noreferrer"><b>Create the Brento app</b></a>. Slack opens with everything filled in.</li>'
      + '<li>Pick your workspace, click Next, then Create.</li><li>On the left, click "Incoming Webhooks", then "Add New Webhook". Pick the channel for Brento\'s messages and click Allow.</li>'
      + '<li>Copy the webhook link and paste it here.</li></ol>';
    return html + '<div class="wz-paste"><input id="wz-slack" type="password" placeholder="https://hooks.slack.com/services/…" autocomplete="off" spellcheck="false"><button class="btn primary" type="button" id="wz-slackgo">Connect</button></div>' + (WZ.msg ? wzWarn(esc(WZ.msg)) : '');
  }
  function wzTools() {
    const d = WZ.data;
    if (!WZ.tools) {
      const cal = (WZ.provider || '');
      const pick = new Set(d.catalog.filter((t) => t.added).map((t) => t.id));
      if (WZ.vault) pick.add('obsidian');
      if (WZ.calOk && cal === 'google') { pick.add('gmail'); pick.add('google-calendar'); }
      if (WZ.calOk && cal === 'outlook') { pick.add('outlook'); pick.add('outlook-calendar'); pick.add('teams'); }
      if (WZ.slackOn) pick.add('slack');
      ((d.team && d.team.tools) || []).forEach((id) => pick.add(id));
      if (d.claude && d.claude.ready) pick.add('claude');
      WZ.tools = pick;
    }
    return '<h2>Your apps</h2><p class="wz-lead">Pick the apps you use every day. They sit in Brento\'s dock and open in their own window.</p><p class="note">Their logos come from Google\'s icon service. An app you add yourself later gets a letter, so nobody learns its address.</p><div class="wz-apps">'
      + d.catalog.map((t) => '<label class="wz-app' + (t.added ? ' done' : '') + '"><input type="checkbox" data-tool="' + esc(t.id) + '"' + (WZ.tools.has(t.id) ? ' checked' : '') + (t.added ? ' disabled' : '') + '><span>' + esc(t.name) + '</span></label>').join('') + '</div>';
  }
  function wzDone() {
    const d = WZ.data, c = d.claude || {};
    const rows = [];
    rows.push(WZ.vault ? 'Notes from ' + esc(WZ.vault.split(/[\\/]/).pop()) : 'No notes');
    rows.push(WZ.board ? 'Board: ' + esc(WZ.board.title) : 'No board');
    rows.push(WZ.calOk ? 'Calendar connected' : 'No calendar yet');
    rows.push(WZ.slackOn ? 'Slack connected' : 'No Slack');
    let html = '<h2>Brento is ready</h2><ul class="wz-sum">' + rows.map((r) => '<li>' + r + '</li>').join('') + '</ul>';
    if (WZ.vault) {
      html += '<div class="wz-extra"><b>Optional: the Ask box</b><p>Ask questions about your notes. Claude Code answers them on this computer, under your own Claude plan. What it reads for an answer goes to Claude.</p>'
        + (c.ready ? (WZ.askOn ? wzOk('The Ask box is on.') : '<button class="btn" type="button" id="wz-ask">Switch it on</button>')
          : /not installed/i.test(c.reason || '') ? '<a class="btn" href="https://claude.com/claude-code" target="_blank" rel="noopener noreferrer">Get Claude Code</a>'
          : '<button class="btn" type="button" data-open="claude-login">Sign in to Claude and switch it on</button>') + (WZ.msg ? '<p class="wz-wait">' + esc(WZ.msg) + '</p>' : '') + '</div>';
    }
    if (WZ.board && WZ.board.ownerType === 'org' && !(d.team && d.team.board.owner)) {
      html += '<div class="wz-extra"><b>Set up your team in one go</b><p>Save this board, these apps and the Slack timing as team.json in the Brento folder. Commit and push it, and everyone who installs from your copy of the repo gets the same setup without choosing.</p>'
        + (WZ.teamSaved ? wzOk('Saved as team.json. Commit and push it to share.') : '<button class="btn" type="button" id="wz-team">Save as team setup</button>') + '</div>';
    }
    if (d.platform === 'darwin') html += '<div class="wz-extra"><b>Brento on your Mac</b><p>Brento starts when you log in. To open it later, press Cmd and Space, type Brento and press Return.</p></div>';
    if (d.platform === 'win32') html += '<div class="wz-extra"><b>Brento on your computer</b><p>To open Brento later, press the Windows key, type Brento and press Enter. Right-click the icon to pin it to the taskbar.</p></div>';
    html += '<div class="wz-extra"><b>Brento on your phone</b><p>iPhone or Android: Brain, then "Sources and setup", then Phone. It takes a six-digit code, nothing to install.</p></div>';
    return html + '<p class="note">Change anything later: Brain, then "Sources and setup".</p>';
  }
  function wzBoardProfile() {
    const b = WZ.board;
    return { owner: b.owner, ownerType: b.ownerType, number: b.number, statusField: b.statusField, areaField: b.areaField || '', dueField: b.dueField || '', doneField: b.doneField || '',
      homeAreas: b.homeAreas || {}, me: WZ.data.gh.login || WZ.data.profile.board.me || '' };
  }
  function wzSources() {
    const d = WZ.data, old = d.profile.sources, sources = {};
    d.sources.forEach((s) => { sources[s.id] = { on: !!(old[s.id] || {}).on }; if (s.path) sources[s.id].path = (old[s.id] || {}).path || s.path; });
    return sources;
  }
  // The end of the first setup.
  function wzSave() {
    const sources = wzSources();
    sources.library.on = sources.tasks.on = !!WZ.vault; sources.calendar.on = true; sources.board.on = !!WZ.board; sources.ask.on = false;
    WZ.sources = sources;
    const profile = { name: WZ.name, vault: WZ.vault, sources, tasks: WZ.data.profile.tasks, slack: WZ.slack };
    if (WZ.board) profile.board = wzBoardProfile();
    return post('/api/setup', { profile, tools: Array.from(WZ.tools || []) });
  }
  // Someone who has finished the setup came for one page. Only that is saved, everything else stays as they left it.
  function wzSaveOne(name) {
    const p = WZ.data.profile, profile = {}, on = (value) => ({ on: value });
    if (name === 'welcome') profile.name = WZ.name;
    if (name === 'notes' && WZ.vault !== p.vault) {
      profile.vault = WZ.vault;
      if (!p.vault || !WZ.vault) profile.sources = { library: on(!!WZ.vault), tasks: on(!!WZ.vault) };
    }
    if (name === 'board' && WZ.board) { profile.board = wzBoardProfile(); profile.sources = { board: on(true) }; }
    if (name === 'calendar' && WZ.calOk) profile.sources = { calendar: on(true) };
    if (name === 'slack') profile.slack = WZ.slack;
    return post('/api/setup', { profile, tools: name === 'tools' ? Array.from(WZ.tools || []) : [] });
  }
  function paintWizard() {
    const box = $('#wz');
    if (!box || route !== 'setup' || !WZ.data) return;
    const name = WZ_STEPS[WZ.step], one = !WZ.data.needed && !WZ.sources && name !== 'done';
    const dots = name === 'done' || one ? '' : '<div class="wz-dots" aria-label="Step ' + (WZ.step + 1) + ' of 6">' + WZ_STEPS.slice(0, 6).map((s, i) => '<i class="' + (i < WZ.step ? 'done' : i === WZ.step ? 'on' : '') + '"></i>').join('') + '</div>';
    let body = '', next = 'Next', skip = false;
    if (name === 'welcome') {
      body = '<h2>Welcome to ' + (WZ.data.team && WZ.data.team.team ? esc(WZ.data.team.team) + '\'s Brento' : 'Brento') + '</h2><p class="wz-lead">One screen that tells you what needs you today: your tasks, your board and your meetings. Setup takes about two minutes. Brento runs on this computer and keeps its settings here.</p>'
        + '<div class="setup-field"><label for="wz-name">What should Brento call you?</label><input id="wz-name" maxlength="40" value="' + esc(WZ.name) + '" autocomplete="given-name"></div>';
      next = 'Let\'s go';
    } else if (name === 'notes') body = wzNotes();
    else if (name === 'board') { body = wzBoard(); skip = !WZ.board; }
    else if (name === 'calendar') { body = wzCalendar(); skip = !WZ.calOk; }
    else if (name === 'slack') { body = wzSlack(); skip = !WZ.slackOn; }
    else if (name === 'tools') { body = wzTools(); next = 'Finish'; }
    else body = wzDone();
    const error = '<p class="tools-error" id="wz-error" role="alert"></p>';
    const nav = one ? '<div class="wz-nav">' + error + '<button class="btn" type="button" id="wz-close">Cancel</button><button class="btn primary" type="button" id="wz-one">Done</button></div>' : name === 'done' ? '<div class="wz-nav"><span></span><button class="btn primary" type="button" id="wz-home">Open Brento</button></div>'
      : '<div class="wz-nav">' + error + (WZ.step ? '<button class="btn" type="button" id="wz-back">Back</button>' : '<span></span>') + '<span class="wz-right">'
        + (skip ? '<button class="link-btn" type="button" id="wz-skip">Skip for now</button>' : '') + '<button class="btn primary" type="button" id="wz-next">' + next + '</button></span></div>';
    box.innerHTML = '<section class="wz-card">' + dots + body + nav + '</section>';
    bindWizard(name);
  }
  function bindWizard(name) {
    const on = (sel, fn) => { const el = $(sel); if (el) el.onclick = fn; };
    on('#wz-back', () => wzGo(-1));
    on('#wz-skip', () => wzGo(1));
    on('#wz-home', () => { WZ.over = true; stateText = ''; load(); navigate('home'); });
    on('#wz-close', () => { WZ.over = true; stateText = ''; load(); navigate('home'); });
    on('#wz-ask', wzAskOn);
    // A link that was pasted and not connected yet: the button does that first, and the page shows what came of it.
    const pending = () => {
      const field = name === 'calendar' ? $('#wz-cal') : name === 'slack' ? $('#wz-slack') : null;
      if (!field || !field.value.trim()) return false;
      $(name === 'calendar' ? '#wz-calgo' : '#wz-slackgo').click();
      return true;
    };
    on('#wz-one', async () => {
      if (WZ.boardBusy || pending()) return;
      if (name === 'notes' && WZ.other) WZ.vault = typedPath($('#wz-path'));
      const b = $('#wz-one'); b.disabled = true;
      try { await wzSaveOne(name); WZ.over = true; stateText = ''; await load(); loadTools(true); navigate('home'); }
      catch (err) { $('#wz-error').textContent = err.message; b.disabled = false; }
    });
    on('#wz-team', () => post('/api/team', { team: WZ.board.owner, tools: Array.from(WZ.tools || []), calendar: WZ.calOk ? WZ.provider : '' })
      .then(() => { WZ.teamSaved = true; paintWizard(); }).catch((err) => toast(err.message)));
    $$('#wz [data-open]').forEach((b) => { b.onclick = () => wzOpen(b.dataset.open, b.dataset.open === 'gh-install' ? 'Downloading the GitHub program from github.com. This page moves on by itself when it is done.'
      : b.dataset.open === 'claude-login' ? 'Claude\'s sign-in page opens in your browser. Confirm there, then come back. This page moves on by itself.' : 'Getting a code from GitHub…'); });
    on('#wz-code-go', () => { if (navigator.clipboard) navigator.clipboard.writeText($('#wz-code').textContent).then(() => toast('Code copied. Paste it on the GitHub page.')).catch(() => {}); });
    if (name === 'welcome') { const n = $('#wz-name'); n.oninput = () => { WZ.name = n.value.trim(); }; n.focus(); }
    if (name === 'notes') {
      $$('#wz [data-vault]').forEach((b) => { b.onclick = () => { const v = b.dataset.vault; WZ.other = v === '__other'; WZ.vault = WZ.other ? '' : v; if (WZ.vault) vaultStats(); paintWizard(); }; });
      const p = $('#wz-path');
      if (p) { p.onchange = () => { WZ.vault = typedPath(p); if (WZ.vault) vaultStats(); else paintFound(); }; }
    }
    if (name === 'board') {
      const pickBoard = wzPickBoard;
      $$('#wz [data-org]').forEach((b) => { b.onclick = () => pickBoard({ action: 'create', title: 'Brento', org: b.dataset.org }, 'Creating the team board in ' + b.dataset.org + '…'); });
      on('#wz-create', () => pickBoard({ action: 'create', title: 'Brento' }, 'Creating your board on GitHub…'));
      $$('#wz [data-board]').forEach((b) => { b.onclick = () => pickBoard({ action: 'pick', owner: b.dataset.owner, ownerType: b.dataset.kind, number: Number(b.dataset.board) }, 'Reading the board…'); });
      on('#wz-lanes', () => pickBoard({ action: 'lanes', owner: WZ.board.owner, ownerType: WZ.board.ownerType, number: WZ.board.number }, 'Adding the lanes…'));
      on('#wz-reboard', () => { WZ.board = null; paintWizard(); });
      if (!WZ.data.gh.ready && (WZ.msg || (WZ.data.signin && WZ.data.signin.running))) wzPoll();
    }
    if (name === 'calendar') {
      $$('#wz [data-provider]').forEach((b) => { b.onclick = () => { WZ.provider = b.dataset.provider; WZ.msg = ''; paintWizard(); }; });
      on('#wz-calagain', () => { WZ.calOk = false; paintWizard(); });
      on('#wz-calgo', () => {
        const b = $('#wz-calgo'); b.disabled = true; b.textContent = 'Checking…';
        post('/api/calendar', { url: $('#wz-cal').value }).then((j) => { WZ.calOk = j.connected; WZ.calEvents = j.events; WZ.msg = ''; }).catch((err) => { WZ.msg = err.message; }).finally(paintWizard);
      });
    }
    if (name === 'slack') {
      on('#wz-slackgo', () => {
        const b = $('#wz-slackgo'); b.disabled = true; b.textContent = 'Sending a test…';
        post('/api/slack', { url: $('#wz-slack').value }).then((j) => { WZ.slackOn = j.connected; WZ.msg = ''; }).catch((err) => { WZ.msg = err.message; }).finally(paintWizard);
      });
      const keep = () => { const t = $('#wz-digest'), r = $('#wz-remind'), a = $('#wz-alerts'); if (t) WZ.slack = { digest: t.value || '', remind: Number(r.value), alerts: a.checked, sources: WZ.slack.sources }; };
      $$('#wz-digest, #wz-remind, #wz-alerts').forEach((el) => { el.onchange = keep; });
    }
    if (name === 'tools') $$('#wz [data-tool]').forEach((c) => { c.onchange = () => { if (c.checked) WZ.tools.add(c.dataset.tool); else WZ.tools.delete(c.dataset.tool); }; });
    on('#wz-next', async () => {
      if (name === 'notes' && WZ.other) {
        // A folder that cannot be read is said here, not four questions later.
        const typed = typedPath($('#wz-path')), seen = typed === WZ.vault && WZ.stats;
        WZ.vault = typed;
        const found = typed ? seen || await vaultStats() : null;
        if (route !== 'setup' || WZ_STEPS[WZ.step] !== name || (found && found.error)) return undefined;
      }
      if (pending()) return undefined;
      if (name !== 'tools') return wzGo(1);
      if (WZ.boardBusy) { $('#wz-error').textContent = WZ.boardBusy + ' This takes a moment.'; return undefined; }
      const b = $('#wz-next'); b.disabled = true; b.textContent = 'Saving…';
      try {
        await wzSave(); stateText = ''; await load(); loadTools(true);
        // From now on a reload keeps the last page.
        routeId = '6'; history.replaceState(null, '', '#setup/6');
        wzGo(1);
      }
      catch (err) { $('#wz-error').textContent = err.message; b.disabled = false; b.textContent = 'Finish'; }
    });
  }

  /* Router */
  const RENDER = { home: renderHome, today: renderToday, day: renderDay, projects: renderProjects, library: renderLibrary, pipeline: renderPipeline, board: renderBoard, brain: renderBrain, ask: renderAsk, setup: renderWizard, settings: renderSettings };
  function parseHash() {
    const raw = (location.hash || '#home').slice(1);
    const cut = raw.indexOf('/');
    const name = cut < 0 ? raw : raw.slice(0, cut);
    if (!RENDER[name]) return { route: 'home', id: null };
    let id = null;
    if (cut >= 0) { try { id = decodeURIComponent(raw.slice(cut + 1)); } catch (e) { id = null; } }
    return { route: name, id };
  }
  function renderRoute() {
    deckApi = null;
    // One question per page: the dock would only lead away from it, and on a small window it lies over the buttons.
    document.documentElement.classList.toggle('in-setup', route === 'setup' && !S.phone);
    (RENDER[route] || renderHome)();
    $('#view').setAttribute('aria-label', (ROUTES[routeIndex(route)] || { label: route === 'day' ? 'Day' : '' }).label);
  }
  function render() {
    if (S) stripWeek = route === 'day' ? clamp(Math.floor(daysBetween(S.today, openDay()) / 7), 0, lastWeek()) : 0;
    renderTop();
    renderStrip();
    renderDock();
    if (S) { renderRoute(); popAlert(); }
  }

  /* A slide that pops up over whatever page is open, once a day per item. Home needs no pop-up: it is already there. */
  function ackGet() { try { return JSON.parse(store.get('leitstand:ack') || '{}'); } catch (e) { return {}; } }
  function ack(id) { const a = ackGet(); a[id] = S.today; store.set('leitstand:ack', JSON.stringify(a)); }
  function closeAlert() { $('#alert-pop').hidden = true; }
  function popAlert() {
    const box = $('#alert-pop');
    if (route === 'home') { S.alerts.forEach((a) => ack(a.id)); closeAlert(); return; }
    if (!box.hidden || ['ask', 'setup', 'settings'].includes(route) || !$('#palette').hidden || !$('#tools').hidden) return;
    const seen = ackGet();
    const a = S.alerts.find((x) => seen[x.id] !== S.today);
    if (!a) return;
    const target = cardTarget(a), tool = relatedTool(a);
    box.innerHTML = '<div class="alert-box" role="alertdialog" aria-modal="true" aria-label="Needs preparing" style="--c:' + Art.tone(a) + '"><div class="alert-art"></div><div class="alert-copy"><div class="eyebrow"><span class="tag">' + esc(a.eyebrow) + '</span>' + (a.tag ? '<span class="tag ghost">' + esc(a.tag) + '</span>' : '') + '</div><h2>' + esc(a.title) + '</h2>' + (a.body ? '<p>' + esc(a.body) + '</p>' : '') + '<p class="alert-why">' + esc(a.why) + '</p>'
      + '<div class="alert-actions">' + (a.join ? '<a class="btn primary" href="' + esc(a.join) + '" target="_blank" rel="noopener noreferrer" id="alert-join">Join call</a>' : '')
      + (tool ? '<button class="btn' + (a.join ? '' : ' primary') + '" type="button" id="alert-tool">Open ' + esc(tool.name) + '</button>' : '') + (target ? '<a class="btn' + (tool || a.join ? '' : ' primary') + '" href="' + esc(target) + '" id="alert-open">Open note</a>' : '')
      + '<button class="btn" type="button" id="alert-step">Smallest first step</button><button class="btn" type="button" id="alert-later">Later</button></div></div></div>';
    $('.alert-art', box).prepend(cardPicture(a, 900, 300));
    box.hidden = false;
    const done = () => { ack(a.id); closeAlert(); setTimeout(popAlert, 300); };
    $('#alert-later').onclick = done;
    $('#alert-step').onclick = () => { ask.draft = 'Give me the smallest first step, five minutes at most, to prepare for: ' + a.title + '. ' + (a.body || ''); done(); navigate('ask'); };
    if (tool) $('#alert-tool').onclick = (e) => { openTool(tool, e); done(); };
    if (target) $('#alert-open').onclick = done;
    if (a.join) $('#alert-join').onclick = done;
    $('#alert-later').focus();
  }
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-open-tool]');
    if (!b) return;
    const t = toolById(b.dataset.openTool);
    if (t) openTool(t, e);
  });
  // On Home a Home link changes nothing in the URL, so no route fires. It goes back to the first card instead.
  document.addEventListener('click', (e) => {
    if (route === 'home' && deckApi && e.target.closest('a[href="#home"]')) deckApi.first();
  });
  function navigate(target) {
    if (location.hash !== '#' + target) location.hash = target;
    else render();
  }
  function onRoute() {
    const next = parseHash();
    if (next.route === route && next.id === routeId && S && $('#view').children.length) return;
    const delta = (routeIndex(next.route) - routeIndex(route)) || (next.id ? 1 : -1);
    route = next.route; routeId = next.id;
    render();
    // The live page slides in. A view transition would lay a frozen picture over it and lose every click until it ended.
    if (motionFull() && !document.hidden) $('#view').animate([{ opacity: 0, transform: 'translateX(' + (delta < 0 ? -26 : 26) + 'px)' }, { opacity: 1, transform: 'none' }], { duration: 380, easing: 'cubic-bezier(.16, .84, .26, 1)' });
    const page = $('.page');
    if (page) page.scrollTop = 0;
  }
  window.addEventListener('hashchange', onRoute);

  /* Not let in: the frame without anything in it, and the way in. After the next good answer the page starts over. */
  function showLocked() {
    document.documentElement.classList.add('locked');
    document.title = 'Brento';
    const win = /Windows/.test(navigator.userAgent), mac = /Mac OS/.test(navigator.userAgent);
    $('#view').innerHTML = '<div class="page"><div class="wz"><section class="wz-card"><h2>Open Brento with its icon</h2>'
      + '<p class="wz-lead">Brento opens only for the person it belongs to, and this window has not been let in.</p>'
      + '<p class="wz-lead">' + (win ? 'Press the <b>Windows key</b>, type <b>Brento</b> and press <b>Enter</b>. Brento then opens in a window of its own.'
        : mac ? 'Press <b>Cmd</b> and <b>Space</b>, type <b>Brento</b> and press <b>Return</b>. Brento then opens in your browser.'
        : 'Open Brento from your programs, or type <b>brento</b> in a terminal. It then opens in your browser.') + '</p></section></div></div>';
  }

  /* Data */
  let webVersion = null, lookAgain = 0, looked = 0;
  async function load() {
    try {
      const res = await fetch('/api/state');
      if (res.status === 401) {
        const j = await res.json().catch(() => ({}));
        if (j.locked) showLocked();
        // A phone that is no longer paired: the page that comes back asks for the code.
        else if (!WORD) location.reload();
        return;
      }
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const text = await res.text();
      if (document.documentElement.classList.contains('locked')) { location.reload(); return; }
      const now = new Date();
      // Something is still being read: look again soon, not only in a minute.
      clearTimeout(lookAgain);
      looked = (JSON.parse(text).sources || []).some((s) => s.note === 'still loading') ? looked + 1 : 0;
      if (looked && looked < 20) lookAgain = setTimeout(load, 3000);
      $('#refresh').title = 'Refresh now (R). Last read ' + String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
      if (text === stateText) return;
      const first = !S;
      stateText = text;
      S = JSON.parse(text);
      if (first) { webVersion = S.webVersion; if (S.setupNeeded && route !== 'setup' && !S.phone) { location.hash = '#setup'; } render(); return; }
      // New code on disk. Reload, unless that would throw away a question being asked or typed.
      if (S.webVersion !== webVersion && !ask.busy && !ask.draft) { location.reload(); return; }
      // A refresh never pulls the page out from under a question being typed.
      renderTop();
      renderStrip();
      renderDock();
      // The same goes for a note being read, for the setup and for the settings: new data never starts them over.
      if (!['ask', 'library', 'setup', 'settings'].includes(route)) refreshInPlace();
      popAlert();
    } catch (err) {
      if (!S) $('#view').innerHTML = '<div class="offline"><b>Brento is not answering.</b><br>On the computer, open it with its icon: press the Windows key, or Cmd and Space on a Mac, type Brento and press Enter. On a phone: is the computer on, and in the same Wi-Fi?</div>';
    }
  }

  /* The timer reads what the server already has. This makes the server ask GitHub and the calendar right now. */
  async function refreshNow() {
    const b = $('#refresh');
    if (b.classList.contains('busy')) return;
    b.classList.add('busy');
    b.setAttribute('aria-busy', 'true');
    try {
      const res = await fetch('/api/refresh', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Leitstand': '1' }, body: '{}' });
      const j = await res.json();
      if (!res.ok) throw new Error(j.error);
      const before = stateText;
      await load();
      toast(j.problems.length ? 'Not everything could be read. ' + j.problems.join(' ') : stateText === before ? 'Up to date. Nothing changed.' : 'Updated.');
    } catch (err) {
      toast('Could not refresh. Brento is not answering.');
    } finally {
      b.classList.remove('busy');
      b.removeAttribute('aria-busy');
    }
  }

  $('#refresh').innerHTML = icon('refresh');
  $('#refresh').onclick = refreshNow;
  $('#open-palette').innerHTML = icon('search');
  $('#open-palette').onclick = openPalette;
  // Brento runs as the app installed in Chrome (owner, 08.11.2026 evening: back from the desktop window, "it's just a
  // mess"). It is installed already, so the browser's own install offer stays quiet.
  window.addEventListener('beforeinstallprompt', (e) => e.preventDefault());

  applyMotion();
  const startAt = parseHash();
  route = startAt.route; routeId = startAt.id;
  tickClock();
  setInterval(tickClock, 5000);
  renderTop();
  renderDock();
  // A bookmark of a page that lies among the notes. The address that opens it carries a seal, so ask for it and go there.
  async function openVaultPage() {
    try {
      const r = await fetch('/api/library/seal' + location.search), j = await r.json();
      if (r.ok) { location.replace(j.url); return; }
      if (r.status === 401) { showLocked(); return; }
      throw new Error(j.error);
    } catch (err) { $('#view').innerHTML = '<div class="offline"><b>This page cannot be opened.</b><br>' + esc(err.message) + '</div>'; }
  }
  enter().then(() => {
    if (location.pathname !== '/') { openVaultPage(); return; }
    loadTools();
    load();
    setInterval(() => { load(); loadTools(); }, 60000);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) { load(); loadTools(); } });
  });
  let resizeAt = 0;
  window.addEventListener('resize', () => {
    clearTimeout(resizeAt);
    resizeAt = setTimeout(() => { if (route === 'home' && S) renderHome(); }, 180);
  });
})();
