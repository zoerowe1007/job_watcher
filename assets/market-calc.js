/* Every number on the Market page, computed from the rows of data/history.csv.
   Also loaded by Node (tests/market_check.mjs) and compared with watcher/market.py. */
(function (root) {
  'use strict';
  var JW = root.JW || (typeof require !== 'undefined' ? require('./common.js') : null);

  function median(xs) {
    if (!xs.length) return null;
    var s = xs.slice().sort(function (a, b) { return a - b; }), m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
  }
  function tally(rows, keyFn) {
    var m = {};
    rows.forEach(function (r) { var k = keyFn(r); m[k] = (m[k] || 0) + 1; });
    return Object.keys(m).map(function (k) { return [k, m[k]]; })
      .sort(function (a, b) { return b[1] - a[1] || (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0); });
  }
  function isRole(r) { return r.in_role === true || r.in_role === 'true'; }
  function isFirst(r) { return r.first_run === true || r.first_run === 'true'; }

  function compute(rows) {
    var out = { lastRun: null, firstDate: null, days: [], newAll: [], newRole: [], removed: [],
                openByEmployer: [], daysOpen: [], medianDaysOpen: null,
                share7: { num: 0, den: 0, share: null }, topLocations: [], openCount: 0 };
    if (!rows.length) return out;
    var last = '', first = '9999-99-99';
    rows.forEach(function (r) {
      [r.first_seen, r.last_seen, r.removed_date].forEach(function (d) { if (d && d > last) last = d; });
      if (r.first_seen < first) first = r.first_seen;
    });
    out.lastRun = last; out.firstDate = first;
    var a = JW.toDay(first), b = JW.toDay(last), idx = {};
    for (var d = a; d <= b; d++) { idx[JW.fromDay(d)] = out.days.length; out.days.push(JW.fromDay(d)); }
    out.newAll = out.days.map(function () { return 0; });
    out.newRole = out.newAll.slice(); out.removed = out.newAll.slice();
    rows.forEach(function (r) {
      if (!isFirst(r)) { out.newAll[idx[r.first_seen]]++; if (isRole(r)) out.newRole[idx[r.first_seen]]++; }
      if (r.removed_date) out.removed[idx[r.removed_date]]++;
    });
    var open = rows.filter(function (r) { return r.status === 'open'; });
    out.openCount = open.length;
    out.openByEmployer = tally(open, function (r) { return r.employer; });
    out.topLocations = tally(open, function (r) { return r.location || '(not listed)'; }).slice(0, 10);
    rows.forEach(function (r) {
      if (!isFirst(r) && r.removed_date) out.daysOpen.push(JW.daysBetween(r.first_seen, r.removed_date));
    });
    out.medianDaysOpen = median(out.daysOpen);
    rows.forEach(function (r) {
      if (isFirst(r) || JW.daysBetween(r.first_seen, last) < 7) return;
      out.share7.den++;
      if (r.removed_date && JW.daysBetween(r.first_seen, r.removed_date) <= 7) out.share7.num++;
    });
    if (out.share7.den) out.share7.share = out.share7.num / out.share7.den;
    return out;
  }

  var api = { compute: compute, median: median };
  root.JWMarket = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
