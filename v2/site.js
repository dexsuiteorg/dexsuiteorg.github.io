// DexSuite v2: scroll scenes. No dependencies.
(function () {
  'use strict';
  var V2 = window.V2 || {};
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var clamp = function (x, a, b) { return Math.max(a, Math.min(b, x)); };

  // progress of a tall section: 0 when its top reaches the viewport top, 1 when its bottom reaches the viewport bottom
  function pinned(el) {
    var r = el.getBoundingClientRect();
    return clamp(-r.top / Math.max(1, r.height - window.innerHeight), 0, 1);
  }
  // progress of an element passing through the viewport: 0 when its top is at 85 %, 1 when its bottom is at 45 %
  function passing(el) {
    var r = el.getBoundingClientRect(), h = window.innerHeight;
    return clamp((h * 0.85 - r.top) / (r.height + h * 0.4), 0, 1);
  }

  // ------------------------------------------------------------------ hero: hand and paper layers, scrubbed by scroll
  var hero = $('#hero'), canvas = $('#hero canvas'), ctx = canvas && canvas.getContext('2d');
  var layers = { hand: { im: [], ok: [] }, paper: { im: [], ok: [] } }, lastDrawn = -1;
  function src(layer, i) { return V2.hero[layer] + '/f' + String(i).padStart(4, '0') + '.webp'; }
  function loadFrames() {
    var order = [];
    for (var s2 = 16; s2 >= 1; s2 = Math.floor(s2 / 2)) for (var i = 0; i < V2.hero.n; i += s2) if (order.indexOf(i) < 0) order.push(i);
    order.forEach(function (i) {
      ['paper', 'hand'].forEach(function (L) {
        var im = new Image();
        im.decoding = 'async';
        im.onload = function () { layers[L].ok[i] = true; if (lastDrawn < 0) draw(true); };
        im.src = src(L, i);
        layers[L].im[i] = im;
      });
    });
  }
  function sizeCanvas() {
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(canvas.clientWidth * dpr);
    canvas.height = Math.round(canvas.clientHeight * dpr);
    lastDrawn = -1;
  }
  function nearest(L, i) {
    for (var d = 0; d < V2.hero.n; d++) {
      if (layers[L].ok[i - d]) return i - d;
      if (layers[L].ok[i + d]) return i + d;
    }
    return -1;
  }
  function draw(force) {
    if (!ctx) return;
    var want = Math.round(pinned(hero) * 0.94 * (V2.hero.n - 1));   // the last stretch holds the finished painting
    var ih = nearest('hand', want), ip = nearest('paper', want);
    if (ih < 0 || ip < 0 || (want === lastDrawn && !force)) return;
    var cw = canvas.width, ch = canvas.height, wide = cw > ch * 1.15;
    ctx.clearRect(0, 0, cw, ch);
    var P = layers.paper.im[ip], H = layers.hand.im[ih];
    // paper low and to the right, the hand above it, larger: they are composed, not one photograph
    var pw = wide ? cw * 0.56 : cw * 0.80, ph = pw * P.naturalHeight / P.naturalWidth;
    var px = wide ? cw * 0.42 : (cw - pw) / 2, py = wide ? ch * 0.40 : ch * 0.36;
    var hh = wide ? ch * 0.80 : ch * 0.34, hw = hh * H.naturalWidth / H.naturalHeight;
    var hx = wide ? cw * 0.74 - hw / 2 : (cw - hw) / 2, hy = wide ? ch * 0.04 : ch * 0.07;
    ctx.drawImage(P, px, py, pw, ph);
    ctx.drawImage(H, hx, hy, hw, hh);
    lastDrawn = want;
  }
  function heroCopy() {
    var p = pinned(hero);
    $$('.hero-lines span').forEach(function (s) {
      var a = +s.dataset.from, b = +s.dataset.to;
      s.classList.toggle('on', p >= a && p < b);
    });
    var bar = $('.progress i');
    if (bar) bar.style.width = (p * 100).toFixed(1) + '%';
    var hint = $('.scroll-hint');
    if (hint) hint.style.opacity = p > 0.02 ? 0 : 1;
  }

  // ------------------------------------------------------------------ statement: words light up as it scrolls by
  function statement() {
    $$('.statement').forEach(function (st) {
      var words = $$('.w', st), p = passing(st);
      var k = Math.round(p * 1.6 * words.length);
      words.forEach(function (w, i) { w.classList.toggle('on', i < k); });
    });
  }

  // ------------------------------------------------------------------ robots: arms with their own gripper, arms with a Robotiq, hands on the Franka
  var curPhase = 'own';
  function robots() {
    var sec = $('#robots');
    if (!sec) return;
    var imgs = $$('.stage img', sec);
    var i = clamp(Math.floor(pinned(sec) * imgs.length), 0, imgs.length - 1);
    imgs.forEach(function (im, k) { im.classList.toggle('on', k === i); });
    var ph = imgs[i].dataset.phase;
    if (ph !== curPhase) {
      curPhase = ph;
      var t = V2.phases[ph];
      $('#ph-eyebrow').textContent = t[0];
      $('#ph-title').textContent = t[1];
      $('#ph-lede').textContent = t[2];
      $$('.hand-list', sec).forEach(function (ul) { ul.hidden = ul.dataset.phase !== ph; });
    }
    $$('.hand-list li', sec).forEach(function (li) { li.classList.toggle('on', +li.dataset.i === i); });
    var tag = $('.stage .tag b', sec), sub = $('.stage .tag span', sec), cnt = $('.counter', sec);
    tag.textContent = imgs[i].dataset.name;
    sub.textContent = imgs[i].dataset.kind;
    cnt.textContent = String(i + 1).padStart(2, '0') + ' / ' + String(imgs.length).padStart(2, '0');
  }

  // ------------------------------------------------------------------ horizontal gallery
  function gallery() {
    var sec = $('#dexterity');
    if (!sec) return;
    var track = $('.track', sec);
    var maxX = track.scrollWidth - window.innerWidth + Math.max(22, (window.innerWidth - 1080) / 2);
    track.style.transform = 'translate3d(' + (-Math.max(0, maxX) * pinned(sec)).toFixed(1) + 'px,0,0)';
  }

  // ------------------------------------------------------------------ one-shot effects when things come into view
  function countUp(el, dur) {
    var end = parseFloat(el.dataset.count), dec = (el.dataset.count.split('.')[1] || '').length;
    var t0 = performance.now();
    dur = dur || 1400;
    (function step(t) {
      var k = clamp((t - t0) / dur, 0, 1), e = 1 - Math.pow(1 - k, 3);
      el.textContent = (end * e).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + (el.dataset.suffix || '');
      if (k < 1) requestAnimationFrame(step);
    })(t0);
  }
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (!en.isIntersecting) return;
      var el = en.target;
      el.classList.add('in');
      $$('[data-count]', el).concat(el.dataset.count ? [el] : []).forEach(function (c) { if (!c.dataset.done) { c.dataset.done = 1; countUp(c); } });
      $$('[data-w]', el).forEach(function (b) { b.style.width = b.dataset.w + '%'; });
      $$('.hb', el).forEach(function (b) { var em = $('em', b); if (em) em.style.left = 'calc(' + b.dataset.w + '% + 8px)'; });
      io.unobserve(el);
    });
  }, { threshold: 0.25 });
  $$('.reveal, .observe').forEach(function (el) { io.observe(el); });
  var cio = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      if (!en.isIntersecting) return;
      var el = en.target;
      $$('[data-count]', el).concat(el.dataset.count ? [el] : []).forEach(function (c, k) {
        if (c.dataset.done) return;
        c.dataset.done = 1;
        setTimeout(function () { countUp(c, 2600); }, k * 140);
      });
      cio.unobserve(el);
    });
  }, { threshold: 0.75 });
  $$('.count-on-view').forEach(function (el) { cio.observe(el); });

  // videos play only while visible; the two Pick & Place clips restart together
  var vio = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      var v = en.target;
      if (en.isIntersecting) {
        if (v.dataset.sync) {
          $$('video[data-sync="' + v.dataset.sync + '"]').forEach(function (o) { o.currentTime = 0; var p = o.play(); if (p && p.catch) p.catch(function () {}); });
        } else { var p = v.play(); if (p && p.catch) p.catch(function () {}); }
      } else { v.pause(); }
    });
  }, { threshold: 0.4 });
  $$('video').forEach(function (v) { v.muted = true; vio.observe(v); });

  // ------------------------------------------------------------------ loop
  var ticking = false;
  function frame() {
    ticking = false;
    draw(false);
    heroCopy();
    statement();
    robots();
    gallery();
  }
  function onScroll() { if (!ticking) { ticking = true; requestAnimationFrame(frame); } }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', function () { if (canvas) sizeCanvas(); onScroll(); });
  document.addEventListener('DOMContentLoaded', function () {
    if (canvas && V2.hero) { sizeCanvas(); loadFrames(); }
    frame();
  });
})();
