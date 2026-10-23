// DexSuite data viewer page. Assets: ../static/data_viewer (manifest.json, clips/<id>.mp4 + .json).
(function () {
  'use strict';
  var BASE = '../static/data_viewer/';
  var TIERS = ['Human teleoperation', 'Scripted expert', 'Machine-generated'];
  var EMBS = ['Robotiq gripper', 'UMI gripper', 'Allegro hand', 'Sharpa hand'];
  var XYZ = [{ n: 'x', c: '#2a78d6' }, { n: 'y', c: '#eb6834' }, { n: 'z', c: '#1baf7a' }];
  var GRIP = { n: 'closure', c: '#2a78d6' };
  var NS = 'http://www.w3.org/2000/svg';
  var tasks = window.DV_TASKS, sets = [];
  var st = { task: 'spray_graffiti', emb: null, tier: null, ep: 0 };
  var data = null, charts = {};
  var $ = function (id) { return document.getElementById(id); };
  var front = $('cam-front'), wrist = $('cam-wrist');

  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function sv(tag, a) { var e = document.createElementNS(NS, tag); for (var k in a) e.setAttribute(k, a[k]); return e; }
  function task(k) { return tasks.filter(function (t) { return t.key === k; })[0]; }
  function setsOf(t, e) { return sets.filter(function (s) { return s.task === t && (!e || s.embodiment === e); }); }
  function cur() { return setsOf(st.task, st.emb).filter(function (s) { return s.tier === st.tier; })[0]; }

  function seg(box, values, active, pick, label) {
    box.textContent = '';
    values.forEach(function (v, i) {
      var b = el('button', v === active ? 'on' : '', label ? label(v, i) : v);
      b.type = 'button';
      b.setAttribute('role', 'radio');
      b.setAttribute('aria-checked', v === active);
      b.addEventListener('click', function () { pick(v); });
      box.appendChild(b);
    });
  }

  function picker() {
    var box = $('dv-picker');
    box.textContent = '';
    tasks.forEach(function (t) {
      var b = el('button', t.key === st.task ? 'on' : '');
      b.type = 'button';
      b.setAttribute('role', 'option');
      b.setAttribute('aria-selected', t.key === st.task);
      var img = el('img');
      img.src = 'assets/thumbs/' + t.key + '.jpg';
      img.alt = t.name;
      img.loading = 'lazy';
      b.appendChild(img);
      b.appendChild(el('b', '', t.name));
      b.appendChild(el('small', '', 'Track ' + t.track));
      b.addEventListener('click', function () { selectTask(t.key); });
      box.appendChild(b);
      if (t.key === st.task) requestAnimationFrame(function () {
        box.scrollTo({ left: b.offsetLeft - box.clientWidth / 2 + b.clientWidth / 2, behavior: 'smooth' });
      });
    });
  }

  function selectTask(k) {
    st.task = k;
    var embs = EMBS.filter(function (e) { return setsOf(k, e).length; });
    if (embs.indexOf(st.emb) < 0) st.emb = embs.indexOf('Allegro hand') >= 0 && k !== 'reach' ? 'Allegro hand' : embs[0];
    selectEmb(st.emb);
  }
  function selectEmb(e) {
    st.emb = e;
    var tiers = TIERS.filter(function (t) { return setsOf(st.task, e).some(function (s) { return s.tier === t; }); });
    if (tiers.indexOf(st.tier) < 0) st.tier = tiers[0];
    st.ep = 0;
    render();
  }

  function render() {
    picker();
    var t = task(st.task), set = cur(), clip = set.clips[st.ep];
    $('dv-title').textContent = t.name;
    $('dv-sub').textContent = t.blurb;
    seg($('dv-emb'), EMBS.filter(function (e) { return setsOf(st.task, e).length; }), st.emb, selectEmb);
    seg($('dv-tier'), TIERS.filter(function (x) { return setsOf(st.task, st.emb).some(function (s) { return s.tier === x; }); }), st.tier,
      function (x) { st.tier = x; st.ep = 0; render(); });
    seg($('dv-ep'), set.clips.map(function (_, i) { return i; }), st.ep, function (i) { st.ep = i; render(); }, function (i) { return 'Ep ' + (i + 1); });
    $('f-track').textContent = t.track === 1 ? 'Track 1, cross-embodiment' : 'Track 2, dexterous capability';
    $('f-len').textContent = clip.seconds.toFixed(1) + ' s';
    $('f-limit').textContent = t.seconds + ' s';
    $('f-success').textContent = t.success.charAt(0).toUpperCase() + t.success.slice(1);
    var ch = $('f-stages');
    ch.textContent = '';
    t.stages.forEach(function (s) { ch.appendChild(el('span', '', s)); });
    var hf = $('dv-hf');
    if (set.hf) { hf.hidden = false; hf.href = 'https://huggingface.co/datasets/' + set.hf; $('dv-note').textContent = set.hf + ', episode ' + clip.episode; }
    else { hf.hidden = true; $('dv-note').textContent = 'This set is not on Hugging Face yet.'; }
    var q = new URLSearchParams({ task: st.task, emb: st.emb, tier: st.tier, ep: st.ep + 1 });
    history.replaceState(null, '', '?' + q.toString());
    load(clip);
  }

  function load(clip) {
    var src = BASE + 'clips/' + clip.id + '.mp4';
    if (front.getAttribute('src') !== src) {
      [front, wrist].forEach(function (v) { v.setAttribute('src', src); v.loop = true; v.load(); });
      play();
    }
    data = null;
    drawAll();
    fetch(BASE + 'clips/' + clip.id + '.json').then(function (r) { return r.json(); }).then(function (d) {
      var p0 = d.tcp[0];
      data = {
        t: d.tcp.map(function (_, i) { return i / d.fps; }),
        xyz: d.tcp.map(function (p) { return [0, 1, 2].map(function (k) { return (p[k] - p0[k]) * 100; }); }),
        grip: (d.grip || d.tcp.map(function () { return 0; })).map(function (g) { return [g * 100]; }),
      };
      drawAll();
    });
  }

  // ------------------------------------------------------------------ charts
  function nice(span, n) { var raw = span / n, p = Math.pow(10, Math.floor(Math.log10(raw))), m = raw / p; return (m < 1.5 ? 1 : m < 3.5 ? 2 : m < 7.5 ? 5 : 10) * p; }
  function draw(svg, rows, series, fixed, area) {
    while (svg.firstChild) svg.removeChild(svg.firstChild);
    var W = svg.clientWidth || 600, H = svg.clientHeight || 190;
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    if (!data) return null;
    var m = { l: 36, r: 34, t: 8, b: 22 }, T = data.t[data.t.length - 1] || 1;
    var lo = fixed ? fixed[0] : Infinity, hi = fixed ? fixed[1] : -Infinity;
    if (!fixed) rows.forEach(function (r) { r.forEach(function (v) { lo = Math.min(lo, v); hi = Math.max(hi, v); }); });
    if (hi - lo < 1) { hi += 0.5; lo -= 0.5; }
    var step = nice(hi - lo, 3);
    if (!fixed) { lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step; }
    var X = function (t) { return m.l + (W - m.l - m.r) * t / T; }, Y = function (v) { return m.t + (H - m.t - m.b) * (1 - (v - lo) / (hi - lo)); };
    for (var v = lo; v <= hi + 1e-9; v += step) {
      svg.appendChild(sv('line', { class: 'grid', x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v) }));
      var a = sv('text', { class: 'axis', x: m.l - 8, y: Y(v) + 4, 'text-anchor': 'end' }); a.textContent = Math.round(v * 10) / 10; svg.appendChild(a);
    }
    var ts = T > 20 ? 5 : T > 8 ? 2 : 1;
    for (var t = 0; t <= T + 1e-9; t += ts) { var b = sv('text', { class: 'axis', x: X(t), y: H - 4, 'text-anchor': 'middle' }); b.textContent = t + ' s'; svg.appendChild(b); }
    series.forEach(function (s, k) {
      var pts = rows.map(function (r, i) { return X(data.t[i]).toFixed(1) + ',' + Y(r[k]).toFixed(1); });
      if (area) svg.appendChild(sv('polygon', { class: 'area', fill: s.c, points: X(0) + ',' + Y(lo) + ' ' + pts.join(' ') + ' ' + X(T) + ',' + Y(lo) }));
      svg.appendChild(sv('polyline', { class: 'series', stroke: s.c, points: pts.join(' ') }));
      if (series.length > 1) { var e = sv('text', { class: 'end', x: W - m.r + 6, y: Y(rows[rows.length - 1][k]) + 4 }); e.textContent = s.n; svg.appendChild(e); }
    });
    var hover = sv('line', { class: 'hover', x1: -9, x2: -9, y1: m.t, y2: H - m.b }), ph = sv('line', { class: 'playhead', x1: m.l, x2: m.l, y1: m.t, y2: H - m.b });
    svg.appendChild(hover); svg.appendChild(ph);
    return { X: X, T: T, m: m, W: W, ph: ph, hover: hover, rows: rows, series: series };
  }
  function drawAll() {
    charts.tcp = draw($('ch-tcp'), data ? data.xyz : [], XYZ, null, false);
    charts.grip = draw($('ch-grip'), data ? data.grip : [], [GRIP], [0, 100], true);
    var lg = $('lg-tcp');
    if (!lg.childNodes.length) XYZ.forEach(function (s) { var sp = el('span'), i = el('i'); i.style.background = s.c; sp.appendChild(i); sp.appendChild(document.createTextNode(s.n)); lg.appendChild(sp); });
  }
  function bindChart(id, key, unit) {
    var svg = $(id), tip = $('dv-tip');
    svg.addEventListener('pointermove', function (ev) {
      var g = charts[key];
      if (!g || !data) return;
      var r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) * g.W / r.width;
      var t = Math.max(0, Math.min(g.T, (x - g.m.l) / (g.W - g.m.l - g.m.r) * g.T)), i = Math.round(t / g.T * (data.t.length - 1));
      g.hover.setAttribute('x1', g.X(data.t[i])); g.hover.setAttribute('x2', g.X(data.t[i]));
      tip.textContent = '';
      tip.appendChild(el('strong', '', data.t[i].toFixed(1) + ' s'));
      g.series.forEach(function (s, k) { var d = el('div'), ic = el('i'); ic.style.background = s.c; d.appendChild(ic); d.appendChild(document.createTextNode(s.n + ' ' + g.rows[i][k].toFixed(1) + unit)); tip.appendChild(d); });
      tip.hidden = false;
      var box = svg.closest('.dv-charts').getBoundingClientRect();
      tip.style.left = Math.min(ev.clientX - box.left + 14, box.width - tip.offsetWidth - 6) + 'px';
      tip.style.top = (r.top - box.top + 40) + 'px';
    });
    svg.addEventListener('pointerleave', function () { tip.hidden = true; var g = charts[key]; if (g) { g.hover.setAttribute('x1', -9); g.hover.setAttribute('x2', -9); } });
    svg.addEventListener('click', function (ev) {
      var g = charts[key];
      if (!g || !data) return;
      var r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) * g.W / r.width;
      seek(Math.max(0, Math.min(g.T, (x - g.m.l) / (g.W - g.m.l - g.m.r) * g.T)));
    });
  }

  // ------------------------------------------------------------------ transport: front is the master clock, wrist follows
  function play() { [front, wrist].forEach(function (v) { var p = v.play(); if (p && p.catch) p.catch(function () {}); }); $('dv-play').classList.remove('paused'); }
  function pause() { front.pause(); wrist.pause(); $('dv-play').classList.add('paused'); }
  function seek(t) { front.currentTime = t; wrist.currentTime = t; }
  $('dv-play').addEventListener('click', function () { front.paused ? play() : pause(); });
  var scrub = $('dv-scrub'), dragging = false;
  scrub.addEventListener('input', function () { dragging = true; if (front.duration) seek(scrub.value / 1000 * front.duration); });
  scrub.addEventListener('change', function () { dragging = false; });
  function tick() {
    if (front.duration) {
      if (Math.abs(wrist.currentTime - front.currentTime) > 0.08) wrist.currentTime = front.currentTime;
      if (!dragging) scrub.value = Math.round(front.currentTime / front.duration * 1000);
      $('dv-time').textContent = front.currentTime.toFixed(1) + ' s';
      ['tcp', 'grip'].forEach(function (k) {
        var g = charts[k];
        if (g) { var x = g.X(Math.min(g.T, front.currentTime)); g.ph.setAttribute('x1', x); g.ph.setAttribute('x2', x); }
      });
    }
    requestAnimationFrame(tick);
  }

  document.addEventListener('DOMContentLoaded', function () {
    fetch(BASE + 'manifest.json').then(function (r) { return r.json(); }).then(function (m) {
      sets = m.sets;
      bindChart('ch-tcp', 'tcp', ' cm');
      bindChart('ch-grip', 'grip', ' %');
      var q = new URLSearchParams(location.search);
      if (q.get('task') && task(q.get('task'))) st.task = q.get('task');
      if (q.get('emb')) st.emb = q.get('emb');
      if (q.get('tier')) st.tier = q.get('tier');
      selectTask(st.task);
      if (q.get('ep')) { var e = parseInt(q.get('ep'), 10) - 1; if (cur() && cur().clips[e]) { st.ep = e; render(); } }
      window.addEventListener('resize', drawAll);
      requestAnimationFrame(tick);
    });
  });
})();
