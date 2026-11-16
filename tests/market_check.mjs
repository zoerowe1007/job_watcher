// Checks that the Market page's JavaScript (assets/market-calc.js) gets the same
// numbers as the Python reference from the same history.csv, and tests Browse filtering.
// Run:  node tests/market_check.mjs
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const JW = require('../assets/common.js');
globalThis.JW = JW;
const { compute } = require('../assets/market-calc.js');

const csv = readFileSync(new URL('./fixtures/market_history.csv', import.meta.url), 'utf8');
const expected = JSON.parse(readFileSync(new URL('./fixtures/market_expected.json', import.meta.url), 'utf8'));
const rows = JW.parseCSV(csv).map(JW.typed);
assert.ok(rows.length > 300, 'fixture rows parsed');

const got = JSON.parse(JSON.stringify(compute(rows)));
for (const key of Object.keys(expected)) {
  assert.deepEqual(got[key], expected[key], `Market number differs: ${key}`);
}
console.log('market: JavaScript matches the Python reference for', Object.keys(expected).length, 'numbers');

// Browse filtering
const today = expected.lastRun;
const open = rows.filter(r => r.status === 'open');
const base = { role: false, employer: '', location: '', maxDays: null, minDays: null, q: '', sort: 'new', today };
assert.equal(JW.filterRows(rows, base).length, open.length, 'all open postings');
const role = JW.filterRows(rows, { ...base, role: true });
assert.equal(role.length, open.filter(r => r.in_role).length, 'role switch');
assert.ok(role.every(r => r.in_role && r.status === 'open'));
const emp = JW.filterRows(rows, { ...base, employer: 'Beta' });
assert.ok(emp.length > 0 && emp.every(r => r.employer === 'Beta'));
const loc = JW.filterRows(rows, { ...base, location: 'Dallas, TX' });
assert.ok(loc.every(r => r.location === 'Dallas, TX'));
const week = JW.filterRows(rows, { ...base, maxDays: 7 });
assert.ok(week.every(r => JW.daysBetween(r.first_seen, today) <= 7));
const old = JW.filterRows(rows, { ...base, minDays: 14 });
assert.ok(old.every(r => JW.daysBetween(r.first_seen, today) >= 14));
const s = JW.filterRows(rows, { ...base, q: 'CREDIT' });
assert.ok(s.length > 0 && s.every(r => /credit/i.test(r.title)), 'title search ignores case');
const newest = JW.filterRows(rows, base), oldest = JW.filterRows(rows, { ...base, sort: 'old' });
assert.ok(newest[0].first_seen >= newest[newest.length - 1].first_seen);
assert.ok(oldest[0].first_seen <= oldest[oldest.length - 1].first_seen);
console.log('browse: filters, search and sort behave');
