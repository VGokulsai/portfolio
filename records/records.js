/* Records: click a sleeve in the crate and its record drops onto the turntable,
   the arm swings over and it spins; click it again to stop. When the needle
   lands there is a short vinyl crackle made in the browser (no audio file).
   Real songs plug in later: each record will get its own player. */
(function () {
  var deck = document.querySelector(".deck");
  if (!deck) return;
  var disc = deck.querySelector(".disc"), led = deck.querySelector(".led");
  var now = document.querySelector(".now"), playing = null, timer = 0, ctx = null;

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

  function stop() {
    if (playing) playing.classList.remove("out");
    playing = null;
    deck.classList.remove("on");
    led.textContent = "33 rpm · off";
    now.innerHTML = "Pick a record from the crate.";
  }

  [].forEach.call(document.querySelectorAll(".sleeve"), function (s) {
    s.addEventListener("click", function () {
      if (playing === s) { stop(); return; }
      if (playing) playing.classList.remove("out");
      playing = s;
      s.classList.add("out");
      deck.classList.remove("on");
      disc.style.setProperty("--c", s.style.getPropertyValue("--c"));
      void deck.offsetWidth;                      // restart the drop for the new record
      deck.classList.add("on");
      led.textContent = "33 rpm · on";
      now.innerHTML = "Now spinning: <b>" + s.dataset.title + "</b>" + (s.dataset.artist ? " · " + s.dataset.artist : "");
      clearTimeout(timer);
      timer = setTimeout(crackle, 850);           // when the needle lands
    });
  });
  stop();
})();
