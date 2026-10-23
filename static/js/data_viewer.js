// DexSuite data viewer: pick a task, embodiment, source tier and episode; plays the front and wrist cameras and plots
// the tool center point trajectory with a playhead synced to the video. Assets: static/data_viewer (build_data_viewer.py).
(function () {
  'use strict';
  var BASE = 'static/data_viewer/';
  var TIERS = ['Human teleoperation', 'Scripted expert', 'Machine-generated'];
  var EMBS = ['Robotiq gripper', 'UMI gripper', 'Allegro hand', 'Sharpa hand'];
  var AXES = [{ name: 'x', color: 'var(--series-1)' }, { name: 'y', color: 'var(--series-2)' }, { name: 'z', color: 'var(--series-3)' }];
  var NS = 'http://www.w3.org/2000/svg';
  var tasks = window.DEXSUITE_TASKS || [];
  var sets = [];
  var state = { task: 'pick_place_pan', emb: null, tier: null, ep: 0 };
  var traj = null; // {t: [...], v: [[x,y,z] cm]}
  var geom = null;
  var $ = function (id) { return document.getElementById(id); };

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function svg(tag, attrs) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }
  function taskInfo(key) { return tasks.filter(function (t) { return t.key === key; })[0]; }
  function setsFor(task, emb) {
    return sets.filter(function (s) { return s.task === task && (!emb || s.embodiment === emb); });
  }
  function current() { return setsFor(state.task, state.emb).filter(function (s) { return s.tier === state.tier; })[0]; }

  function optionGroup(container, values, active, onPick, label) {
    container.textContent = '';
    values.forEach(function (v, i) {
      var b = el('button', 'dv-opt' + (v === active ? ' is-active' : ''), label ? label(v, i) : v);
      b.type = 'button';
      b.setAttribute('aria-pressed', v === active ? 'true' : 'false');
      b.addEventListener('click', function () { onPick(v); });
      container.appendChild(b);
    });
  }

  function renderTasks() {
    var box = $('dv-tasks');
    box.textContent = '';
    [1, 2].forEach(function (track) {
      var row = el('div', 'dv-track-row');
      row.appendChild(el('span', 'dv-track', 'Track ' + track));
      box.appendChild(row);
      tasks.filter(function (t) { return t.track === track; }).forEach(function (t) {
        var b = el('button', 'dv-pill' + (t.key === state.task ? ' is-active' : ''), t.name);
        b.type = 'button';
        b.setAttribute('aria-pressed', t.key === state.task ? 'true' : 'false');
        b.addEventListener('click', function () { selectTask(t.key); });
        row.appendChild(b);
      });
    });
  }

  function selectTask(key) {
    state.task = key;
    var embs = EMBS.filter(function (e) { return setsFor(key, e).length; });
    if (embs.indexOf(state.emb) < 0) embs.indexOf('Allegro hand') >= 0 && key !== 'reach' ? state.emb = 'Allegro hand' : state.emb = embs[0];
    selectEmb(state.emb, true);
  }
  function selectEmb(emb, keepTier) {
    state.emb = emb;
    var tiers = TIERS.filter(function (t) { return setsFor(state.task, emb).some(function (s) { return s.tier === t; }); });
    if (!keepTier || tiers.indexOf(state.tier) < 0) state.tier = tiers[0];
    state.ep = 0;
    render();
  }

  function render() {
    renderTasks();
    var info = taskInfo(state.task);
    var embs = EMBS.filter(function (e) { return setsFor(state.task, e).length; });
    var tiers = TIERS.filter(function (t) { return setsFor(state.task, state.emb).some(function (s) { return s.tier === t; }); });
    var set = current();
    $('dv-name').textContent = info.name;
    $('dv-blurb').textContent = info.blurb;
    optionGroup($('dv-emb'), embs, state.emb, function (e) { selectEmb(e, true); });
    optionGroup($('dv-tier'), tiers, state.tier, function (t) { state.tier = t; state.ep = 0; render(); });
    optionGroup($('dv-ep'), set.clips.map(function (c, i) { return i; }), state.ep, function (i) { state.ep = i; render(); },
      function (v) { return String(v + 1); });
    var clip = set.clips[state.ep];
    var rows = [
      ['Track', info.track === 1 ? 'Track 1, cross-embodiment' : 'Track 2, dexterous capability'],
      ['Stages', info.stages.join(', ')],
      ['Success', info.success],
      ['Time limit', info.seconds + ' s'],
      ['This episode', clip.seconds.toFixed(1) + ' s'],
    ];
    var body = $('dv-facts');
    body.textContent = '';
    rows.forEach(function (r) {
      var tr = el('tr');
      tr.appendChild(el('td', '', r[0]));
      tr.appendChild(el('td', '', r[1]));
      body.appendChild(tr);
    });
    var hf = $('dv-hf');
    if (set.hf) { hf.href = 'https://huggingface.co/datasets/' + set.hf; hf.hidden = false; } else { hf.hidden = true; }
    loadClip(clip);
  }

  function loadClip(clip) {
    var video = $('dv-video');
    var src = BASE + 'clips/' + clip.id + '.mp4';
    if (video.getAttribute('src') !== src) {
      video.setAttribute('src', src);
      video.load();
      var p = video.play();
      if (p && p.catch) p.catch(function () {});
    }
    traj = null;
    drawChart();
    fetch(BASE + 'clips/' + clip.id + '.json').then(function (r) { return r.json(); }).then(function (d) {
      var p0 = d.tcp[0];
      traj = {
        t: d.tcp.map(function (_, i) { return i / d.fps; }),
        v: d.tcp.map(function (p) { return [0, 1, 2].map(function (k) { return (p[k] - p0[k]) * 100; }); }),
      };
      drawChart();
    });
  }

  function niceStep(span) {
    var raw = span / 3, pow = Math.pow(10, Math.floor(Math.log10(raw))), n = raw / pow;
    return (n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10) * pow;
  }

  function drawChart() {
    var s = $('dv-chart');
    while (s.firstChild) s.removeChild(s.firstChild);
    var legend = $('dv-legend');
    if (!legend.childNodes.length) {
      AXES.forEach(function (a) {
        var span = el('span');
        var key = el('i');
        key.style.background = a.color;
        span.appendChild(key);
        span.appendChild(document.createTextNode(a.name));
        legend.appendChild(span);
      });
    }
    var W = s.clientWidth || 600, H = s.clientHeight || 150;
    s.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    if (!traj) { geom = null; return; }
    var m = { l: 34, r: 18, t: 6, b: 18 };
    var T = traj.t[traj.t.length - 1] || 1;
    var lo = Infinity, hi = -Infinity;
    traj.v.forEach(function (p) { p.forEach(function (x) { lo = Math.min(lo, x); hi = Math.max(hi, x); }); });
    if (hi - lo < 1) { hi += 0.5; lo -= 0.5; }
    var step = niceStep(hi - lo);
    lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
    var X = function (t) { return m.l + (W - m.l - m.r) * t / T; };
    var Y = function (v) { return m.t + (H - m.t - m.b) * (1 - (v - lo) / (hi - lo)); };
    for (var v = lo; v <= hi + 1e-9; v += step) {
      s.appendChild(svg('line', { class: 'grid', x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v) }));
      var lab = svg('text', { class: 'axis-label', x: m.l - 6, y: Y(v) + 3, 'text-anchor': 'end' });
      lab.textContent = Math.round(v * 10) / 10;
      s.appendChild(lab);
    }
    var tstep = T > 20 ? 5 : T > 8 ? 2 : 1;
    for (var t = 0; t <= T + 1e-9; t += tstep) {
      var tl = svg('text', { class: 'axis-label', x: X(t), y: H - 4, 'text-anchor': 'middle' });
      tl.textContent = t + ' s';
      s.appendChild(tl);
    }
    AXES.forEach(function (a, k) {
      var pts = traj.v.map(function (p, i) { return X(traj.t[i]).toFixed(1) + ',' + Y(p[k]).toFixed(1); }).join(' ');
      s.appendChild(svg('polyline', { class: 'series', points: pts, stroke: a.color }));
      var last = traj.v[traj.v.length - 1][k];
      var end = svg('text', { class: 'end-label', x: W - m.r + 4, y: Y(last) + 3 });
      end.textContent = a.name;
      s.appendChild(end);
    });
    var hover = svg('line', { class: 'hover-line', y1: m.t, y2: H - m.b, x1: -10, x2: -10 });
    var play = svg('line', { class: 'playhead', y1: m.t, y2: H - m.b, x1: m.l, x2: m.l });
    s.appendChild(hover);
    s.appendChild(play);
    geom = { X: X, T: T, m: m, W: W, play: play, hover: hover };
  }

  function tick() {
    var v = $('dv-video');
    if (geom && v.duration) {
      var t = Math.min(geom.T, v.currentTime);
      var x = geom.X(t);
      geom.play.setAttribute('x1', x);
      geom.play.setAttribute('x2', x);
    }
    requestAnimationFrame(tick);
  }

  function nearest(evt) {
    var s = $('dv-chart'), r = s.getBoundingClientRect();
    var x = (evt.clientX - r.left) * (geom.W / r.width);
    var t = Math.max(0, Math.min(geom.T, (x - geom.m.l) / (geom.W - geom.m.l - geom.m.r) * geom.T));
    var i = Math.round(t / geom.T * (traj.t.length - 1));
    return { i: i, t: traj.t[i], px: evt.clientX - r.left };
  }

  function bindChart() {
    var s = $('dv-chart'), tip = $('dv-tooltip');
    s.addEventListener('pointermove', function (evt) {
      if (!geom || !traj) return;
      var n = nearest(evt);
      geom.hover.setAttribute('x1', geom.X(n.t));
      geom.hover.setAttribute('x2', geom.X(n.t));
      tip.textContent = '';
      tip.appendChild(el('strong', '', n.t.toFixed(1) + ' s'));
      AXES.forEach(function (a, k) {
        var row = el('div');
        var key = el('i');
        key.style.background = a.color;
        row.appendChild(key);
        row.appendChild(document.createTextNode(a.name + ' ' + traj.v[n.i][k].toFixed(1) + ' cm'));
        tip.appendChild(row);
      });
      tip.hidden = false;
      var left = Math.min(n.px + 12, s.clientWidth - tip.offsetWidth - 4);
      tip.style.left = left + 'px';
      tip.style.top = '28px';
    });
    s.addEventListener('pointerleave', function () {
      tip.hidden = true;
      if (geom) { geom.hover.setAttribute('x1', -10); geom.hover.setAttribute('x2', -10); }
    });
    s.addEventListener('click', function (evt) {
      if (!geom || !traj) return;
      $('dv-video').currentTime = nearest(evt).t;
    });
    window.addEventListener('resize', drawChart);
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!$('dv')) return;
    fetch(BASE + 'manifest.json').then(function (r) { return r.json(); }).then(function (m) {
      sets = m.sets;
      bindChart();
      var q = new URLSearchParams(window.location.search);  // shareable view: ?task=spray_graffiti&emb=Sharpa%20hand
      if (q.get('task') && taskInfo(q.get('task'))) state.task = q.get('task');
      if (q.get('emb')) state.emb = q.get('emb');
      selectTask(state.task);
      requestAnimationFrame(tick);
    });
  });
})();
