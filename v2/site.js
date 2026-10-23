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

  // ------------------------------------------------------------------ hero: one fixed camera on hand, can and paper, scrubbed by scroll
  var hero = $('#hero'), canvas = $('#hero canvas'), ctx = canvas && canvas.getContext('2d');
  var frames = { im: [], ok: [] }, lastDrawn = -1, heroWant = 0;
  // coarse to fine (every 16th frame first), a few requests at a time so the first frames are not queued behind the rest
  function loadFrames() {
    var order = [], next = 0, busy = 0;
    for (var s2 = 16; s2 >= 1; s2 = Math.floor(s2 / 2)) for (var i = 0; i < V2.hero.n; i += s2) if (order.indexOf(i) < 0) order.push(i);
    function pump() {
      while (busy < 6 && next < order.length) start(order[next++]);
    }
    function start(i) {
      var im = new Image();
      busy++;
      im.decoding = 'async';
      im.onload = function () {
        busy--;
        frames.ok[i] = true;
        if (i === 0) firstFrame();
        if (lastDrawn < 0 || i === heroWant) draw(true);
        pump();
      };
      im.onerror = function () { busy--; pump(); };
      im.src = V2.hero.dir + '/f' + String(i).padStart(4, '0') + '.webp';
      frames.im[i] = im;
    }
    pump();
  }
  // the intro plays once the first frame is decoded and Inter is in (or after 1.8 s, whatever comes first)
  var gotFrame = false, gotFont = false;
  function firstFrame() { gotFrame = true; intro(); }
  function intro(force) {
    if (force || (gotFrame && gotFont)) requestAnimationFrame(function () { document.documentElement.classList.add('ready'); });
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { gotFont = true; copyBox = null; draw(true); intro(); }); else gotFont = true;
  setTimeout(function () { intro(true); }, 1800);
  // the copy's box in CSS px of the hero, from the real widths (fonts included), so the scene can avoid it
  var copyBox = null;
  function measureCopy() {
    var st = $('#hero .sticky').getBoundingClientRect(), c = $('.hero-copy').getBoundingClientRect(), right = 0;
    [$('.hero-copy h1')].concat($$('.hero-lines span'), $$('.hero-ctas > *')).forEach(function (e) { right = Math.max(right, e.offsetLeft + e.offsetWidth); });
    copyBox = { right: c.left - st.left + right, top: c.top - st.top };
    return copyBox;
  }
  function sizeCanvas() {
    copyBox = null;
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = Math.round(canvas.clientWidth * dpr);
    canvas.height = Math.round(canvas.clientHeight * dpr);
    lastDrawn = -1;
  }
  function nearest(i) {
    for (var d = 0; d < V2.hero.n; d++) {
      if (frames.ok[i - d]) return i - d;
      if (frames.ok[i + d]) return i + d;
    }
    return -1;
  }
  function draw(force) {
    if (!ctx) return;
    var want = Math.round(pinned(hero) * 0.94 * (V2.hero.n - 1));   // the last stretch holds the finished painting
    var k = nearest(want);
    heroWant = want;
    if (k < 0 || (want === lastDrawn && !force)) return;
    var cw = canvas.width, ch = canvas.height, wide = cw > ch * 1.15, dpr = cw / canvas.clientWidth;
    var cb = copyBox || measureCopy(), M = 0.06, side, x, y;   // M: the empty margin the render keeps around hand, can and paper
    if (wide) {   // right of the copy, never on it
      var margin = Math.max(22, (cw / dpr - 1240) / 2) * dpr, left = (cb.right + 28) * dpr;
      side = Math.min(ch * 0.96, 820 * dpr, cw * 0.62);
      x = cw - margin - side * (1 - M);
      if (x + side * M < left) { side = Math.max(side * 0.6, (cw - margin - left) / (1 - 2 * M)); x = left - side * M; }
      y = (ch - side) / 2 + 26 * dpr;
    } else {      // between the nav and the copy
      var top = 56 * dpr, room = (cb.top - 16) * dpr - top;
      side = Math.min(cw / (1 - 2 * M), room / (1 - 2 * M));
      x = (cw - side) / 2;
      y = top - side * M + Math.max(0, (room - side * (1 - 2 * M)) / 2);
    }
    ctx.clearRect(0, 0, cw, ch);
    ctx.drawImage(frames.im[k], x, y, side, side);
    lastDrawn = k === want ? want : -2;   // redraw when the wanted frame arrives
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
    if (hint) { hint.style.opacity = p > 0.03 ? 0 : ''; hint.style.pointerEvents = p > 0.03 ? 'none' : ''; }
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
  // Each robot holds, then dissolves into the next as you scroll; from the Franka arm the camera flies into its wrist
  // (a rendered sequence on a canvas) and the hands swap on it. Scroll progress is eased so wheel steps don't show.
  var R = null;
  var smooth = function (x) { return x * x * (3 - 2 * x); };
  function robotsInit() {
    var sec = $('#robots');
    if (!sec) return;
    var imgs = $$('.stage img', sec), n = imgs.length, zi = -1, w = [], tot = 0;
    imgs.forEach(function (im, j) { if (im.dataset.zoom) zi = j; });
    for (var j = 0; j < n - 1; j++) { w.push(j === zi ? 2.4 : 1); tot += w[j]; }
    var cv = $('.stage canvas', sec), zf = [];
    // the fly-in frames load once the section is within a screen and a half
    var near = new IntersectionObserver(function (en) {
      if (!en[0].isIntersecting) return;
      near.disconnect();
      for (var k = 0; zi >= 0 && k < V2.zoom.n; k++) {
        var im = new Image();
        im.decoding = 'async';
        im.src = V2.zoom.dir + '/z' + String(k).padStart(2, '0') + '.webp';
        zf.push(im);
      }
    }, { rootMargin: '150% 0px' });
    near.observe(sec);
    R = { sec: sec, imgs: imgs, n: n, zi: zi, w: w, tot: tot + 0.6, cv: cv, cx: cv.getContext('2d'), zf: zf,
          p: -1, raf: 0, last: 0, phase: 'own', label: 0, zk: -1 };
  }
  function robots() { if (R && !R.raf) { R.last = performance.now(); R.raf = requestAnimationFrame(robotsTick); } }
  function robotsTick(now) {
    R.raf = 0;
    var target = pinned(R.sec), dt = Math.min(64, now - R.last);
    R.last = now;
    if (R.p < 0) R.p = target;
    R.p += (target - R.p) * (1 - Math.exp(-dt / 120));
    if (Math.abs(target - R.p) < 1e-4) R.p = target; else R.raf = requestAnimationFrame(robotsTick);
    robotsDraw();
  }
  function zoomFrame(k) {
    var cv = R.cv, side, dpr = Math.min(window.devicePixelRatio || 1, 2);
    for (var d = 0; d < R.zf.length; d++) {
      var a = R.zf[k - d] || R.zf[k + d], b = R.zf[k + d];
      var im = a && a.complete && a.naturalWidth ? a : b && b.complete && b.naturalWidth ? b : null;
      if (!im) continue;
      if (cv.width !== Math.round(cv.clientWidth * dpr) || cv.height !== Math.round(cv.clientHeight * dpr)) {
        cv.width = Math.round(cv.clientWidth * dpr);
        cv.height = Math.round(cv.clientHeight * dpr);
        R.zk = -1;
      }
      if (im !== R.zk) {
        side = Math.min(cv.width, cv.height);
        R.cx.clearRect(0, 0, cv.width, cv.height);
        R.cx.drawImage(im, (cv.width - side) / 2, (cv.height - side) / 2, side, side);
        R.zk = im;
      }
      return true;
    }
    return false;
  }
  function robotsDraw() {
    var f = R.p * R.tot, j = 0;
    while (j < R.n - 2 && f > R.w[j]) { f -= R.w[j]; j++; }
    var t = clamp(f / R.w[j], 0, 1), fly = j === R.zi;
    var k = fly ? smooth(clamp((t - 0.15) / 0.85, 0, 1)) : smooth(clamp((t - 0.42) / 0.58, 0, 1));
    fly = fly && R.zf.length > 0 && zoomFrame(Math.round(k * (R.zf.length - 1)));
    R.cv.style.opacity = fly ? 1 : 0;
    // hands share the camera and the arm: a pure (additive) dissolve keeps the arm still; other robots drift sideways
    var same = R.imgs[j].dataset.phase === 'hand' && R.imgs[j + 1].dataset.phase === 'hand';
    var dx = same ? 0 : R.sec.clientWidth * 0.035;
    R.imgs.forEach(function (im, i) {
      var o = 0, x = 0;
      if (i === j) { o = 1 - k; x = -dx * k; }
      else if (i === j + 1) { o = k; x = dx * (1 - k); }
      if (fly) o = 0;
      im.style.opacity = o.toFixed(3);
      im.style.transform = x ? 'translate3d(' + x.toFixed(1) + 'px,0,0)' : '';
    });
    var i = k < 0.5 ? j : j + 1, sec = R.sec, ph = R.imgs[i].dataset.phase;
    if (ph !== R.phase) {
      R.phase = ph;
      var copy = $('.ph-copy', sec);
      copy.classList.add('swap');
      setTimeout(function () {
        var tx = V2.phases[R.phase];
        $('#ph-eyebrow').textContent = tx[0];
        $('#ph-title').textContent = tx[1];
        $('#ph-lede').textContent = tx[2];
        $$('.hand-list', sec).forEach(function (ul) { ul.hidden = ul.dataset.phase !== R.phase; });
        copy.classList.remove('swap');
      }, 260);
    }
    if (i !== R.label) {
      R.label = i;
      $$('.hand-list li', sec).forEach(function (li) { li.classList.toggle('on', +li.dataset.i === i); });
      var tag = $('.stage .tag', sec);
      tag.classList.add('swap');
      setTimeout(function () {
        $('b', tag).textContent = R.imgs[R.label].dataset.name;
        $('span', tag).textContent = R.imgs[R.label].dataset.kind;
        tag.classList.remove('swap');
      }, 180);
      $('.counter', sec).textContent = String(i + 1).padStart(2, '0') + ' / ' + String(R.n).padStart(2, '0');
    }
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
  $$('video').forEach(function (v) { v.muted = true; if (!v.closest('.duo.t1')) vio.observe(v); });

  // ------------------------------------------------------------------ Track 1: one task at a time, gripper and hand in sync;
  // the tabs advance by themselves after both clips have played, until someone picks one
  function track1() {
    var box = $('.duo.t1');
    if (!box || !V2.t1) return;
    var vids = { grip: $('video[data-k="grip"]', box), hand: $('video[data-k="hand"]', box) }, tabs = $$('.t1-tabs button');
    var cur = 0, auto = true, done = 0, shown = false;
    function src(k, e) { return V2.clips + '/t1_' + k + '_' + e; }
    function set(i, user) {
      if (user) auto = false;
      cur = i;
      var t = V2.t1[i];
      tabs.forEach(function (b, j) { b.classList.toggle('on', j === i); b.setAttribute('aria-selected', j === i); });
      $('[data-k="grip-name"]', box).textContent = t.grip;
      $('[data-k="grip-score"]', box).textContent = 'Best policy ' + t.gs + '%' + (t.fast ? '   2\u00d7 speed' : '');
      $('[data-k="hand-score"]', box).textContent = 'Best policy ' + t.hs + '%' + (t.fast ? '   2\u00d7 speed' : '');
      box.classList.add('swap');
      setTimeout(function () {
        ['grip', 'hand'].forEach(function (e) { var v = vids[e]; v.poster = src(t.key, e) + '.jpg'; v.src = src(t.key, e) + '.mp4'; v.load(); });
        done = 0;
        if (shown) play();
        box.classList.remove('swap');
      }, 260);
    }
    function play() { ['grip', 'hand'].forEach(function (e) { var p = vids[e].play(); if (p && p.catch) p.catch(function () {}); }); }
    ['grip', 'hand'].forEach(function (e) {
      vids[e].addEventListener('ended', function () {
        if (++done < 2) return;
        if (auto) set((cur + 1) % V2.t1.length);
        else { done = 0; ['grip', 'hand'].forEach(function (k) { vids[k].currentTime = 0; }); play(); }
      });
    });
    tabs.forEach(function (b, j) { b.addEventListener('click', function () { set(j, true); }); });
    new IntersectionObserver(function (en) {
      shown = en[0].isIntersecting;
      if (shown) play(); else { vids.grip.pause(); vids.hand.pause(); }
    }, { threshold: 0.35 }).observe(box);
    set(0);
  }

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
    robotsInit();
    track1();
    var hint = $('.scroll-hint');
    if (hint) hint.addEventListener('click', function () { window.scrollBy({ top: window.innerHeight * 0.9, behavior: 'smooth' }); });
    frame();
  });
})();
