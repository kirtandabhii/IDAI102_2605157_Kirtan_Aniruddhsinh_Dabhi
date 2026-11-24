// Replays an SvgTurtle drawing stroke by stroke, with a little turtle walking
// the path — the same order Python's turtle recorded the moves in.

const SVG_NS = "http://www.w3.org/2000/svg";
const tokens = new WeakMap();

function turtleGlyph(size) {
  // A tiny turtle pointing along +x, centred on (0,0).
  const g = document.createElementNS(SVG_NS, "g");
  g.setAttribute("class", "t-cursor");
  g.innerHTML = `
    <g transform="scale(${size})">
      <ellipse cx="-0.05" cy="-0.72" rx="0.28" ry="0.2" fill="#2D5A40"/>
      <ellipse cx="-0.05" cy="0.72" rx="0.28" ry="0.2" fill="#2D5A40"/>
      <ellipse cx="0.55" cy="-0.6" rx="0.22" ry="0.17" fill="#2D5A40"/>
      <ellipse cx="0.55" cy="0.6" rx="0.22" ry="0.17" fill="#2D5A40"/>
      <path d="M-0.85 0 L-1.25 0.12 L-1.25 -0.12 Z" fill="#2D5A40"/>
      <circle cx="1.12" cy="0" r="0.3" fill="#3F7D58"/>
      <ellipse cx="0.1" cy="0" rx="0.95" ry="0.72" fill="#4E8A57" stroke="#1E3B2F" stroke-width="0.09"/>
      <path d="M-0.5 0 H0.7 M0.1 -0.62 V0.62 M-0.35 -0.45 L0.55 0.45 M-0.35 0.45 L0.55 -0.45" stroke="#C8DDB7" stroke-width="0.07" fill="none"/>
    </g>`;
  return g;
}

/**
 * Insert `markup` into `host` and animate it.
 * Options: speed (1 = normal), reduced (skip animation), sound (object with
 * penStart/penStop), maxMs (cap on total duration).
 */
export function playTurtle(host, markup, { speed = 1, reduced = false, sound = null, maxMs = 4200, minMs = 900 } = {}) {
  const token = Symbol("turtle");
  tokens.set(host, token);
  host.innerHTML = markup;
  const svg = host.querySelector("svg");
  if (!svg) return Promise.resolve();

  const seq = [...svg.querySelectorAll("[data-seq]")];
  const fills = [...svg.querySelectorAll(".t-fill")];
  if (reduced || !seq.length || !host.isConnected || host.offsetParent === null) {
    return Promise.resolve();
  }

  // Measure strokes and hide everything.
  const DOT_UNITS = 9;
  const items = seq.map((el) => {
    if (el.tagName.toLowerCase() === "path") {
      const len = Math.max(el.getTotalLength(), 0.01);
      el.style.strokeDasharray = `${len} ${len}`;
      el.style.strokeDashoffset = `${len}`;
      return { el, len, kind: "path", units: len };
    }
    el.style.transform = "scale(0)";
    return { el, len: 0, kind: "dot", units: DOT_UNITS };
  });
  fills.forEach((f) => { f.style.opacity = "0"; });

  const totalUnits = items.reduce((s, it) => s + it.units, 0);
  const duration = Math.min(Math.max(totalUnits * 4.5, minMs), maxMs) / speed;
  const msPerUnit = duration / totalUnits;

  // Turtle cursor sized to the drawing.
  const vb = svg.viewBox.baseVal;
  const cursor = turtleGlyph(Math.max(vb.width, vb.height) * 0.032);
  svg.appendChild(cursor);

  // Fill reveal thresholds.
  const fillAt = fills.map((f) => ({ el: f, at: Number(f.dataset.at || 0), shown: false }));
  const revealFills = (done) => {
    for (const f of fillAt) if (!f.shown && done >= f.at) { f.el.style.opacity = "1"; f.shown = true; }
  };

  sound?.penStart?.();
  return new Promise((resolve) => {
    let idx = 0;
    let itemStart = performance.now();
    let lastAngle = 0;

    const finish = () => {
      items.forEach((it) => {
        if (it.kind === "path") it.el.style.strokeDashoffset = "0";
        else it.el.style.transform = "";
      });
      revealFills(Infinity);
      cursor.style.opacity = "0";
      setTimeout(() => cursor.remove(), 350);
      sound?.penStop?.();
      resolve();
    };

    const frame = (now) => {
      if (tokens.get(host) !== token || !host.isConnected) { sound?.penStop?.(); resolve(); return; }
      while (idx < items.length) {
        const it = items[idx];
        const span = it.units * msPerUnit;
        const p = Math.min((now - itemStart) / span, 1);
        if (it.kind === "path") {
          it.el.style.strokeDashoffset = `${it.len * (1 - p)}`;
          const at = it.el.getPointAtLength(it.len * p);
          const back = it.el.getPointAtLength(Math.max(it.len * p - 1.5, 0));
          if (at.x !== back.x || at.y !== back.y) lastAngle = Math.atan2(at.y - back.y, at.x - back.x) * 180 / Math.PI;
          cursor.setAttribute("transform", `translate(${at.x} ${at.y}) rotate(${lastAngle})`);
        } else {
          it.el.style.transform = `scale(${p < 1 ? 0.4 + p * 0.8 : 1})`;
          cursor.setAttribute("transform", `translate(${it.el.getAttribute("cx")} ${it.el.getAttribute("cy")}) rotate(${lastAngle})`);
        }
        if (p < 1) break;
        itemStart += span;
        idx += 1;
        revealFills(idx);
      }
      if (idx >= items.length) finish();
      else requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  });
}

/** Show a drawing instantly (no animation). */
export function showStatic(host, markup) {
  tokens.set(host, Symbol("static"));
  host.innerHTML = markup;
}
