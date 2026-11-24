// ShopImpact sound kit — every sound is synthesised live with the Web Audio
// API (no audio files). Wooden marimba tones for the till, a thermal-printer
// chatter for receipts, a soft pen scratch while the turtle draws.

const NOTE = (n) => 440 * Math.pow(2, (n - 69) / 12); // MIDI note -> Hz

class SoundKit {
  constructor() {
    this.ctx = null;
    this.master = null;
    this.enabled = true;
    this.volume = 0.6;
    this.penNode = null;
    this.unlocked = false; // set after the first click / key press
  }

  // Browsers only allow audio after a user gesture, so we start lazily.
  ensure() {
    if (!this.enabled || !this.unlocked) return null;
    if (!this.ctx) {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return null;
      this.ctx = new AC();
      this.master = this.ctx.createGain();
      this.master.gain.value = this.volume * 0.5;
      const comp = this.ctx.createDynamicsCompressor();
      comp.threshold.value = -18;
      this.master.connect(comp).connect(this.ctx.destination);
    }
    if (this.ctx.state === "suspended") this.ctx.resume();
    return this.ctx;
  }

  setEnabled(on) {
    this.enabled = on;
    if (!on) this.penStop();
  }

  setVolume(v) {
    this.volume = v;
    if (this.master) this.master.gain.setTargetAtTime(v * 0.5, this.ctx.currentTime, 0.05);
  }

  // A mallet-like tone: sine fundamental + a quiet bright partial.
  mallet(freq, when = 0, { gain = 0.35, decay = 0.7, bright = 0.25, type = "sine" } = {}) {
    const ctx = this.ensure();
    if (!ctx) return;
    const t = ctx.currentTime + when;
    const out = ctx.createGain();
    out.gain.setValueAtTime(0.0001, t);
    out.gain.exponentialRampToValueAtTime(gain, t + 0.006);
    out.gain.exponentialRampToValueAtTime(0.0001, t + decay);
    out.connect(this.master);

    const o1 = ctx.createOscillator();
    o1.type = type;
    o1.frequency.value = freq;
    o1.connect(out);

    const g2 = ctx.createGain();
    g2.gain.setValueAtTime(bright * gain, t);
    g2.gain.exponentialRampToValueAtTime(0.0001, t + decay * 0.25);
    const o2 = ctx.createOscillator();
    o2.frequency.value = freq * 3.98;
    o2.connect(g2).connect(this.master);

    o1.start(t); o2.start(t);
    o1.stop(t + decay + 0.05); o2.stop(t + decay + 0.05);
  }

  noise(duration, when = 0, { gain = 0.08, freq = 2400, q = 1.2, type = "bandpass" } = {}) {
    const ctx = this.ensure();
    if (!ctx) return;
    const t = ctx.currentTime + when;
    const len = Math.max(1, Math.floor(ctx.sampleRate * duration));
    const buffer = ctx.createBuffer(1, len, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / len);
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    const filter = ctx.createBiquadFilter();
    filter.type = type;
    filter.frequency.value = freq;
    filter.Q.value = q;
    const g = ctx.createGain();
    g.gain.value = gain;
    src.connect(filter).connect(g).connect(this.master);
    src.start(t);
  }

  // --- The vocabulary -----------------------------------------------------

  // "Tuck": a short wooden detent for every slider step. Every 10th step is a
  // slightly deeper, firmer click, like the notches on a real dial.
  tuck(strong = false) {
    const ctx = this.ensure();
    if (!ctx) return;
    const t = ctx.currentTime;
    if (this.lastTuck && t - this.lastTuck < 0.024) return; // fast drags: ~40 tucks/s max
    this.lastTuck = t;
    const base = strong ? 430 : 640 + Math.random() * 40;
    const o = ctx.createOscillator();
    o.type = "sine";
    o.frequency.setValueAtTime(base * 1.8, t);
    o.frequency.exponentialRampToValueAtTime(base * 0.5, t + 0.04);
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t);
    g.gain.exponentialRampToValueAtTime(strong ? 0.42 : 0.26, t + 0.002);
    g.gain.exponentialRampToValueAtTime(0.0001, t + (strong ? 0.07 : 0.045));
    o.connect(g).connect(this.master);
    o.start(t);
    o.stop(t + 0.09);
    this.noise(0.006, 0, { gain: strong ? 0.22 : 0.14, freq: 3400, q: 1.4 });
  }

  tick() { this.mallet(NOTE(96), 0, { gain: 0.05, decay: 0.06, bright: 0 }); }

  nav() { this.mallet(NOTE(84), 0, { gain: 0.07, decay: 0.12, bright: 0.1 }); }

  toggle(on) {
    this.mallet(NOTE(on ? 79 : 72), 0, { gain: 0.1, decay: 0.15 });
    this.mallet(NOTE(on ? 84 : 67), 0.07, { gain: 0.1, decay: 0.2 });
  }

  // The till key: brighter and more musical the lighter the purchase.
  ring(tier) {
    const chords = {
      low: [72, 76, 79, 84],
      medium: [67, 72, 76],
      high: [60, 64],
    };
    (chords[tier] || chords.medium).forEach((n, i) =>
      this.mallet(NOTE(n), i * 0.075, { gain: 0.26, decay: tier === "high" ? 0.9 : 0.75 }));
  }

  // Thermal printer: rapid filtered clicks plus a low motor hum.
  print(duration = 1.3) {
    const ctx = this.ensure();
    if (!ctx) return;
    const step = 0.032;
    for (let t = 0; t < duration; t += step) {
      this.noise(0.016, t, { gain: 0.05 + Math.random() * 0.02, freq: 2600 + Math.random() * 900, q: 2 });
    }
    const t0 = ctx.currentTime;
    const hum = ctx.createOscillator();
    hum.type = "sawtooth";
    hum.frequency.value = 92;
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 260;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(0.04, t0 + 0.05);
    g.gain.setValueAtTime(0.04, t0 + duration - 0.08);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + duration);
    hum.connect(lp).connect(g).connect(this.master);
    hum.start(t0);
    hum.stop(t0 + duration + 0.05);
    this.noise(0.05, duration, { gain: 0.12, freq: 1200, q: 0.8 }); // the tear
  }

  // Soft pen-on-paper scratch while the turtle draws.
  penStart() {
    const ctx = this.ensure();
    if (!ctx || this.penNode) return;
    const len = ctx.sampleRate * 2;
    const buffer = ctx.createBuffer(1, len, ctx.sampleRate);
    const data = buffer.getChannelData(0);
    let last = 0;
    for (let i = 0; i < len; i++) { last = last * 0.96 + (Math.random() * 2 - 1) * 0.04; data[i] = last * 6; }
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.loop = true;
    const bp = ctx.createBiquadFilter();
    bp.type = "bandpass";
    bp.frequency.value = 1700;
    bp.Q.value = 0.7;
    const g = ctx.createGain();
    g.gain.setValueAtTime(0.0001, ctx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.035, ctx.currentTime + 0.08);
    src.connect(bp).connect(g).connect(this.master);
    src.start();
    this.penNode = { src, g };
  }

  penStop() {
    if (!this.penNode || !this.ctx) return;
    const { src, g } = this.penNode;
    const t = this.ctx.currentTime;
    g.gain.cancelScheduledValues(t);
    g.gain.setTargetAtTime(0.0001, t, 0.05);
    src.stop(t + 0.3);
    this.penNode = null;
  }

  badge() {
    [72, 76, 79, 84, 88, 91].forEach((n, i) =>
      this.mallet(NOTE(n), i * 0.085, { gain: 0.2, decay: 1.1, bright: 0.35, type: "triangle" }));
    this.mallet(NOTE(96), 0.6, { gain: 0.08, decay: 1.6, bright: 0.6 });
  }

  swap() {
    this.noise(0.35, 0, { gain: 0.06, freq: 900, q: 0.6 });
    this.mallet(NOTE(76), 0.12, { gain: 0.2, decay: 0.5 });
    this.mallet(NOTE(83), 0.22, { gain: 0.2, decay: 0.7 });
  }

  remove() {
    this.mallet(NOTE(67), 0, { gain: 0.14, decay: 0.25 });
    this.mallet(NOTE(60), 0.08, { gain: 0.12, decay: 0.35 });
  }

  error() {
    this.mallet(NOTE(55), 0, { gain: 0.16, decay: 0.3, type: "triangle" });
    this.mallet(NOTE(54), 0.1, { gain: 0.12, decay: 0.3, type: "triangle" });
  }
}

export const sound = new SoundKit();
