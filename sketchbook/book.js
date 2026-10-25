/* The sketchbook. The closed book in the Art section flies to the middle of the
   screen, opens on its spiral binding, and turns its pages in 3D: click a side,
   use the arrow keys, or drag a page and let go. Always a two-page spread
   with drawings on both sides of a leaf, like a real book. Every motion is a small tween on numbers, so a drag can hand its angle
   straight to the release animation. */
(function () {
  var data = document.getElementById("sketch-pages");
  var closed = document.querySelector(".sketch3d");
  if (!data || !closed || !window.HTMLDialogElement) return;
  var pages = JSON.parse(data.textContent);
  var calm = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Curves from the animation tokens: on-screen movement eases in and out,
  // a page let go from the hand only decelerates.
  var IN_OUT = bezier(0.77, 0, 0.175, 1), OUT = bezier(0.23, 1, 0.32, 1);

  var dlg = document.createElement("dialog");
  dlg.className = "sk";
  dlg.setAttribute("aria-label", "Gokul's sketchbook");
  dlg.innerHTML =
    '<div class="sk-stage"><div class="sk-book"></div></div>' +
    '<p class="sk-hint"></p>' +
    '<button class="btn sk-shut" type="button">Close</button>' +
    '<div class="sk-ui"><button class="btn prev" type="button">Back</button>' +
    '<span class="sk-count" aria-live="polite"></span>' +
    '<button class="btn next" type="button">Next</button></div>';
  document.body.appendChild(dlg);
  var stage = dlg.querySelector(".sk-stage"), bookEl = dlg.querySelector(".sk-book");
  var hint = dlg.querySelector(".sk-hint"), count = dlg.querySelector(".sk-count");
  var prev = dlg.querySelector(".prev"), next = dlg.querySelector(".next");

  var W, H, leaves = [], at = 0, busy = null, opened = false;
  var cam = {dx: 0, dy: 0, s: 1, rx: 10, ry: 0, rz: 0, x: 0};   // the whole book's pose

  // ---- building ------------------------------------------------------------
  function side(kind, i, half) {
    var f = document.createElement("div");
    f.className = "sk-face";
    if (kind === "page") {
      var img = new Image();
      img.src = pages[i].src; img.alt = pages[i].alt; img.draggable = false;
      f.appendChild(img);
      f.dataset.page = i + 1;
      if (half) f.className += " half " + half;               // one half of a drawing across the spread
    } else if (kind === "cover") {
      f.className += " cv";
      f.innerHTML = closed.querySelector(".cv").innerHTML;   // the same cover as the closed book
    } else if (kind === "inside") {
      f.className += " inside";
    } else if (kind === "end") {
      f.className += " inside endpaper";
      f.textContent = "More pages loading.";
    }
    return f;
  }

  function size() {
    // always a two-page spread, like a real book; phones get a smaller one
    var ratio = 420 / 580, room = innerWidth - (innerWidth >= 760 ? 80 : 20);
    H = Math.min(innerHeight * 0.74, 660);
    W = H * ratio;
    if (2 * W > room) { W = room / 2; H = W / ratio; }
    bookEl.style.setProperty("--w", W + "px");
    bookEl.style.setProperty("--h", H + "px");
  }

  function build() {
    size();
    bookEl.innerHTML = '<div class="sk-back"></div><div class="sk-edge"></div>';
    var under = side("end");
    under.style.transform = "translateZ(0.1px)";
    bookEl.appendChild(under);
    // the sides in reading order; each leaf takes a front and a back
    var sides = [side("cover"), side("inside")];
    // A landscape drawing spans the whole spread, across the binding, like a
    // real sketchbook: its left half on a left page (a leaf's back, an odd
    // position here), its right half on the next right page.
    pages.forEach(function (p, i) {
      if (p.w <= p.h) { sides.push(side("page", i)); return; }
      if (sides.length % 2 === 0) sides.push(side("inside"));   // start it on a left page
      sides.push(side("page", i, "l"), side("page", i, "r"));
    });
    if (sides.length % 2) sides.push(side("inside"));
    leaves = [];
    for (var i = 0; i < sides.length; i += 2) {
      var leaf = document.createElement("div");
      leaf.className = "sk-leaf";
      sides[i].className += " front";
      sides[i + 1].className += " back";
      leaf.appendChild(sides[i]); leaf.appendChild(sides[i + 1]);
      leaf.a = 0;
      leaves.push(leaf);
      bookEl.appendChild(leaf);
    }
    var rings = document.createElement("div");
    rings.className = "sk-rings";
    rings.innerHTML = new Array(12).join("<i></i>");
    bookEl.appendChild(rings);
    at = 0;
    leaves.forEach(drawLeaf);
  }

  // ---- drawing ---------------------------------------------------------------
  function drawLeaf(leaf, i) {
    i = leaves.indexOf(leaf);
    var t = -leaf.a / 180;                          // 0 lying right, 1 lying left
    var lift = Math.sin(t * Math.PI) * W * 0.08;
    var stack = t > 0.5 ? (i + 1) * 0.6 : (leaves.length - i) * 0.6;
    leaf.style.transform = "translateZ(" + (stack + lift).toFixed(2) + "px) rotateY(" + leaf.a.toFixed(2) + "deg)";
    leaf.firstChild.style.setProperty("--shade", Math.min(1, t * 2) * 0.7);
    leaf.lastChild.style.setProperty("--shade", Math.min(1, (1 - t) * 2) * 0.7);
  }
  function drawBook() {
    bookEl.style.transform = "translate(" + cam.dx + "px," + cam.dy + "px) translateX(" + cam.x + "px) scale(" + cam.s +
      ") rotateX(" + cam.rx + "deg) rotateY(" + cam.ry + "deg) rotateZ(" + cam.rz + "deg)";
  }
  function openX() { return 0; }   // open: the spine sits in the middle

  function label() {
    var shown = [];
    var left = at > 0 ? leaves[at - 1].lastChild : null, right = at < leaves.length ? leaves[at].firstChild : null;
    if (left && left.dataset.page) shown.push(+left.dataset.page);
    if (right && right.dataset.page) shown.push(+right.dataset.page);
    count.textContent = at === 0 ? "Cover" : !shown.length ? "The end" :
      (shown.length === 2 && shown[0] !== shown[1] ? "Pages " + shown[0] + "\u2013" + shown[1] : "Page " + shown[0]) + " of " + pages.length;
    prev.disabled = at <= 1;
    next.disabled = at >= leaves.length;
  }

  // ---- motion --------------------------------------------------------------
  // tween(obj, to, ms, ease, draw): moves obj's numbers to `to`; returns a handle
  // whose finish() jumps to the end, so a new action never waits on an old one.
  function tween(obj, to, ms, ease, draw, done) {
    var from = {}, k, start = performance.now(), raf, over = false;
    for (k in to) from[k] = obj[k];
    function step(now) {
      var p = calm || ms <= 0 ? 1 : Math.min(1, (now - start) / ms), e = ease(p);
      for (k in to) obj[k] = from[k] + (to[k] - from[k]) * e;
      draw();
      if (p < 1) raf = requestAnimationFrame(step); else end();
    }
    function end() { if (over) return; over = true; cancelAnimationFrame(raf); for (k in to) obj[k] = to[k]; draw(); if (done) done(); }
    raf = requestAnimationFrame(step);
    return {finish: end};
  }
  function settle() { if (busy) { var b = busy; busy = null; b.finish(); } }

  function turn(forward) {
    settle();
    var i = forward ? at : at - 1;
    if (forward ? at >= leaves.length : at <= 1) return;
    var leaf = leaves[i];
    at += forward ? 1 : -1;
    label(); hint.classList.add("gone");
    busy = tween(leaf, {a: forward ? -180 : 0}, 680, IN_OUT, function () { drawLeaf(leaf); }, function () { busy = null; });
  }

  function open() {
    if (opened) return;
    opened = true;
    build();
    hint.textContent = matchMedia("(pointer: coarse)").matches ? "swipe or tap a page to turn" : "click a page, drag it, or use the arrow keys";
    hint.classList.remove("gone");
    var r = closed.getBoundingClientRect();
    cam = {dx: r.left + r.width / 2 - innerWidth / 2, dy: r.top + r.height / 2 - innerHeight / 2,
           s: r.width / W, rx: 16, ry: -26, rz: 3, x: -W / 2};
    drawBook();
    dlg.showModal();
    closed.classList.add("away");
    label();
    busy = tween(cam, {dx: 0, dy: 0, s: 1, rx: 10, ry: 0, rz: 0}, 560, IN_OUT, drawBook, function () {
      var cover = leaves[0];
      at = 1; label();
      var both = {p: 0};
      busy = tween(both, {p: 1}, 820, IN_OUT, function () {
        cover.a = -180 * both.p; drawLeaf(cover);
        cam.x = -W / 2 + (openX() + W / 2) * both.p; drawBook();
      }, function () { busy = null; dlg.classList.add("is-open"); });
    });
  }

  function shut() {
    if (!opened) return;
    settle();
    opened = false;
    dlg.classList.remove("is-open");
    var flipped = leaves.slice(0, at), r = closed.getBoundingClientRect();
    var all = {p: 0}, starts = flipped.map(function (l) { return l.a; }), x0 = cam.x;
    busy = tween(all, {p: 1}, 640, IN_OUT, function () {
      flipped.forEach(function (l, j) { l.a = starts[j] * (1 - all.p); drawLeaf(l); });
      cam.x = x0 + (-W / 2 - x0) * all.p; drawBook();
    }, function () {
      at = 0;
      busy = tween(cam, {dx: r.left + r.width / 2 - innerWidth / 2, dy: r.top + r.height / 2 - innerHeight / 2,
                         s: r.width / W, rx: 16, ry: -26, rz: 3}, 480, IN_OUT, drawBook, function () {
        busy = null; dlg.close(); closed.classList.remove("away");
      });
    });
  }

  // ---- input ----------------------------------------------------------------
  [].forEach.call(document.querySelectorAll("[data-page]"), function (b) { b.addEventListener("click", open); });
  dlg.querySelector(".sk-shut").addEventListener("click", shut);
  prev.addEventListener("click", function () { turn(false); });
  next.addEventListener("click", function () { turn(true); });
  dlg.addEventListener("cancel", function (e) { e.preventDefault(); shut(); });   // Esc closes the book first
  dlg.addEventListener("keydown", function (e) {
    if (!dlg.classList.contains("is-open")) return;
    if (e.key === "ArrowRight") { e.preventDefault(); turn(true); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); turn(false); }
  });

  // drag: the first real move picks the leaf (left = forward, right = back),
  // the page follows the finger, and the release speed decides where it lands
  var drag = null;
  stage.addEventListener("pointerdown", function (e) {
    if (!dlg.classList.contains("is-open") || e.button > 0) return;
    drag = {x: e.clientX, y: e.clientY, leaf: null, samples: [[e.timeStamp, e.clientX]], id: e.pointerId};
  });
  stage.addEventListener("pointermove", function (e) {
    if (!drag || e.pointerId !== drag.id) return;
    var dx = e.clientX - drag.x;
    drag.samples.push([e.timeStamp, e.clientX]);
    if (drag.samples.length > 5) drag.samples.shift();
    if (!drag.leaf) {
      if (Math.abs(dx) < 8) return;
      drag.forward = dx < 0;
      if (drag.forward ? at >= leaves.length : at <= 1) { drag = null; return; }
      settle();
      drag.leaf = leaves[drag.forward ? at : at - 1];
      drag.a0 = drag.leaf.a;
      stage.setPointerCapture(e.pointerId);
      hint.classList.add("gone");
    }
    var span = W * 1.15;
    drag.leaf.a = Math.max(-180, Math.min(0, drag.a0 + dx / span * 180));
    drawLeaf(drag.leaf);
  });
  function release(e) {
    if (!drag || e.pointerId !== drag.id) return;
    var d = drag; drag = null;
    if (!d.leaf) { tap(e); return; }
    var s = d.samples, v = s.length > 1 ? (s[s.length - 1][1] - s[0][1]) / Math.max(1, s[s.length - 1][0] - s[0][0]) : 0;
    var done = d.forward ? (d.leaf.a < -90 || v < -0.45) && v < 0.45 : (d.leaf.a > -90 || v > 0.45) && v > -0.45;
    var target = d.forward === done ? -180 : 0;
    if (done) { at += d.forward ? 1 : -1; label(); }
    var leaf = d.leaf;
    busy = tween(leaf, {a: target}, Math.max(180, 560 * Math.abs(target - leaf.a) / 180), OUT,
                 function () { drawLeaf(leaf); }, function () { busy = null; });
  }
  stage.addEventListener("pointerup", release);
  stage.addEventListener("pointercancel", function (e) { if (drag && drag.leaf) release(e); else drag = null; });

  function tap(e) {
    var b = bookEl.getBoundingClientRect();
    var inside = e.clientY > b.top && e.clientY < b.bottom &&
      e.clientX > innerWidth / 2 - W && e.clientX < innerWidth / 2 + W;
    if (!inside) { shut(); return; }
    turn(e.clientX > innerWidth / 2);
  }

  addEventListener("resize", function () {
    if (!opened) return;
    settle(); size(); cam.x = openX(); drawBook(); leaves.forEach(drawLeaf);
  });

  // cubic-bezier(x1, y1, x2, y2) as a function of progress, like CSS
  function bezier(x1, y1, x2, y2) {
    function c(u, a, b) { return 3 * a * u * (1 - u) * (1 - u) + 3 * b * u * u * (1 - u) + u * u * u; }
    function dc(u, a, b) { return 3 * a * (1 - u) * (1 - u) + 6 * (b - a) * u * (1 - u) + 3 * (1 - b) * u * u; }
    return function (t) {
      if (t <= 0 || t >= 1) return t <= 0 ? 0 : 1;
      var lo = 0, hi = 1, u = t;
      for (var n = 0; n < 12; n++) {
        var x = c(u, x1, x2) - t;
        if (Math.abs(x) < 1e-5) break;
        if (x > 0) hi = u; else lo = u;
        var d = dc(u, x1, x2);
        u = Math.abs(d) > 1e-6 ? u - x / d : (lo + hi) / 2;
        if (u <= lo || u >= hi) u = (lo + hi) / 2;
      }
      return c(u, y1, y2);
    };
  }
})();
