/* Small dependency-free SVG charts (work offline). Each returns an SVG string. */
(function (root) {
  'use strict';
  var JW = root.JW;
  var W = 720;

  // Axis with whole-number ticks: a step of 1, 2, 5, 10, 20, 25, 50... and enough ticks to cover the data.
  function axis(v) {
    var steps = [1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000, 10000, 20000, 50000, 100000];
    var step = steps.find(function (s) { return Math.ceil(v / s) <= 5; }) || 100000;
    var n = Math.max(2, Math.ceil(v / step));
    return { step: step, n: n, max: step * n };
  }
  function svg(h, label, body) {
    return '<svg class="chart" viewBox="0 0 ' + W + ' ' + h + '" role="img" aria-label="' + JW.esc(label) + '">' + body + '</svg>';
  }

  // Vertical bars. series: [{name, values, cls}] drawn on top of each other (first = widest).
  function columns(o) {
    var H = 280, L = 44, R = 10, T = 14, B = 34, n = o.labels.length;
    if (!n) return '';
    var all = []; o.series.forEach(function (s) { all = all.concat(s.values); });
    var ax = axis(Math.max.apply(null, all.concat([1]))), max = ax.max, pw = W - L - R, ph = H - T - B, slot = pw / n;
    var g = '', i, ticks = ax.n;
    for (i = 0; i <= ticks; i++) {
      var y = T + ph - ph * i / ticks;
      g += '<line class="grid" x1="' + L + '" x2="' + (W - R) + '" y1="' + y + '" y2="' + y + '"/><text x="' + (L - 6) +
        '" y="' + (y + 4) + '" text-anchor="end">' + JW.fmt(ax.step * i) + '</text>';
    }
    o.series.forEach(function (s, k) {
      var bw = Math.max(2, slot * (k === 0 ? 0.72 : 0.42));
      s.values.forEach(function (v, j) {
        var h = ph * v / max, x = L + slot * j + (slot - bw) / 2;
        g += '<rect class="' + s.cls + '" x="' + x.toFixed(2) + '" y="' + (T + ph - h).toFixed(2) + '" width="' + bw.toFixed(2) +
          '" height="' + h.toFixed(2) + '"><title>' + JW.esc(o.labels[j] + ' - ' + s.name + ': ' + v) + '</title></rect>';
      });
    });
    var step = Math.ceil(n / 12);
    o.labels.forEach(function (lab, j) {
      if (j % step === 0 || j === n - 1) g += '<text x="' + (L + slot * j + slot / 2) + '" y="' + (H - 12) + '" text-anchor="middle">' + JW.esc(o.short ? o.short(lab) : lab) + '</text>';
    });
    if (o.marker != null) {
      var mx = L + slot * (o.marker + 0.5);
      g += '<line class="median" x1="' + mx + '" x2="' + mx + '" y1="' + T + '" y2="' + (T + ph) + '"/>' +
        '<text class="hl" x="' + Math.min(mx + 6, W - 90) + '" y="' + (T + 12) + '">' + JW.esc(o.markerLabel || '') + '</text>';
    }
    g += '<line class="axis" x1="' + L + '" x2="' + (W - R) + '" y1="' + (T + ph) + '" y2="' + (T + ph) + '"/>';
    return svg(H, o.label, g);
  }

  // Horizontal bars: rows [[label, value]].
  function bars(o) {
    var rows = o.rows, rowH = 26, T = 6, L = 190, R = 56, H = T * 2 + rowH * rows.length;
    if (!rows.length) return '';
    var max = Math.max.apply(null, rows.map(function (r) { return r[1]; }).concat([1]));
    var g = '';
    rows.forEach(function (r, i) {
      var y = T + i * rowH, w = (W - L - R) * r[1] / max, lab = r[0].length > 28 ? r[0].slice(0, 27) + '…' : r[0];
      g += '<text x="' + (L - 8) + '" y="' + (y + 17) + '" text-anchor="end">' + JW.esc(lab) + '</text>' +
        '<rect class="' + (o.cls || 'bar-neutral') + '" x="' + L + '" y="' + (y + 3) + '" width="' + w.toFixed(2) + '" height="' + (rowH - 8) +
        '" rx="2"><title>' + JW.esc(r[0] + ': ' + r[1]) + '</title></rect>' +
        '<text class="vlabel" x="' + (L + w + 6) + '" y="' + (y + 17) + '">' + JW.fmt(r[1]) + '</text>';
    });
    return svg(H, o.label, g);
  }

  // One 100% bar split in two parts: {a:{label,value,cls}, b:{...}}
  function split(o) {
    var H = 96, L = 10, pw = W - 20, tot = o.a.value + o.b.value || 1, wa = pw * o.a.value / tot;
    var g = '<rect class="' + o.a.cls + '" x="' + L + '" y="18" width="' + wa.toFixed(2) + '" height="34"><title>' + JW.esc(o.a.label + ': ' + o.a.value) + '</title></rect>' +
      '<rect class="' + o.b.cls + '" x="' + (L + wa).toFixed(2) + '" y="18" width="' + (pw - wa).toFixed(2) + '" height="34"><title>' + JW.esc(o.b.label + ': ' + o.b.value) + '</title></rect>' +
      '<text class="hl" x="' + L + '" y="72">' + JW.esc(o.a.label + ': ' + JW.fmt(o.a.value)) + '</text>' +
      '<text class="hl" x="' + (W - 10) + '" y="72" text-anchor="end">' + JW.esc(o.b.label + ': ' + JW.fmt(o.b.value)) + '</text>';
    return svg(H, o.label, g);
  }

  // A table with the numbers behind a chart (accessible, and lets anyone check the chart).
  function dataTable(head, rows) {
    return '<details class="data"><summary>Show the numbers</summary><table><thead><tr>' +
      head.map(function (h, i) { return '<th' + (i ? ' class="num"' : '') + '>' + JW.esc(h) + '</th>'; }).join('') +
      '</tr></thead><tbody>' + rows.map(function (r) {
        return '<tr>' + r.map(function (c, i) { return '<td' + (i ? ' class="num"' : '') + '>' + JW.esc(c) + '</td>'; }).join('') + '</tr>';
      }).join('') + '</tbody></table></details>';
  }

  root.JWCharts = { columns: columns, bars: bars, split: split, dataTable: dataTable };
})(window);
