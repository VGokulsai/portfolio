/* Records: click a sleeve and it lifts out of the crate; its record drops onto
   the 3D turntable from above, lands with a small thud and a needle crackle,
   the arm swings over and it spins while notes drift up. Click it again to
   stop; click another record and the first lifts off before the new one drops.
   Real songs plug in later: each record will get its own player. */
(function () {
  var deck = document.querySelector(".deck");
  if (!deck) return;
  var disc = deck.querySelector(".disc"), led = deck.querySelector(".led"), notes = document.querySelector(".notes");
  var sheet = document.querySelector(".records"), now = document.querySelector(".now"), playing = null, timers = [], ctx = null, seen = true;
  var calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var NOTE = '<svg viewBox="0 0 24 24"><path d="M9 3v11.3A3.5 3.5 0 1 0 11 17V7h7V3z"/></svg>';

  function later(fn, ms) { timers.push(setTimeout(fn, calm ? 0 : ms)); }
  function clear() { timers.forEach(clearTimeout); timers = []; }

  function crackle() {
    try {
      ctx = ctx || new (window.AudioContext || window.webkitAudioContext)();
      var n = ctx.sampleRate * 0.9, buf = ctx.createBuffer(1, n, ctx.sampleRate), d = buf.getChannelData(0);
      for (var i = 0; i < n; i++) d[i] = Math.random() < 0.002 ? (Math.random() * 2 - 1) * 0.6 : (Math.random() * 2 - 1) * 0.015;
      var src = ctx.createBufferSource(), g = ctx.createGain();
      g.gain.setValueAtTime(0.5, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.9);
      src.buffer = buf; src.connect(g); g.connect(ctx.destination); src.start();
    } catch (e) { /* no sound is fine; the record still spins */ }
  }

  // one note every ~0.9 s from the record, only while it plays and is on screen
  function note() {
    if (!playing || calm) return;
    if (seen) {
      var n = document.createElement("span");
      n.className = "note"; n.innerHTML = NOTE;
      n.style.left = (36 + Math.random() * 46) + "%"; n.style.top = (24 + Math.random() * 18) + "%";
      n.style.setProperty("--dx", (Math.random() * 60 - 30).toFixed(0) + "px");
      n.addEventListener("animationend", function () { n.remove(); });
      notes.appendChild(n);
    }
    later(note, 700 + Math.random() * 500);
  }
  if (window.IntersectionObserver) new IntersectionObserver(function (es) { seen = es[0].isIntersecting; }).observe(deck);

  function idle() {
    sheet.classList.remove("playing");
    led.textContent = "33 rpm · off";
    now.innerHTML = "Pick a record from the crate.";
  }

  function drop(s) {
    disc.style.setProperty("--c", s.style.getPropertyValue("--c"));
    deck.classList.add("on");
    sheet.classList.add("playing");             // the staff's notes start hopping
    led.textContent = "33 rpm · on";
    now.innerHTML = '<span class="eq" aria-hidden="true"><i></i><i></i><i></i><i></i></span>Now spinning: <b>' +
      s.dataset.title + "</b>" + (s.dataset.artist ? " · " + s.dataset.artist : "");
    later(function () {                       // the record lands
      deck.classList.remove("thud"); void deck.offsetWidth; deck.classList.add("thud");
    }, 420);
    later(crackle, 1050);                     // the needle meets the groove
    later(note, 1300);
  }

  [].forEach.call(document.querySelectorAll(".sleeve"), function (s) {
    s.addEventListener("click", function () {
      clear();
      var was = playing;
      if (was) was.classList.remove("out");
      if (was === s) { playing = null; deck.classList.remove("on"); idle(); return; }
      playing = s;
      s.classList.add("out");
      if (was) { deck.classList.remove("on"); later(function () { drop(s); }, 420); }   // lift the old one off first
      else drop(s);
    });
  });
  idle();
})();
