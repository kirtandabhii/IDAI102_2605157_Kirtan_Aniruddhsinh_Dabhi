// ShopImpact browser runtime for the Streamlit app.
// Installed once per page (st.html with JavaScript enabled). Python decides
// *what* to show; this only animates it and plays sounds:
//   * SoundKit      — synthesised sounds (Web Audio, no files)
//   * playTurtle    — replays Python's recorded turtle strokes with a walking turtle
//   * printReceipt  — feeds a receipt out of the printer, then the turtle stamps it
//   * bridges       — "tuck" on every slider step, soft ticks on buttons
(function () {
  if (window.ShopImpact) return;
  const SI = (window.ShopImpact = {
    config: { sound: true, volume: 0.6, motion: "full", speed: 1 },
    played: new Set(),
  });
  const reduced = () => SI.config.motion === "reduced" || matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ------------------------------------------------------------------ sound
  const NOTE = (n) => 440 * Math.pow(2, (n - 69) / 12);
  const kit = {
    ctx: null, master: null, unlocked: false, pen: null, lastTuck: 0,
    ensure() {
      if (!SI.config.sound || !this.unlocked) return null;
      if (!this.ctx) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return null;
        this.ctx = new AC();
        this.master = this.ctx.createGain();
        const comp = this.ctx.createDynamicsCompressor();
        comp.threshold.value = -18;
        this.master.connect(comp).connect(this.ctx.destination);
      }
      this.master.gain.value = SI.config.volume * 0.5;
      if (this.ctx.state === "suspended") this.ctx.resume();
      return this.ctx;
    },
    mallet(freq, when = 0, { gain = 0.3, decay = 0.7, bright = 0.25, type = "sine" } = {}) {
      const ctx = this.ensure(); if (!ctx) return;
      const t = ctx.currentTime + when;
      const out = ctx.createGain();
      out.gain.setValueAtTime(0.0001, t);
      out.gain.exponentialRampToValueAtTime(gain, t + 0.006);
      out.gain.exponentialRampToValueAtTime(0.0001, t + decay);
      out.connect(this.master);
      const o1 = ctx.createOscillator(); o1.type = type; o1.frequency.value = freq; o1.connect(out);
      const g2 = ctx.createGain();
      g2.gain.setValueAtTime(bright * gain, t);
      g2.gain.exponentialRampToValueAtTime(0.0001, t + decay * 0.25);
      const o2 = ctx.createOscillator(); o2.frequency.value = freq * 3.98; o2.connect(g2).connect(this.master);
      o1.start(t); o2.start(t); o1.stop(t + decay + 0.05); o2.stop(t + decay + 0.05);
    },
    noise(duration, when = 0, { gain = 0.08, freq = 2400, q = 1.2, type = "bandpass" } = {}) {
      const ctx = this.ensure(); if (!ctx) return;
      const t = ctx.currentTime + when;
      const len = Math.max(1, Math.floor(ctx.sampleRate * duration));
      const buffer = ctx.createBuffer(1, len, ctx.sampleRate);
      const data = buffer.getChannelData(0);
      for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / len);
      const src = ctx.createBufferSource(); src.buffer = buffer;
      const f = ctx.createBiquadFilter(); f.type = type; f.frequency.value = freq; f.Q.value = q;
      const g = ctx.createGain(); g.gain.value = gain;
      src.connect(f).connect(g).connect(this.master); src.start(t);
    },
    // "Tuck": a wooden detent for every slider step; every 10th is deeper.
    tuck(strong = false) {
      const ctx = this.ensure(); if (!ctx) return;
      const t = ctx.currentTime;
      if (t - this.lastTuck < 0.024) return;
      this.lastTuck = t;
      const base = strong ? 430 : 640 + Math.random() * 40;
      const o = ctx.createOscillator(); o.type = "sine";
      o.frequency.setValueAtTime(base * 1.8, t);
      o.frequency.exponentialRampToValueAtTime(base * 0.5, t + 0.04);
      const g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(strong ? 0.42 : 0.26, t + 0.002);
      g.gain.exponentialRampToValueAtTime(0.0001, t + (strong ? 0.07 : 0.045));
      o.connect(g).connect(this.master); o.start(t); o.stop(t + 0.09);
      this.noise(0.006, 0, { gain: strong ? 0.22 : 0.14, freq: 3400, q: 1.4 });
      if (strong && navigator.vibrate) navigator.vibrate(6);
    },
    tick() { this.mallet(NOTE(90), 0, { gain: 0.06, decay: 0.09, bright: 0.05 }); },
    nav() { this.mallet(NOTE(84), 0, { gain: 0.07, decay: 0.12, bright: 0.1 }); },
    ring(tier) {
      const chords = { low: [72, 76, 79, 84], medium: [67, 72, 76], high: [60, 64] };
      (chords[tier] || chords.medium).forEach((n, i) =>
        this.mallet(NOTE(n), i * 0.075, { gain: 0.26, decay: tier === "high" ? 0.9 : 0.75 }));
    },
    print(duration = 1.3) {
      const ctx = this.ensure(); if (!ctx) return;
      for (let t = 0; t < duration; t += 0.032)
        this.noise(0.016, t, { gain: 0.05 + Math.random() * 0.02, freq: 2600 + Math.random() * 900, q: 2 });
      const t0 = ctx.currentTime;
      const hum = ctx.createOscillator(); hum.type = "sawtooth"; hum.frequency.value = 92;
      const lp = ctx.createBiquadFilter(); lp.type = "lowpass"; lp.frequency.value = 260;
      const g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, t0);
      g.gain.exponentialRampToValueAtTime(0.04, t0 + 0.05);
      g.gain.setValueAtTime(0.04, t0 + duration - 0.08);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
      hum.connect(lp).connect(g).connect(this.master); hum.start(t0); hum.stop(t0 + duration + 0.05);
      this.noise(0.05, duration, { gain: 0.12, freq: 1200, q: 0.8 });
    },
    penStart() {
      const ctx = this.ensure(); if (!ctx || this.pen) return;
      const len = ctx.sampleRate * 2;
      const buffer = ctx.createBuffer(1, len, ctx.sampleRate);
      const data = buffer.getChannelData(0);
      let last = 0;
      for (let i = 0; i < len; i++) { last = last * 0.96 + (Math.random() * 2 - 1) * 0.04; data[i] = last * 6; }
      const src = ctx.createBufferSource(); src.buffer = buffer; src.loop = true;
      const bp = ctx.createBiquadFilter(); bp.type = "bandpass"; bp.frequency.value = 1700; bp.Q.value = 0.7;
      const g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, ctx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.035, ctx.currentTime + 0.08);
      src.connect(bp).connect(g).connect(this.master); src.start();
      this.pen = { src, g };
    },
    penStop() {
      if (!this.pen || !this.ctx) return;
      const { src, g } = this.pen; const t = this.ctx.currentTime;
      g.gain.cancelScheduledValues(t); g.gain.setTargetAtTime(0.0001, t, 0.05); src.stop(t + 0.3);
      this.pen = null;
    },
    badge() {
      [72, 76, 79, 84, 88, 91].forEach((n, i) =>
        this.mallet(NOTE(n), i * 0.085, { gain: 0.2, decay: 1.1, bright: 0.35, type: "triangle" }));
      this.mallet(NOTE(96), 0.6, { gain: 0.08, decay: 1.6, bright: 0.6 });
    },
    swap() {
      this.noise(0.35, 0, { gain: 0.06, freq: 900, q: 0.6 });
      this.mallet(NOTE(76), 0.12, { gain: 0.2, decay: 0.5 });
      this.mallet(NOTE(83), 0.22, { gain: 0.2, decay: 0.7 });
    },
    remove() { this.mallet(NOTE(67), 0, { gain: 0.14, decay: 0.25 }); this.mallet(NOTE(60), 0.08, { gain: 0.12, decay: 0.35 }); },
    error() { this.mallet(NOTE(55), 0, { gain: 0.16, decay: 0.3, type: "triangle" }); this.mallet(NOTE(54), 0.1, { gain: 0.12, decay: 0.3, type: "triangle" }); },
  };
  SI.sound = kit;
  // Remember this browser's private ledger id, so a plain visit finds it again.
  setInterval(() => {
    try { if (SI.config.sid) localStorage.setItem("shopimpact.id", SI.config.sid); } catch (e) { /* private mode */ }
  }, 2000);

  const unlock = () => { kit.unlocked = true; kit.ensure(); };
  addEventListener("pointerdown", unlock, { capture: true });
  addEventListener("keydown", unlock, { capture: true });

  // ------------------------------------------------------------ turtle player
  const NS = "http://www.w3.org/2000/svg";
  const tokens = new WeakMap();
  function turtleGlyph(size) {
    const g = document.createElementNS(NS, "g");
    g.setAttribute("class", "t-cursor");
    g.innerHTML = `<g transform="scale(${size})">
      <ellipse cx="-0.05" cy="-0.72" rx="0.28" ry="0.2" fill="#2D5A40"/><ellipse cx="-0.05" cy="0.72" rx="0.28" ry="0.2" fill="#2D5A40"/>
      <ellipse cx="0.55" cy="-0.6" rx="0.22" ry="0.17" fill="#2D5A40"/><ellipse cx="0.55" cy="0.6" rx="0.22" ry="0.17" fill="#2D5A40"/>
      <path d="M-0.85 0 L-1.25 0.12 L-1.25 -0.12 Z" fill="#2D5A40"/><circle cx="1.12" cy="0" r="0.3" fill="#3F7D58"/>
      <ellipse cx="0.1" cy="0" rx="0.95" ry="0.72" fill="#4E8A57" stroke="#1E3B2F" stroke-width="0.09"/>
      <path d="M-0.5 0 H0.7 M0.1 -0.62 V0.62 M-0.35 -0.45 L0.55 0.45 M-0.35 0.45 L0.55 -0.45" stroke="#C8DDB7" stroke-width="0.07" fill="none"/></g>`;
    return g;
  }

  SI.showStatic = function (host, markup) {
    tokens.set(host, Symbol("static"));
    host.innerHTML = markup;
  };

  SI.playTurtle = function (host, markup, { maxMs = 4200, minMs = 900, withSound = true } = {}) {
    const token = Symbol("turtle");
    tokens.set(host, token);
    host.innerHTML = markup;
    const svg = host.querySelector("svg");
    if (!svg || reduced()) return Promise.resolve();
    const seq = [...svg.querySelectorAll("[data-seq]")];
    const fills = [...svg.querySelectorAll(".t-fill")];
    if (!seq.length) return Promise.resolve();
    const DOT_UNITS = 9;
    const items = seq.map((el) => {
      if (el.tagName.toLowerCase() === "path") {
        const len = Math.max(el.getTotalLength(), 0.01);
        el.style.strokeDasharray = `${len} ${len}`;
        el.style.strokeDashoffset = `${len}`;
        return { el, len, kind: "path", units: len };
      }
      el.style.transformBox = "fill-box"; el.style.transformOrigin = "center"; el.style.transform = "scale(0)";
      return { el, len: 0, kind: "dot", units: DOT_UNITS };
    });
    fills.forEach((f) => { f.style.opacity = "0"; f.style.transition = "opacity .35s ease"; });
    const totalUnits = items.reduce((s, it) => s + it.units, 0);
    const duration = Math.min(Math.max(totalUnits * 4.5, minMs), maxMs) / (SI.config.speed || 1);
    const msPerUnit = duration / totalUnits;
    const vb = svg.viewBox.baseVal;
    const cursor = turtleGlyph(Math.max(vb.width, vb.height) * 0.032);
    svg.appendChild(cursor);
    const fillAt = fills.map((f) => ({ el: f, at: Number(f.dataset.at || 0), shown: false }));
    const reveal = (done) => { for (const f of fillAt) if (!f.shown && done >= f.at) { f.el.style.opacity = "1"; f.shown = true; } };
    if (withSound) kit.penStart();
    return new Promise((resolve) => {
      let idx = 0, start = performance.now(), angle = 0;
      const finish = () => {
        items.forEach((it) => { if (it.kind === "path") it.el.style.strokeDashoffset = "0"; else it.el.style.transform = ""; });
        reveal(Infinity);
        cursor.style.transition = "opacity .3s"; cursor.style.opacity = "0";
        setTimeout(() => cursor.remove(), 350);
        kit.penStop(); resolve();
      };
      const frame = (now) => {
        if (tokens.get(host) !== token || !host.isConnected) { kit.penStop(); resolve(); return; }
        while (idx < items.length) {
          const it = items[idx];
          const span = it.units * msPerUnit;
          const p = Math.min((now - start) / span, 1);
          if (it.kind === "path") {
            it.el.style.strokeDashoffset = `${it.len * (1 - p)}`;
            const at = it.el.getPointAtLength(it.len * p);
            const back = it.el.getPointAtLength(Math.max(it.len * p - 1.5, 0));
            if (at.x !== back.x || at.y !== back.y) angle = Math.atan2(at.y - back.y, at.x - back.x) * 180 / Math.PI;
            cursor.setAttribute("transform", `translate(${at.x} ${at.y}) rotate(${angle})`);
          } else {
            it.el.style.transform = `scale(${p < 1 ? 0.4 + p * 0.8 : 1})`;
            cursor.setAttribute("transform", `translate(${it.el.getAttribute("cx")} ${it.el.getAttribute("cy")}) rotate(${angle})`);
          }
          if (p < 1) break;
          start += span; idx += 1; reveal(idx);
        }
        if (idx >= items.length) finish(); else requestAnimationFrame(frame);
      };
      requestAnimationFrame(frame);
    });
  };

  // ------------------------------------------------------------- receipt
  // Plays once per nonce: feed out of the printer, then the turtle stamps it.
  SI.printReceipt = async function (rootId, nonce, tier, stampSvg, fresh) {
    const root = document.getElementById(rootId);
    if (!root) return;
    const paper = root.querySelector(".receipt");
    const stamp = root.querySelector("[data-stamp]");
    const led = root.querySelector(".printer-led");
    const firstTime = fresh && !SI.played.has(nonce);
    SI.played.add(nonce);
    if (!firstTime || reduced()) {
      if (stamp && stampSvg) SI.showStatic(stamp, stampSvg);
      return;
    }
    kit.ring(tier);
    paper.classList.add("is-feeding");
    if (led) led.classList.add("is-on");
    kit.print(1.35);
    await new Promise((r) => setTimeout(r, 1400));
    paper.classList.remove("is-feeding");
    if (led) led.classList.remove("is-on");
    if (stamp && stampSvg) await SI.playTurtle(stamp, stampSvg, { maxMs: 2600 });
  };

  // One-off drawings (badge spotlight, monthly tree) keyed by a nonce.
  SI.draw = function (hostId, nonce, svg, opts = {}) {
    const host = document.getElementById(hostId);
    if (!host) return;
    if (SI.played.has(nonce) && !opts.always) { SI.showStatic(host, svg); return; }
    SI.played.add(nonce);
    if (opts.chime === "badge") kit.badge();
    SI.playTurtle(host, svg, opts);
  };

  // ------------------------------------------------------------- bridges
  // 1. Every Streamlit slider "tucks" as it passes each step (react-aria keeps
  //    aria-valuetext on its hidden range input up to date while dragging).
  const lastValue = new WeakMap();
  new MutationObserver((records) => {
    for (const r of records) {
      const el = r.target;
      if (el.tagName !== "INPUT" || el.type !== "range") continue;
      const text = el.getAttribute("aria-valuetext") || el.value;
      if (lastValue.get(el) === text) continue;
      const first = !lastValue.has(el);
      lastValue.set(el, text);
      if (first) continue;
      const holder = el.closest("[class*='st-key-']");
      const isPrice = holder && holder.className.includes("st-key-f_tag");
      // Step number: for the price tag, price ÷ currency step; otherwise value ÷ slider step.
      const n = isPrice
        ? Math.round(Number(String(text).replace(/[^0-9.]/g, "")) / (SI.config.priceStep || 1))
        : Math.round(Number(el.value) / (Number(el.step) || 1));
      kit.tuck(n % 10 === 0);
    }
  }).observe(document.body, { subtree: true, attributes: true, attributeFilter: ["aria-valuetext", "value"] });

  // 2. Brand logos inside Streamlit's brand dropdown (and in the field once picked).
  //    The dropdown is a real st.selectbox; we only add a logo beside each option.
  //    Python sends {brand name: logo URL}; logos are served from ./static/logos.
  SI.brandLogos = {};
  function decorateBrand() {
    const input = document.querySelector(".st-key-f_brand input[role='combobox']");
    if (!input) return;
    const host = input.parentElement;
    host.dataset.siLogoHost = "1";
    const picked = SI.brandLogos[input.value.trim()];
    if (picked) { host.style.setProperty("--si-logo", `url("${picked}")`); host.dataset.siLogo = "1"; }
    else { delete host.dataset.siLogo; }
    const id = input.getAttribute("aria-controls");
    const list = id && document.getElementById(id);
    if (!list) return;
    list.dataset.siBrand = "1";
    list.querySelectorAll("[role='option']").forEach((opt) => {
      const name = opt.textContent.trim();
      const url = SI.brandLogos[name];
      if (url) {
        if (opt.dataset.siFor !== name) { opt.style.setProperty("--si-logo", `url("${url}")`); opt.dataset.siFor = name; }
        opt.dataset.siLogo = "1";
      } else {
        delete opt.dataset.siLogo; delete opt.dataset.siFor;
      }
    });
  }
  SI.decorateBrand = decorateBrand;
  let pendingDecorate = false;
  new MutationObserver(() => {
    if (pendingDecorate) return;
    pendingDecorate = true;
    requestAnimationFrame(() => { pendingDecorate = false; decorateBrand(); });
  }).observe(document.body, { subtree: true, childList: true, characterData: true,
                              attributes: true, attributeFilter: ["value", "aria-expanded", "aria-controls"] });
  document.addEventListener("input", (e) => {
    if (e.target.closest && e.target.closest(".st-key-f_brand")) requestAnimationFrame(decorateBrand);
  }, true);

  // 3. Soft ticks on buttons, pills and toggles (navigation gets its own note).
  document.addEventListener("click", (e) => {
    const b = e.target.closest("button, [role='switch'], [role='option'], label[data-baseweb='checkbox']");
    if (!b) return;
    if (b.closest(".st-key-rail")) {
      kit.nav();
      // A new screen starts at the top.
      setTimeout(() => { window.scrollTo({ top: 0 }); document.querySelector("[data-testid='stMain']")?.scrollTo({ top: 0 }); }, 250);
    }
    else if (b.closest(".st-key-ring")) { /* the receipt plays its own chime */ }
    else if (b.closest("[class*='st-key-del_']")) kit.remove();
    else if (b.closest(".st-key-take_swap, [class*='st-key-confirm_swap']")) kit.swap();
    else kit.tick();
  }, true);
})();
