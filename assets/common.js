/* Shared helpers for all three pages (also loaded by Node for the tests). */
(function (root) {
  'use strict';
  var JW = {};

  /* ---------- CSV ---------- */
  // Parses RFC 4180 CSV (quoted fields, doubled quotes, newlines inside quotes) into objects.
  JW.parseCSV = function (text) {
    var rows = [], row = [], field = '', i = 0, q = false, c;
    if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
    while (i < text.length) {
      c = text[i];
      if (q) {
        if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else q = false; }
        else field += c;
      } else if (c === '"') q = true;
      else if (c === ',') { row.push(field); field = ''; }
      else if (c === '\n' || c === '\r') {
        if (c === '\r' && text[i + 1] === '\n') i++;
        row.push(field); field = '';
        if (row.length > 1 || row[0] !== '') rows.push(row);
        row = [];
      } else field += c;
      i++;
    }
    if (field !== '' || row.length) { row.push(field); rows.push(row); }
    if (!rows.length) return [];
    var head = rows.shift();
    return rows.map(function (r) {
      var o = {};
      head.forEach(function (h, k) { o[h] = r[k] === undefined ? '' : r[k]; });
      return o;
    });
  };

  // Turn the string cells of a parsed history row into the types the pages use.
  JW.typed = function (r) {
    r.in_role = r.in_role === 'true' || r.in_role === true;
    r.first_run = r.first_run === 'true' || r.first_run === true;
    return r;
  };

  /* ---------- dates (all UTC, YYYY-MM-DD) ---------- */
  JW.toDay = function (s) { var p = s.split('-'); return Date.UTC(+p[0], +p[1] - 1, +p[2]) / 86400000; };
  JW.fromDay = function (n) { return new Date(n * 86400000).toISOString().slice(0, 10); };
  JW.daysBetween = function (a, b) { return JW.toDay(b) - JW.toDay(a); };   // b minus a
  JW.shortDate = function (s) { return s.slice(5); };

  /* ---------- text ---------- */
  JW.esc = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  JW.plural = function (n, one, many) { return n + ' ' + (n === 1 ? one : (many || one + 's')); };
  JW.fmt = function (n) { return Number(n).toLocaleString('en-US'); };

  /* ---------- Browse: pure filtering so it can be tested ---------- */
  // opts: {role:true|false, employer, location, maxDays|null, minDays|null, q, sort:'new'|'old', today}
  JW.filterRows = function (rows, o) {
    var q = (o.q || '').trim().toLowerCase();
    var out = rows.filter(function (r) {
      if (r.status !== 'open') return false;
      if (o.role && !r.in_role) return false;
      if (o.employer && r.employer !== o.employer) return false;
      if (o.location && (r.location || '(not listed)') !== o.location) return false;
      var d = JW.daysBetween(r.first_seen, o.today);
      if (o.maxDays != null && d > o.maxDays) return false;
      if (o.minDays != null && d < o.minDays) return false;
      if (q && r.title.toLowerCase().indexOf(q) === -1) return false;
      return true;
    });
    var dir = o.sort === 'old' ? 1 : -1;
    out.sort(function (a, b) {
      if (a.first_seen !== b.first_seen) return a.first_seen < b.first_seen ? -dir : dir;
      return a.title < b.title ? -1 : a.title > b.title ? 1 : 0;
    });
    return out;
  };

  root.JW = JW;
  if (typeof module !== 'undefined' && module.exports) module.exports = JW;
  if (typeof document === 'undefined') return;

  /* ---------- browser only ---------- */
  var DATA = { history: 'data/history.csv', status: 'data/status.json' };

  // Load both data files. Online they come from the network; offline the service
  // worker answers from its cache and marks the response (x-from-cache).
  JW.loadData = function () {
    function get(url) {
      return fetch(url, { cache: 'no-cache' }).then(function (res) {
        if (!res.ok) throw new Error(url + ' -> ' + res.status);
        var cached = res.headers.get('x-from-cache') === '1';
        return res.text().then(function (t) { return { text: t, cached: cached }; });
      });
    }
    return Promise.all([get(DATA.status), get(DATA.history)]).then(function (a) {
      var status = JSON.parse(a[0].text);
      var history = JW.parseCSV(a[1].text).map(JW.typed);
      var cached = a[0].cached || a[1].cached;
      if (cached) {
        var b = document.getElementById('banner');
        if (b) {
          b.hidden = false;
          b.textContent = 'You are offline. Showing the data from the last run this device loaded (' +
            JW.runLabel(status.run_time) + ').';
        }
      }
      return { status: status, history: history, cached: cached };
    });
  };

  JW.runLabel = function (iso) {
    var d = new Date(iso);
    if (isNaN(d)) return iso;
    return iso.slice(0, 10) + ' ' + iso.slice(11, 16) + ' UTC';
  };

  JW.showError = function (err) {
    var el = document.getElementById('content') || document.querySelector('main');
    el.insertAdjacentHTML('afterbegin',
      '<div class="card" role="alert"><strong>Could not load the data.</strong> ' + JW.esc(err.message) +
      '<br>The pipeline may not have run yet. Open the Actions tab of the repository and run "daily run".</div>');
  };

  /* ---------- shortlist (stars), kept in the browser ---------- */
  var KEY = 'jobwatcher.shortlist.v1';
  JW.shortlist = {
    all: function () {
      try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { return []; }
    },
    has: function (id) { return this.all().indexOf(id) !== -1; },
    toggle: function (id) {
      var list = this.all(), i = list.indexOf(id);
      if (i === -1) list.push(id); else list.splice(i, 1);
      try { localStorage.setItem(KEY, JSON.stringify(list)); } catch (e) { /* storage blocked */ }
      return i === -1;
    }
  };

  /* ---------- posting list item ---------- */
  JW.postingItem = function (r, opts) {
    opts = opts || {};
    var star = opts.star ? '<button class="star" data-id="' + JW.esc(r.posting_id) + '" aria-pressed="' +
      JW.shortlist.has(r.posting_id) + '" aria-label="Shortlist: ' + JW.esc(r.title) + '" title="Add to shortlist">' +
      (JW.shortlist.has(r.posting_id) ? '★' : '☆') + '</button>' : '';
    var meta = [r.employer, r.location, r.department].filter(Boolean).map(JW.esc).join(' · ');
    var extra = [];
    if (r.in_role) extra.push('<span class="pill role">my role</span>');
    if (opts.showDays) extra.push(JW.plural(JW.daysBetween(r.first_seen, opts.today), 'day') + ' open' +
      (r.first_run ? '+' : ''));
    if (opts.showFirstSeen) extra.push('first seen ' + r.first_seen);
    if (r.status === 'removed') extra.push('removed ' + r.removed_date);
    var link = r.url ? '<a href="' + JW.esc(r.url) + '" target="_blank" rel="noopener">' + JW.esc(r.title || r.source_id) + '</a>'
      : JW.esc(r.title || r.source_id);
    var apply = opts.apply && r.url ? '<a class="btn" href="' + JW.esc(r.url) + '" target="_blank" rel="noopener">Apply</a>' : '';
    return '<li>' + star + '<div class="main"><div class="title">' + link + '</div><div class="meta">' + meta +
      (extra.length ? '<br>' + extra.join(' · ') : '') + '</div></div>' + apply + '</li>';
  };

  /* ---------- service worker ---------- */
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('sw.js').catch(function () { /* not fatal */ });
    });
  }
})(typeof window !== 'undefined' ? window : globalThis);
