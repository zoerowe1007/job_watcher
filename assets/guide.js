/* Plain-language labels, explanations and small page pieces shared by the three pages.
   (Browser only: the numbers themselves are computed in common.js and market-calc.js.) */
(function (root) {
  'use strict';
  var JW = root.JW, esc = JW.esc;

  JW.ROLE_TEXT = 'analyst roles in finance and data: titles with "analyst", "analytics", "FP&A", "financial planning" or "business intelligence", leaving out directors, managers and vice presidents and unrelated fields such as security, software or nursing';

  JW.TERMS = [
    ['Posting', 'One job advertised on an employer\'s careers website. It has a stable key (employer + the employer\'s own job number), so the same posting lines up from day to day.'],
    ['Employer board / source', 'An employer\'s public careers site. The tool reads it every day with no login, in the same way the "Apply" pages do.'],
    ['Run', 'One check of every board. It runs by itself several times a day; a later run on the same date replaces the earlier one, so each date counts once.'],
    ['History', 'The file data/history.csv: one row per posting ever seen, with the day it was first seen, last seen, and removed. Every page is calculated from it.'],
    ['Open / removed', 'A posting is open while its employer still lists it. It is removed on the day its employer\'s board stops listing it.'],
    ['New', 'A posting the tool sees for the first time. Postings that were already open on a board\'s very first read are not counted as new, because we cannot know when they were really posted.'],
    ['Starting point (+)', 'Postings already open when tracking began. Their "days open" is shown with a + (for example "4+ days") because they were open for longer than we can see.'],
    ['My role', 'Postings whose titles match the title rule: ' + JW.ROLE_TEXT + '. They are marked with a pink "my role" tag.'],
    ['Days open', 'For an open posting, the days since the tool first saw it. For a removed one, the days between first seen and removed.'],
    ['Shortlist', 'The postings you star on Browse. They are saved only in your own browser.'],
    ['UTC', 'The time zone every date uses. A UTC day can start late in the evening in the United States.']
  ];
  JW.guide = {};
  JW.guide.glossary = function () {
    return '<details class="card glossary"><summary>Glossary: what the words on these pages mean</summary><dl>' +
      JW.TERMS.map(function (t) { return '<dt>' + esc(t[0]) + '</dt><dd>' + esc(t[1]) + '</dd>'; }).join('') + '</dl></details>';
  };
  JW.guide.flow = function (c) {
    function step(n, title, text) {
      return '<li class="step' + (n === 4 ? ' here' : '') + '"><span class="n">' + n + '</span><strong>' + title + '</strong><span>' + text + '</span></li>';
    }
    return '<ol class="flow" aria-label="How the data gets to this page">' +
      step(1, 'Employer job boards', JW.plural(c.employers, 'employer') + ' in the Dallas–Fort Worth and Northwest Arkansas areas and beyond, read from their public careers sites. No login needed.') +
      step(2, 'Daily download', 'GitHub saves each board\'s answer untouched in <code>data/raw/</code> several times a day. ' + JW.plural(c.days, 'day') + ' saved so far.') +
      step(3, 'History table', 'Each posting gets one row in <code>data/history.csv</code> with when it was first seen and when it left: ' + JW.fmt(c.rows) + ' postings so far.') +
      step(4, 'These pages', 'Your browser reads that one file and does the sums: <a href="index.html">Today</a> (what changed), <a href="browse.html">Browse</a> (find a posting), <a href="market.html">Market</a> (the big picture).') +
      '</ol>';
  };
  JW.guide.next = function (links) {
    return '<nav class="next" aria-label="Where to next"><strong>Where to next</strong>' +
      links.map(function (l) { return '<a class="btn ghost" href="' + l[0] + '">' + esc(l[1]) + '</a>'; }).join('') + '</nav>';
  };
  JW.hash = function () {
    var out = {};
    location.hash.replace(/^#/, '').split('&').forEach(function (p) {
      var kv = p.split('='); if (kv[0]) out[kv[0]] = decodeURIComponent(kv[1] || '');
    });
    return out;
  };
  JW.browseHref = function (params) {
    return 'browse.html#' + Object.keys(params).map(function (k) { return k + '=' + encodeURIComponent(params[k]); }).join('&');
  };
})(window);
