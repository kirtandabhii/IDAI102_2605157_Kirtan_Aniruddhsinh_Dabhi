// Hand-built SVG charts. All numbers come pre-computed from the Python engine.

const NS = "http://www.w3.org/2000/svg";
const fmt1 = (n) => (Math.round(n * 10) / 10).toLocaleString(undefined, { maximumFractionDigits: 1 });

function niceMax(v) {
  if (v <= 0) return 10;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  const step = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].find((s) => n <= s) || 10;
  return step * p;
}

/** Cumulative CO2 curve for the month, with budget and projection. */
export function monthCurve(host, summary, { monthLabel = "", animate = true } = {}) {
  const width = Math.max(host.clientWidth, 280);
  const height = host.clientHeight || 260;
  const pad = { l: 40, r: 14, t: 16, b: 26 };
  const w = width - pad.l - pad.r;
  const h = height - pad.t - pad.b;
  const days = summary.days_in_month;
  const daily = summary.daily;
  const lastDay = summary.is_current ? summary.today : days;
  const maxVal = niceMax(Math.max(summary.budget * 1.08, summary.projected || 0, summary.co2) || 10);
  const x = (d) => pad.l + ((d - 1) / Math.max(days - 1, 1)) * w;
  const y = (v) => pad.t + h - (v / maxVal) * h;

  // Line points: day 0 starts at zero.
  const pts = [[pad.l, y(0)]];
  for (let i = 0; i < lastDay; i++) pts.push([x(daily[i].day), y(daily[i].cum)]);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
  const area = `${line} L${pts[pts.length - 1][0].toFixed(1)} ${y(0)} L${pad.l} ${y(0)} Z`;
  const yB = y(summary.budget);

  const ticks = [0, maxVal / 2, maxVal];
  const dayTicks = [1, 8, 15, 22, days];

  let svg = `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Running CO₂ total for ${monthLabel}: ${fmt1(summary.co2)} kilograms against a ${summary.budget} kilogram budget">
    <defs>
      <linearGradient id="cvGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="var(--accent)" stop-opacity=".22"/>
        <stop offset="1" stop-color="var(--accent)" stop-opacity="0"/>
      </linearGradient>
      <clipPath id="cvOver"><rect x="0" y="0" width="${width}" height="${Math.max(yB, 0)}"/></clipPath>
    </defs>`;
  for (const t of ticks) {
    svg += `<line class="cv-grid" x1="${pad.l}" x2="${width - pad.r}" y1="${y(t)}" y2="${y(t)}"/>`;
    svg += `<text class="cv-axis" x="${pad.l - 8}" y="${y(t) + 3}" text-anchor="end">${fmt1(t)}</text>`;
  }
  for (const d of dayTicks) {
    svg += `<text class="cv-axis" x="${x(d)}" y="${height - 6}" text-anchor="middle">${d}</text>`;
  }
  if (summary.is_current) {
    svg += `<line class="cv-today" x1="${x(lastDay)}" x2="${x(lastDay)}" y1="${pad.t}" y2="${y(0)}"/>`;
  }
  svg += `<line class="cv-budget" x1="${pad.l}" x2="${width - pad.r}" y1="${yB}" y2="${yB}"/>`;
  svg += `<text class="cv-budget-label" x="${width - pad.r}" y="${yB - 6}" text-anchor="end">budget ${fmt1(summary.budget)} kg</text>`;
  svg += `<path class="cv-area ${animate ? "cv-fade" : ""}" d="${area}"/>`;
  if (summary.is_current && lastDay < days && summary.count) {
    svg += `<path class="cv-proj ${animate ? "cv-fade" : ""}" d="M${x(lastDay)} ${y(summary.co2)} L${x(days)} ${y(summary.projected)}"/>`;
  }
  svg += `<path class="cv-line ${animate ? "cv-draw" : ""}" d="${line}"/>`;
  svg += `<path class="cv-line over ${animate ? "cv-draw" : ""}" d="${line}" clip-path="url(#cvOver)"/>`;
  daily.forEach((d) => {
    if (d.count && d.day <= lastDay) {
      svg += `<circle class="cv-dot ${animate ? "cv-fade" : ""}" cx="${x(d.day)}" cy="${y(d.cum)}" r="${Math.min(3 + d.count, 6)}"/>`;
    }
  });
  svg += `<line class="cv-guide" x1="0" x2="0" y1="${pad.t}" y2="${y(0)}"/><circle class="cv-hover-dot" r="5"/>`;
  svg += `<rect x="${pad.l}" y="${pad.t}" width="${w}" height="${h}" fill="transparent" class="cv-hit"/></svg>`;

  host.innerHTML = svg + `<div class="tooltip" role="presentation"></div>`;
  const root = host.querySelector("svg");
  root.querySelectorAll(".cv-draw").forEach((p) => p.style.setProperty("--len", Math.ceil(p.getTotalLength())));

  // Hover crosshair + tooltip.
  const guide = root.querySelector(".cv-guide");
  const dot = root.querySelector(".cv-hover-dot");
  const tip = host.querySelector(".tooltip");
  const hit = root.querySelector(".cv-hit");
  const move = (evt) => {
    const rect = root.getBoundingClientRect();
    const px = ((evt.clientX - rect.left) / rect.width) * width;
    const day = Math.min(Math.max(Math.round(((px - pad.l) / w) * (days - 1)) + 1, 1), lastDay || 1);
    const d = daily[day - 1];
    const cx = x(day), cy = y(d.cum);
    guide.setAttribute("x1", cx); guide.setAttribute("x2", cx);
    dot.setAttribute("cx", cx); dot.setAttribute("cy", cy);
    tip.style.left = `${(cx / width) * 100}%`;
    tip.style.top = `${(cy / height) * 100}%`;
    tip.innerHTML = `<div>${monthLabel.split(" ")[0]} ${day}</div>
      <div>${d.count ? `+<b>${fmt1(d.co2)}</b> kg · ${d.count} purchase${d.count > 1 ? "s" : ""}` : "No purchases"}</div>
      <div>Running total <b>${fmt1(d.cum)}</b> kg</div>`;
    host.classList.add("is-hover");
  };
  hit.addEventListener("pointermove", move);
  hit.addEventListener("pointerdown", move);
  hit.addEventListener("pointerleave", () => host.classList.remove("is-hover"));
}

/** Circular budget gauge. */
export function budgetRing(pct, label = "of budget", over = pct > 100) {
  const r = 40, c = 2 * Math.PI * r;
  const clamped = Math.min(Math.max(pct, 0), 100);
  const cls = over ? "over" : pct > 80 ? "warn" : "";
  return `<svg class="ring" viewBox="0 0 100 100" role="img" aria-label="${pct}% ${label}">
    <circle class="ring-track" cx="50" cy="50" r="${r}" fill="none" stroke-width="9"/>
    <circle class="ring-fill ${cls}" cx="50" cy="50" r="${r}" fill="none" stroke-width="9" stroke-linecap="round"
      stroke-dasharray="${c}" stroke-dashoffset="${c}" data-target="${c * (1 - clamped / 100)}" transform="rotate(-90 50 50)"/>
    <text class="ring-text" x="50" y="52" text-anchor="middle">${pct}%</text>
    <text class="ring-sub" x="50" y="64" text-anchor="middle">${label.toUpperCase()}</text>
  </svg>`;
}

/** Ease numbers up from their previous value. */
export function countUp(el, to, { decimals = 0, prefix = "", suffix = "", duration = 900 } = {}) {
  const from = Number(el.dataset.value || 0);
  el.dataset.value = to;
  const format = (v) => prefix + v.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix;
  if (document.documentElement.dataset.motion === "reduced" || matchMedia("(prefers-reduced-motion: reduce)").matches || from === to) {
    el.textContent = format(to);
    return;
  }
  const start = performance.now();
  const step = (now) => {
    const p = Math.min((now - start) / duration, 1);
    const e = 1 - Math.pow(1 - p, 3);
    el.textContent = format(from + (to - from) * e);
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
