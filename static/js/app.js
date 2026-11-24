// ShopImpact front end. Python computes every number; this file renders it,
// animates it and talks back to the API.

import { sound } from "./sound.js";
import { playTurtle, showStatic } from "./turtle-player.js";
import { monthCurve, budgetRing, countUp } from "./charts.js";

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
const kg = (n, d = 1) => Number(n).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
const int = (n) => Math.round(n).toLocaleString();
const icon = (id, cls = "i") => `<svg class="${cls}" aria-hidden="true"><use href="#${id}"/></svg>`;
const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const todayISO = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 10); };
const reducedMotion = () => document.documentElement.dataset.motion === "reduced" || matchMedia("(prefers-reduced-motion: reduce)").matches;

const PREF_KEY = "shopimpact.prefs";
const prefs = Object.assign({ theme: null, text: "regular", sound: true, volume: 0.6, motion: "full", speed: 1 },
  JSON.parse(localStorage.getItem(PREF_KEY) || "{}"));
const savePrefs = () => localStorage.setItem(PREF_KEY, JSON.stringify(prefs));

const VIEWS = {
  overview: { eyebrow: "Overview", title: null },
  ledger: { eyebrow: "Every purchase this month", title: "Your ledger" },
  swaps: { eyebrow: "Lighter choices", title: "Greener swaps" },
  badges: { eyebrow: "Rewards", title: "Badges" },
  garden: { eyebrow: "Turtle graphics", title: "Your garden" },
  settings: { eyebrow: "Preferences", title: "Settings" },
};
const VIEW_ORDER = Object.keys(VIEWS);

// App state
const S = {
  catalog: null,
  types: {},          // id -> type
  groups: {},         // id -> group
  state: null,        // latest /api/state payload
  month: null,
  view: "overview",
  typeId: null,
  swappedFrom: null,
  estimateSeq: 0,
  tips: [],
  tipIndex: 0,
  quoteIndex: 0,
  catalogGroup: "all",
  ledger: { q: "", tiers: new Set(["low", "medium", "high"]), sort: "date" },
  badgeQueue: [],
  treeKey: null,
  sprigSvg: null,
  brandByName: {},    // lowercase name -> brand
  typeBrands: {},     // type id -> lowercase brand names (for the type search)
  brandResults: [],
  brandActive: -1,
  showAllBrands: false,
};

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------
async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    credentials: "same-origin",
  });
  let data;
  try { data = await res.json(); } catch { throw new Error("The server sent an unexpected reply. Try again in a moment."); }
  if (!res.ok || data.ok === false) throw new Error(data.error || "Something went wrong. Try again.");
  return data;
}

function money(n, { decimals } = {}) {
  const code = S.state?.currency?.code || "GBP";
  const d = decimals ?? (Math.abs(n) >= 1000 ? 0 : 2);
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency: code, minimumFractionDigits: d, maximumFractionDigits: d }).format(n);
  } catch {
    return `${S.state?.currency?.symbol || "£"}${Number(n).toFixed(d)}`;
  }
}

/** A short symbol for a currency: our own if we have one, else the browser's (₩, ฿, R$…). */
function currencySymbol(code, fallback) {
  if (fallback && fallback.trim() !== code) return fallback.trim();
  try {
    const part = new Intl.NumberFormat("en", { style: "currency", currency: code, currencyDisplay: "narrowSymbol" })
      .formatToParts(1).find((p) => p.type === "currency");
    return part ? part.value : code;
  } catch {
    return code;
  }
}

/** "Indian rupee", "Swiss franc"… from the browser, falling back to the code. */
function currencyName(code) {
  try { return new Intl.DisplayNames(["en"], { type: "currency" }).of(code) || code; } catch { return code; }
}

// ---------------------------------------------------------------------------
// Toasts
// ---------------------------------------------------------------------------
function toast(message, { action, onAction, timeout = 4200 } = {}) {
  const el = document.createElement("div");
  el.className = "toast";
  el.innerHTML = `<span>${esc(message)}</span>${action ? `<button type="button">${esc(action)}</button>` : ""}`;
  const close = () => { el.classList.add("out"); setTimeout(() => el.remove(), 300); };
  if (action) el.querySelector("button").addEventListener("click", () => { onAction?.(); close(); });
  $("#toasts").appendChild(el);
  setTimeout(close, timeout);
}

// ---------------------------------------------------------------------------
// Preferences: theme, text size, sound, motion
// ---------------------------------------------------------------------------
function applyPrefs() {
  const root = document.documentElement;
  const theme = prefs.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  root.dataset.theme = theme;
  root.dataset.text = prefs.text;
  if (prefs.motion === "reduced") root.dataset.motion = "reduced"; else delete root.dataset.motion;
  sound.setEnabled(prefs.sound);
  sound.setVolume(prefs.volume);

  const st = $("#sound-toggle");
  st.setAttribute("aria-pressed", String(prefs.sound));
  st.title = prefs.sound ? "Sound on (M)" : "Sound off (M)";
  st.querySelector("use").setAttribute("href", prefs.sound ? "#i-sound-on" : "#i-sound-off");
  const tt = $("#theme-toggle");
  tt.querySelector("use").setAttribute("href", theme === "light" ? "#i-moon" : "#i-sun");
  tt.title = theme === "light" ? "Switch to night canopy" : "Switch to daylight";
  $('meta[name="theme-color"]').content = theme === "light" ? "#1E3B2F" : "#0F1713";
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------
function greeting() {
  const h = new Date().getHours();
  const hello = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  const name = S.state?.settings?.name;
  return name ? `${hello}, ${name}` : hello;
}

function showView(view, { focus = false, silent = false } = {}) {
  if (!VIEWS[view]) view = "overview";
  const changed = S.view !== view;
  S.view = view;
  $("#app").dataset.view = view;
  $$("[data-view-panel]").forEach((p) => { p.hidden = p.dataset.viewPanel !== view; });
  $$(".nav-btn").forEach((b) => b.toggleAttribute("aria-current", b.dataset.nav === view));
  $$(".nav-btn[aria-current]").forEach((b) => b.setAttribute("aria-current", "page"));
  renderTitle();
  if (location.hash.slice(1) !== view) history.replaceState(null, "", `#${view}`);
  if (changed && !silent) sound.nav();
  if (changed) $("#main").scrollTop = 0;
  if (view === "garden") renderTree();
  if (view === "overview") requestAnimationFrame(renderCurve);
  if (focus) $("#main").focus({ preventScroll: true });
}

function renderTitle() {
  const v = VIEWS[S.view];
  $("#view-eyebrow").textContent = S.view === "overview" ? `Overview · ${S.state?.summary?.label || ""}` : v.eyebrow;
  $("#view-title").textContent = v.title || greeting();
  document.title = `${v.title || "Overview"} — ShopImpact`;
}

async function loadMonth(key) {
  try {
    S.state = await api(`/api/state?month=${key}`);
    S.month = key;
    renderAll();
  } catch (err) {
    toast(err.message);
  }
}

function renderMonthSwitch() {
  const s = S.state;
  $("#month-label").textContent = s.summary.label;
  const current = todayISO().slice(0, 7);
  $("#month-next").disabled = !s.can_next;
  $("#month-prev").disabled = !s.can_prev;
  const href = `/api/export.csv?month=${S.month}`;
  $("#export-btn").href = href;
  $("#export-btn-2").href = href;
}

function shiftMonth(key, delta) {
  const [y, m] = key.split("-").map(Number);
  const idx = y * 12 + (m - 1) + delta;
  return `${String(Math.floor(idx / 12)).padStart(4, "0")}-${String((idx % 12) + 1).padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Product picker (custom listbox)
// ---------------------------------------------------------------------------
function typeOptionHTML(t) {
  return `<li class="picker-opt" role="option" id="opt-${t.id}" data-id="${t.id}" aria-selected="${t.id === S.typeId}">
    <span>${esc(t.name)}<small>${t.multiplier.toFixed(2)} kg CO₂e per £1</small></span>
    <span class="pill pill-${t.tier}">${t.tier}</span>
  </li>`;
}

function renderPicker(query = "") {
  const q = query.trim().toLowerCase();
  const list = $("#picker-list");
  let html = "";
  for (const g of S.catalog.groups) {
    const items = S.catalog.types.filter((t) => t.group === g.id &&
      (!q || t.name.toLowerCase().includes(q) || g.name.toLowerCase().includes(q) || (S.typeBrands[t.id] || []).some((b) => b.includes(q))));
    if (!items.length) continue;
    html += `<li class="picker-group eyebrow" role="presentation">${icon("g-" + g.icon)}${esc(g.name)}</li>`;
    html += items.map(typeOptionHTML).join("");
  }
  list.innerHTML = html || `<li class="picker-empty" role="presentation">Nothing matches “${esc(query)}”. Try a broader word like “food”.</li>`;
  const opts = $$(".picker-opt", list);
  const selected = opts.findIndex((o) => o.dataset.id === S.typeId);
  setActiveOption(selected >= 0 && !q ? selected : 0);
}

function setActiveOption(i) {
  const opts = $$("#picker-list .picker-opt");
  opts.forEach((o) => o.classList.remove("is-active"));
  if (!opts.length) return;
  const idx = (i + opts.length) % opts.length;
  opts[idx].classList.add("is-active");
  opts[idx].scrollIntoView({ block: "nearest" });
  $("#picker-search").setAttribute("aria-activedescendant", opts[idx].id);
  S.pickerActive = idx;
}

function openPicker() {
  $("#picker").hidden = false;
  $("#type-btn").setAttribute("aria-expanded", "true");
  $("#picker-search").value = "";
  renderPicker("");
  $("#picker-search").focus();
  sound.tick();
}

function closePicker(refocus = true) {
  if ($("#picker").hidden) return;
  $("#picker").hidden = true;
  $("#type-btn").setAttribute("aria-expanded", "false");
  if (refocus) $("#type-btn").focus();
}

function selectType(id, { fromSwap = false } = {}) {
  S.typeId = id;
  if (!fromSwap) S.swappedFrom = null;
  const t = S.types[id];
  const btn = $("#type-btn");
  btn.classList.toggle("is-empty", !t);
  $("#type-btn-name").textContent = t ? t.name : "Choose what you bought";
  $("#type-btn-icon").innerHTML = t ? icon("g-" + S.groups[t.group].icon) : "";
  if (!$("#brand-pop").hidden) renderBrandPop();
  requestEstimate();
}

// ---------------------------------------------------------------------------
// Brand picker: logo + name, 450+ real brands and shops
// ---------------------------------------------------------------------------
const brandOf = (name) => S.brandByName[(name || "").trim().toLowerCase()] || null;

function logoImg(src, cls = "blogo") {
  return src ? `<img class="${cls}" src="${esc(src)}" alt="" loading="lazy" decoding="async">` : "";
}

/** Greener brands (with logos when we know them) for a product type. */
function greenerFor(typeId, limit = 4) {
  const t = S.types[typeId];
  const names = S.catalog.brands.filter((b) => b.greener && b.types.includes(typeId)).map((b) => b.name);
  return [...names, ...(t?.ideas || [])].slice(0, limit);
}

function brandResults(query) {
  const q = query.trim().toLowerCase();
  const all = S.catalog.brands;
  const sections = [];
  if (!q) {
    const used = [...new Set((S.state?.purchases || []).map((p) => brandOf(p.brand)).filter(Boolean))].slice(0, 6);
    if (S.typeId) {
      const forType = all.filter((b) => b.types.includes(S.typeId));
      sections.push(["Greener picks", forType.filter((b) => b.greener)]);
      sections.push(["Also sells this", forType.filter((b) => !b.greener)]);
    }
    sections.push(["Used before", used]);
    if (!S.typeId) sections.push(["Greener brands & shops", all.filter((b) => b.greener).sort((a, b) => a.name.localeCompare(b.name))]);
  } else {
    const hits = all.filter((b) => b.name.toLowerCase().includes(q));
    const rank = (b) => (b.name.toLowerCase().startsWith(q) ? 0 : 1) - (S.typeId && b.types.includes(S.typeId) ? 0.5 : 0);
    hits.sort((a, b) => rank(a) - rank(b) || a.name.localeCompare(b.name));
    sections.push(["", hits]);
  }
  const seen = new Set();
  const out = [];
  for (const [title, list] of sections) {
    const fresh = list.filter((b) => !seen.has(b.name));
    if (!fresh.length) continue;
    fresh.forEach((b) => seen.add(b.name));
    out.push({ title, items: fresh.slice(0, 40) });
  }
  return out;
}

function renderBrandPop() {
  const q = $("#brand").value;
  const sections = brandResults(q);
  S.brandResults = sections.flatMap((sec) => sec.items);
  let i = 0;
  const html = sections.map((sec) =>
    (sec.title ? `<li class="brand-sec eyebrow" role="presentation">${esc(sec.title)}</li>` : "") +
    sec.items.map((b) => `<li class="brand-opt" role="option" id="bopt-${i}" data-i="${i++}" aria-selected="false">
        ${logoImg(b.logo)}<span>${esc(b.name)}</span></li>`).join("")).join("");
  $("#brand-options").innerHTML = html ||
    `<li class="picker-empty" role="presentation">No brand called “${esc(q)}” yet — press Enter to use it anyway.</li>`;
  $("#brand-pop-foot").textContent = q ? "" : `Type to search ${S.catalog.brands.length} brands and shops`;
  const exact = S.brandResults.findIndex((b) => b.name.toLowerCase() === q.trim().toLowerCase());
  setActiveBrand(exact);
}

function setActiveBrand(i) {
  const opts = $$("#brand-options .brand-opt");
  opts.forEach((o) => { o.classList.remove("is-active"); o.setAttribute("aria-selected", "false"); });
  S.brandActive = -1;
  if (!opts.length || i < 0) { $("#brand").removeAttribute("aria-activedescendant"); return; }
  const idx = (i + opts.length) % opts.length;
  opts[idx].classList.add("is-active");
  opts[idx].setAttribute("aria-selected", "true");
  opts[idx].scrollIntoView({ block: "nearest" });
  $("#brand").setAttribute("aria-activedescendant", opts[idx].id);
  S.brandActive = idx;
}

function openBrandPop() {
  if (!S.catalog) return;
  $("#brand-pop").hidden = false;
  $("#brand").setAttribute("aria-expanded", "true");
  renderBrandPop();
}

function closeBrandPop() {
  $("#brand-pop").hidden = true;
  $("#brand").setAttribute("aria-expanded", "false");
  $("#brand").removeAttribute("aria-activedescendant");
}

function chooseBrand(brand) {
  $("#brand").value = brand.name;
  closeBrandPop();
  updateBrandLogo();
  // No product type yet? Start from the brand's main category.
  if (!S.typeId && brand.types.length) selectType(brand.types[0]);
  else requestEstimate();
  sound.tick();
  $("#price").focus();
}

function updateBrandLogo() {
  const b = brandOf($("#brand").value);
  const box = $(".brand-box");
  box.classList.toggle("has-logo", !!b);
  const holder = $("#brand-logo");
  if (b && holder.dataset.src !== b.logo) {
    holder.innerHTML = logoImg(b.logo, "");
    holder.dataset.src = b.logo;
  }
}

// ---------------------------------------------------------------------------
// Live estimate
// ---------------------------------------------------------------------------
const requestEstimate = debounce(async () => {
  const seq = ++S.estimateSeq;
  const price = parseFloat($("#price").value);
  const box = $("#estimate");
  if (!S.typeId) {
    box.innerHTML = `<p class="est-empty">Pick a product type and price — the CO₂ estimate updates as you type.</p>`;
    return;
  }
  try {
    const est = await api("/api/estimate", { method: "POST", body: { product_type: S.typeId, price: isNaN(price) ? 0 : price, brand: $("#brand").value, swapped_from: S.swappedFrom } });
    if (seq !== S.estimateSeq) return; // a newer request is on its way
    renderEstimate(est, isNaN(price) || price <= 0);
  } catch (err) {
    box.innerHTML = `<p class="est-empty">${esc(err.message)}</p>`;
  }
}, 140);

function renderEstimate(est, noPrice) {
  const box = $("#estimate");
  const t = S.types[S.typeId];
  if (noPrice) {
    box.innerHTML = `<div class="est-co2"><strong>${t.multiplier.toFixed(2)}</strong><span>kg CO₂e for every £1</span></div>
      <span class="pill pill-${est.tier}">${est.tier} impact</span>
      <span class="est-feel">Add a price to see this purchase's footprint.</span>`;
    return;
  }
  const e = est.equivalents;
  let right = "";
  if (S.swappedFrom && est.swapped_from_name) {
    right = `<span class="est-good">${icon("i-leaf")}Swapped from ${esc(est.swapped_from_name.toLowerCase())} — saves ${kg(est.swapped_saving)} kg</span>`;
  } else if (est.swap && est.swap.saving > 0) {
    const logos = est.swap.brands.map(brandOf).filter(Boolean).slice(0, 3)
      .map((b) => logoImg(b.logo, "blogo xs")).join("");
    right = `<button type="button" class="est-swap" id="est-swap" data-to="${est.swap.to}">
      ${icon("i-swaps")}<span>Try <b>${esc(est.swap.to_name.toLowerCase())}</b><br><em>−${kg(est.swap.saving)} kg · ${est.swap.saving_pct}% lighter</em></span>
      ${logos ? `<span class="est-logos">${logos}</span>` : ""}</button>`;
  } else if (est.tier === "low") {
    right = `<span class="est-good">${icon("i-leaf")}Already one of the lightest choices</span>`;
  }
  const brandNote = est.ethical_brand ? ` · <b>greener brand</b>` : "";
  box.innerHTML = `<div class="est-co2"><strong class="num">${kg(est.co2, 2)}</strong><span>kg CO₂e</span></div>
    <span class="pill pill-${est.tier}">${est.tier} impact</span>
    <span class="est-feel">≈ <b>${kg(e.car_km)} km</b> by car · <b>${int(e.phone_charges)}</b> phone charges${brandNote}</span>
    ${right}`;
  $("#est-swap")?.addEventListener("click", () => takeSwapInForm(est.swap));
}

function takeSwapInForm(swap) {
  const from = S.typeId;
  selectType(swap.to, { fromSwap: true });
  S.swappedFrom = from;
  if (swap.brands?.length && !$("#brand").value) $("#brand").placeholder = `e.g. ${swap.brands.slice(0, 2).join(", ")}`;
  sound.swap();
  requestEstimate();
}

// ---------------------------------------------------------------------------
// Ring it up: save purchase -> print receipt -> turtle stamp -> badges
// ---------------------------------------------------------------------------
function formError(msg) {
  const el = $("#form-error");
  el.textContent = msg;
  el.hidden = !msg;
  if (msg) {
    const till = $("#till");
    till.classList.remove("shake");
    void till.offsetWidth;
    till.classList.add("shake");
    sound.error();
  }
}

async function ringUp(evt) {
  evt.preventDefault();
  const price = parseFloat($("#price").value);
  if (!S.typeId) { formError("Choose a product type first."); $("#type-btn").focus(); return; }
  if (isNaN(price) || price <= 0) { formError("Enter a price above zero, for example 24.99."); $("#price").focus(); return; }
  formError("");
  const btn = $("#ring-btn");
  btn.disabled = true;
  btn.classList.add("is-pressed");
  try {
    const res = await api("/api/purchases", {
      method: "POST",
      body: {
        product_type: S.typeId, price, brand: $("#brand").value, date: $("#date").value || todayISO(),
        note: $("#note").value, swapped_from: S.swappedFrom,
      },
    });
    sound.ring(res.purchase.tier);
    S.state = res.state;
    S.month = res.state.month;
    renderAll();
    // Reset the form for the next purchase.
    $("#price").value = "";
    $("#price-slider").value = 0;
    S.lastPriceStep = 0;
    updateTagBubble();
    $("#brand").value = "";
    $("#brand").placeholder = "Search 450+ brands";
    updateBrandLogo();
    $("#note").value = "";
    selectType(null);
    S.badgeQueue.push(...res.new_badges);
    await printReceipt(res.purchase, res.reward, res.tip, true);
    nextBadge();
  } catch (err) {
    formError(err.message);
  } finally {
    btn.disabled = false;
    btn.classList.remove("is-pressed");
  }
}

function barcodeVars(id) {
  const n = String(id * 7919 + 1234);
  return `--b1:${1 + (n[0] % 3)}px;--b2:${4 + (n[1] % 3)}px;--b3:${6 + (n[2] % 3)}px;--b4:${10 + (n[3] % 4)}px`;
}

function receiptHTML(p, reward, tip, { fresh }) {
  const when = fresh
    ? new Date().toLocaleString(undefined, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" })
    : new Date(p.date + "T12:00").toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
  let d = 0;
  const L = (html, cls = "") => `<div class="rc-line ${cls}" style="--d:${d++}">${html}</div>`;
  const e = p.equivalents;
  return `
    ${L(`<strong>ShopImpact</strong>conscious till · no. ${String(p.id).padStart(4, "0")}`, "rc-head")}
    ${L(`<span>${esc(when)}</span>`, "rc-row rc-muted")}
    <hr class="rc-rule">
    ${L(esc(p.note || p.type_name), "rc-item")}
    ${p.note ? L(esc(p.type_name), "rc-muted") : ""}
    ${L(`<span class="rc-brand">${p.brand_info ? logoImg(p.brand_info.logo) : ""}<span>${esc(p.brand || "Unbranded")}</span></span><span>${money(p.display_price)}</span>`, "rc-row")}
    <hr class="rc-rule">
    ${L(`<span>CO₂e</span><span>${kg(p.co2, 2)} kg</span>`, "rc-dots rc-big")}
    ${L(`<span>Impact</span><span>${p.tier.toUpperCase()}</span>`, "rc-dots")}
    ${L(`<span>Feels like</span><span>${kg(e.car_km)} km by car</span>`, "rc-dots")}
    ${p.swap_saved ? L(`<span>Swap saved</span><span>${kg(p.swap_saved, 2)} kg</span>`, "rc-dots") : ""}
    <div class="rc-stamp" data-stamp></div>
    ${L(esc(reward?.message || "Logged."), "rc-msg")}
    ${p.swap && p.swap.saving > 0 ? L(`Lighter next time: <b>${esc(p.swap.to_name)}</b> would be ${kg(p.swap.co2, 2)} kg (−${p.swap.saving_pct}%).`, "rc-swap") : ""}
    ${tip ? `<hr class="rc-rule">${L(`TIP · ${esc(tip)}`, "rc-muted")}` : ""}
    <div class="rc-barcode rc-line" style="--d:${d++};${barcodeVars(p.id)}"></div>
    ${L("thank you for shopping mindfully", "rc-foot rc-muted")}`;
}

function welcomeReceiptHTML() {
  return `
    <div class="rc-head"><strong>ShopImpact</strong>conscious till · ready</div>
    <hr class="rc-rule">
    <div class="rc-item">Your first receipt prints here.</div>
    <div class="rc-muted">Ring up a purchase and a turtle will stamp it with a leaf, a footprint or a badge.</div>
    <div class="rc-stamp" data-stamp></div>
    <div class="rc-dots"><span>Light buy</span><span>leaf sprig</span></div>
    <div class="rc-dots"><span>Medium buy</span><span>light steps</span></div>
    <div class="rc-dots"><span>Heavy buy</span><span>deep footprint</span></div>
    <div class="rc-barcode" style="${barcodeVars(42)}"></div>
    <div class="rc-foot rc-muted">press N to start</div>`;
}

async function printReceipt(p, reward, tip, fresh) {
  const well = $("#receipt-well");
  const old = well.querySelector(".receipt");
  if (old) {
    old.classList.add("is-leaving");
    setTimeout(() => old.remove(), 520);
  }
  const r = document.createElement("article");
  r.className = "receipt";
  r.setAttribute("aria-label", "Receipt");
  r.innerHTML = p ? receiptHTML(p, reward, tip, { fresh }) : welcomeReceiptHTML();
  well.prepend(r);
  const stamp = r.querySelector("[data-stamp]");

  if (fresh && !reducedMotion()) {
    r.classList.add("is-feeding");
    $("#printer-led").classList.add("is-on");
    sound.print(1.35);
    await new Promise((res) => setTimeout(res, 1400));
    r.classList.remove("is-feeding");
    $("#printer-led").classList.remove("is-on");
  }
  if (reward?.svg) {
    if (fresh) await playTurtle(stamp, reward.svg, { speed: prefs.speed, reduced: reducedMotion(), sound, maxMs: 2600 });
    else showStatic(stamp, reward.svg);
  }
}

// ---------------------------------------------------------------------------
// Overview rendering
// ---------------------------------------------------------------------------
function renderKPIs() {
  const s = S.state.summary;
  const left = s.budget_left;
  const delta = s.vs_prev_pct == null ? "" :
    `<span class="delta ${s.vs_prev_pct <= 0 ? "down" : "up"}">${s.vs_prev_pct <= 0 ? "▼" : "▲"} ${Math.abs(s.vs_prev_pct)}%</span> vs last month`;
  const g = s.grade;
  const e = s.equivalents;
  $("#kpis").innerHTML = `
    <article class="kpi">
      <div class="kpi-main">
        <div>
          <p class="kpi-label">Footprint this month</p>
          <p class="kpi-value"><span data-count="${s.co2}" data-dec="1">0</span><small>kg CO₂e</small></p>
          <p class="kpi-foot">${left >= 0 ? `<b>${kg(left)} kg</b> left of ${int(s.budget)}` : `<b>${kg(-left)} kg</b> over budget`}${s.is_current && s.count ? ` · on track for ${int(s.projected)}` : ""}</p>
        </div>
        ${budgetRing(s.budget_pct, "of budget", s.budget_left < 0)}
      </div>
    </article>
    <article class="kpi">
      <p class="kpi-label">Spent</p>
      <p class="kpi-value" data-money="${s.spend}">${money(0)}</p>
      <div class="bar" title="${s.spend_pct}% of spending budget"><i style="--w:${Math.min(s.spend_pct, 100)}%"></i></div>
      <p class="kpi-foot"><b>${s.count}</b> purchase${s.count === 1 ? "" : "s"} · ${s.spend_pct}% of ${money(s.spend_budget, { decimals: 0 })}</p>
    </article>
    <article class="kpi">
      <p class="kpi-label">Eco score</p>
      <p class="kpi-value"><span class="grade grade-${s.score == null ? "none" : g.letter}">${g.letter}</span><span data-count="${s.score ?? 0}" data-dec="0">0</span><small>/ 100</small></p>
      <p class="kpi-foot"><b>${esc(g.label)}</b>${delta ? ` · ${delta}` : ""}</p>
    </article>
    <article class="kpi">
      <p class="kpi-label">Feels like driving</p>
      <p class="kpi-value"><span data-count="${e.car_km}" data-dec="0">0</span><small>km</small></p>
      <div class="feels">
        <span><b>${int(e.phone_charges)}</b> phone charges</span>
        <span><b>${int(e.tree_days)}</b> days of a tree's work</span>
      </div>
    </article>`;
  $$("#kpis [data-count]").forEach((el) => countUp(el, Number(el.dataset.count), { decimals: Number(el.dataset.dec) }));
  const m = $("#kpis [data-money]");
  const target = Number(m.dataset.money);
  const start = performance.now();
  const step = (now) => {
    const p = Math.min((now - start) / 900, 1);
    m.textContent = money(target * (1 - Math.pow(1 - p, 3)));
    if (p < 1 && !reducedMotion()) requestAnimationFrame(step); else m.textContent = money(target);
  };
  requestAnimationFrame(step);
  requestAnimationFrame(() => requestAnimationFrame(() => {
    $$("#kpis .ring-fill").forEach((c) => { c.style.strokeDashoffset = c.dataset.target; });
    $$("#kpis .bar > i").forEach((b) => { b.style.width = b.style.getPropertyValue("--w"); });
  }));
}

function renderCurve() {
  const host = $("#curve");
  if (!S.state || host.offsetParent === null) return;
  const s = S.state.summary;
  if (!S.state.total_count) {
    host.style.height = "auto";
    host.innerHTML = `<div class="empty">
      <div class="empty-art paper" data-empty-art></div>
      <h3>Your month is a blank receipt</h3>
      <p>Ring up something you bought — or load a sample month of 15 everyday purchases to see the dashboard come alive.</p>
      <div class="empty-actions">
        <button class="btn btn-primary" type="button" data-action="focus-till">Ring up a purchase</button>
        <button class="btn" type="button" data-action="demo">Load a sample month</button>
      </div></div>`;
    if (S.sprigSvg) showStatic($("[data-empty-art]", host), S.sprigSvg);
    return;
  }
  host.style.height = "";
  $("#curve-sub").textContent = s.count
    ? `${kg(s.co2)} kg so far against a ${int(s.budget)} kg budget`
    : `No purchases in ${s.label} yet`;
  $(".lg-proj-wrap").hidden = !(s.is_current && s.count);
  monthCurve(host, s, { monthLabel: s.label, animate: !reducedMotion() });
}

function renderGroups() {
  const s = S.state.summary;
  const strip = $("#tier-strip");
  const spend = s.spend || 1;
  strip.innerHTML = ["low", "medium", "high"].map((t) =>
    `<i class="ts-${t}" style="width:${(100 * s.tiers[t].spend) / spend}%" title="${t}: ${money(s.tiers[t].spend)}"></i>`).join("");
  strip.title = "Share of spending by impact tier";
  if (!s.groups.length) {
    $("#groups").innerHTML = `<li class="empty"><p>Categories appear once you log a purchase.</p></li>`;
    return;
  }
  const max = Math.max(...s.groups.map((g) => g.co2), 0.01);
  $("#groups").innerHTML = s.groups.map((g) => `
    <li class="group-row">
      <span class="g-icon">${icon("g-" + g.icon)}</span>
      <span class="g-name">${esc(g.name)}</span>
      <span class="g-val">${kg(g.co2)} kg · ${Math.round(g.share * 100)}%</span>
      <span class="g-bar"><i style="--w:${(100 * g.co2) / max}%;background:var(--${g.tier})"></i></span>
    </li>`).join("");
  requestAnimationFrame(() => requestAnimationFrame(() =>
    $$("#groups .g-bar i").forEach((b) => { b.style.width = b.style.getPropertyValue("--w"); })));
}

function renderRecent() {
  const items = S.state.purchases.slice(0, 6);
  $("#recent").innerHTML = items.length ? items.map((p) => `
    <li>
      <span class="tdot tdot-${p.tier}" title="${p.tier} impact"></span>
      <div class="r-main">
        <div class="r-name">${esc(p.note || p.type_name)}</div>
        <div class="r-sub r-name-row">${p.brand_info ? logoImg(p.brand_info.logo, "blogo xs") : ""}<span>${esc(p.brand || "Unbranded")} · ${money(p.display_price)}</span></div>
      </div>
      <div class="r-co2">${kg(p.co2)} kg<small>${new Date(p.date + "T12:00").toLocaleDateString(undefined, { day: "numeric", month: "short" })}</small></div>
    </li>`).join("") : `<li class="empty"><p>Nothing logged in ${esc(S.state.summary.label)} yet.</p></li>`;
}

function renderShelf() {
  const badges = S.state.badges;
  $("#shelf").innerHTML = badges.map((b) => `
    <button class="shelf-item ${b.earned ? "" : "locked"}" type="button" data-badge="${b.id}"
      title="${esc(b.name)}${b.earned ? " — earned" : ` — ${Math.round(b.progress * 100)}%`}">${S.catalog.badge_art[b.id]}</button>`).join("");
  const next = badges.filter((b) => !b.earned).sort((a, b) => b.progress - a.progress)[0];
  $("#shelf-next").innerHTML = next
    ? `Next up: <b>${esc(next.name)}</b> — ${esc(next.hint)}`
    : `Every badge earned this month. Remarkable.`;
  const earned = badges.filter((b) => b.earned).length;
  const count = $("#nav-badge-count");
  count.hidden = !earned;
  count.textContent = earned;
}

// ---------------------------------------------------------------------------
// Ledger
// ---------------------------------------------------------------------------
function renderLedger() {
  const { q, tiers, sort } = S.ledger;
  const term = q.trim().toLowerCase();
  let rows = S.state.purchases.filter((p) => tiers.has(p.tier) &&
    (!term || [p.type_name, p.brand, p.note, p.group_name].some((v) => (v || "").toLowerCase().includes(term))));
  if (sort === "co2") rows = [...rows].sort((a, b) => b.co2 - a.co2);
  if (sort === "price") rows = [...rows].sort((a, b) => b.display_price - a.display_price);

  const totalCo2 = rows.reduce((s, p) => s + p.co2, 0);
  const totalSpend = rows.reduce((s, p) => s + p.display_price, 0);
  $("#ledger-totals").innerHTML = `<span>Showing <b>${rows.length}</b> of ${S.state.purchases.length}</span>
    <span>Spend <b>${money(totalSpend)}</b></span><span>Footprint <b>${kg(totalCo2)} kg</b></span>
    ${S.state.summary.swapped_saving ? `<span>Saved by swaps <b>${kg(S.state.summary.swapped_saving)} kg</b></span>` : ""}`;

  const maxCo2 = Math.max(...S.state.purchases.map((p) => p.co2), 0.01);
  const ledger = $("#ledger");
  if (!rows.length) {
    ledger.innerHTML = `<div class="empty"><h3>${S.state.purchases.length ? "No purchases match" : "Nothing in the ledger yet"}</h3>
      <p>${S.state.purchases.length ? "Try clearing the search or switching the impact filters back on." : `Purchases you ring up in ${esc(S.state.summary.label)} appear here.`}</p>
      ${S.state.purchases.length ? "" : `<div class="empty-actions"><button class="btn btn-primary" data-action="focus-till" type="button">Ring up a purchase</button></div>`}</div>`;
    return;
  }
  ledger.innerHTML = `
    <div class="lg-row lg-head" role="row">
      <span role="columnheader">Date</span><span role="columnheader">Item</span><span role="columnheader" class="lg-brand">Brand</span>
      <span role="columnheader" class="lg-price">Price</span><span role="columnheader" class="lg-co2">CO₂e</span>
      <span role="columnheader" class="lg-tier">Impact</span><span role="columnheader" class="sr">Actions</span>
    </div>` + rows.map((p) => {
    const d = new Date(p.date + "T12:00");
    return `<div class="lg-row" role="row" data-id="${p.id}">
      <span class="lg-date" role="cell"><b>${d.getDate()}</b>${d.toLocaleDateString(undefined, { weekday: "short" })}</span>
      <span class="lg-item" role="cell"><span class="g-icon">${icon("g-" + p.icon)}</span>
        <div><div class="r-name">${esc(p.note || p.type_name)}</div>
        <div class="r-sub">${p.note ? esc(p.type_name) : esc(p.group_name)}${p.swapped_from ? ` · <span class="swapped-tag">swapped from ${esc(p.swapped_from_name?.toLowerCase())}</span>` : ""}</div></div></span>
      <span class="lg-brand" role="cell">${p.brand_info ? logoImg(p.brand_info.logo, "blogo sm") : ""}<span>${esc(p.brand || "—")}</span>${p.ethical_brand ? `<span class="eth" title="On the greener brands list">${icon("i-leaf")}</span>` : ""}</span>
      <span class="lg-price" role="cell">${money(p.display_price)}</span>
      <span class="lg-co2" role="cell">${kg(p.co2, 2)} kg<span class="minibar"><i style="width:${(100 * p.co2) / maxCo2}%;--c:var(--${p.tier})"></i></span></span>
      <span class="lg-tier" role="cell"><span class="pill pill-${p.tier}">${p.tier}</span></span>
      <span class="lg-actions" role="cell">
        ${p.swap && p.swap.saving > 0 ? `<button class="mini-btn swap" type="button" data-swap="${p.id}">${icon("i-swaps")}Swap</button>` : ""}
        <button class="mini-btn del" type="button" data-delete="${p.id}" aria-label="Delete ${esc(p.note || p.type_name)}">${icon("i-trash")}</button>
      </span>
    </div>`;
  }).join("");
}

async function deletePurchase(id) {
  const row = $(`.lg-row[data-id="${id}"]`);
  row?.classList.add("is-removing");
  sound.remove();
  try {
    const res = await api(`/api/purchases/${id}`, { method: "DELETE" });
    await new Promise((r) => setTimeout(r, reducedMotion() ? 0 : 280));
    S.state = res.state;
    renderAll();
    const p = res.deleted;
    toast(`Deleted ${S.types[p.product_type]?.name.toLowerCase() || "purchase"}.`, {
      action: "Undo",
      onAction: async () => {
        try {
          const back = await api("/api/purchases/restore", { method: "POST", body: p });
          S.state = back.state;
          renderAll();
          sound.tick();
        } catch (err) { toast(err.message); }
      },
    });
  } catch (err) {
    row?.classList.remove("is-removing");
    toast(err.message);
  }
}

// ---------------------------------------------------------------------------
// Swap sheet
// ---------------------------------------------------------------------------
function openSwap(id) {
  const p = S.state.purchases.find((x) => x.id === Number(id));
  if (!p || !p.swap) return;
  S.swapTarget = p;
  $("#swap-title").textContent = p.note || p.type_name;
  $("#swap-compare").innerHTML = `
    <div class="sc-box"><span>Now</span><b>${esc(p.type_name)}</b><strong>${kg(p.co2, 2)} kg</strong></div>
    <span class="sc-arrow">${icon("i-arrow")}</span>
    <div class="sc-box after"><span>Greener</span><b>${esc(p.swap.to_name)}</b><strong>${kg(p.swap.co2, 2)} kg</strong></div>`;
  $("#swap-why").innerHTML = `${esc(p.swap.why)} <span class="swap-saving">Saves ${kg(p.swap.saving, 2)} kg (${p.swap.saving_pct}%).</span>`;
  $("#swap-brand").value = "";
  $("#swap-brand-picks").innerHTML = p.swap.brands.map((name) => {
    const b = brandOf(name);
    return `<button type="button" class="pick-chip" data-pick="${esc(name)}" aria-pressed="false">${b ? logoImg(b.logo) : ""}${esc(name)}</button>`;
  }).join("");
  $("#swap-sheet").returnValue = "";
  $("#swap-sheet").showModal();
  sound.tick();
}

async function confirmSwap() {
  const p = S.swapTarget;
  if (!p) return;
  try {
    const res = await api(`/api/purchases/${p.id}/swap`, { method: "POST", body: { to: p.swap.to, brand: $("#swap-brand").value } });
    S.state = res.state;
    renderAll();
    sound.swap();
    toast(`Swapped to ${res.purchase.type_name.toLowerCase()} — ${kg(res.purchase.swap_saved || 0)} kg lighter.`);
    S.badgeQueue.push(...res.new_badges);
    nextBadge();
  } catch (err) {
    toast(err.message);
  }
}

// ---------------------------------------------------------------------------
// Swaps view
// ---------------------------------------------------------------------------
function renderWhatIf() {
  const slider = $("#whatif");
  const pct = Number(slider.value);
  paintSlider(slider);
  $("#whatif-pct").textContent = `${pct}%`;
  const s = S.state.summary;
  const candidates = S.state.purchases.filter((p) => p.swap && p.tier !== "low");
  // Every number here is worked out in Python (engine.monthly_summary -> whatif).
  const row = s.whatif.find((w) => w.pct === pct) || s.whatif[0];
  const { saved, after, score } = row;
  const max = Math.max(s.co2, 1);
  $("#whatif-out").innerHTML = `
    <div class="wi-stat good"><span>You'd save</span><b>${kg(saved)} kg</b></div>
    <div class="wi-stat"><span>New monthly total</span><b>${kg(after)} kg</b></div>
    <div class="wi-stat"><span>New eco score</span><b>${score ?? "–"}</b></div>
    <div class="wi-compare">
      <span>Now · ${kg(s.co2)} kg</span><div class="wi-bar before"><i style="width:${(100 * s.co2) / max}%"></i></div>
      <span>After swapping ${pct}% · ${kg(after)} kg</span><div class="wi-bar after"><i style="width:${(100 * after) / max}%"></i></div>
    </div>
    ${!candidates.length ? `<p class="hint" style="grid-column:1/-1">No medium or high-impact purchases this month — nothing left to swap.</p>` : ""}`;
}

function renderTopSwaps() {
  const list = S.state.summary.top_swaps;
  $("#top-swaps").innerHTML = list.length ? list.map((t) => `
    <li class="ts-item">
      <p><b>${esc(t.type_name)}</b>${t.brand ? ` · ${esc(t.brand)}` : ""}<br>→ ${esc(t.to_name)} <small>−${kg(t.saving)} kg</small></p>
      <button class="mini-btn swap" type="button" data-swap="${t.id}">${icon("i-swaps")}Swap</button>
    </li>`).join("") : `<li class="hint">Log some purchases and the biggest wins show up here.</li>`;
}

function renderCatalog() {
  const chips = [{ id: "all", name: "All", icon: null }, ...S.catalog.groups];
  $("#group-chips").innerHTML = chips.map((g) =>
    `<button class="chip-btn" role="tab" type="button" data-group="${g.id}" aria-selected="${S.catalogGroup === g.id}">
      ${g.icon ? icon("g-" + g.icon) : ""}${esc(g.name)}</button>`).join("");
  const maxM = Math.max(...S.catalog.types.map((t) => t.multiplier));
  const types = S.catalog.types
    .filter((t) => S.catalogGroup === "all" || t.group === S.catalogGroup)
    .sort((a, b) => b.multiplier - a.multiplier);
  $("#catalog").innerHTML = types.map((t) => `
    <article class="card pt-card">
      <div class="pt-top"><h3>${esc(t.name)}</h3><span class="pill pill-${t.tier}">${t.tier}</span></div>
      <div class="pt-meter">
        <div class="pt-meter-row"><span>This choice</span><b>${t.multiplier.toFixed(2)} kg / £1</b></div>
        <div class="pt-track"><i style="width:${(100 * t.multiplier) / maxM}%;background:var(--${t.tier})"></i></div>
        ${t.swap_to ? `<div class="pt-meter-row"><span>Greener swap</span><b>${t.swap_multiplier.toFixed(2)} kg / £1</b></div>
        <div class="pt-track"><i style="width:${(100 * t.swap_multiplier) / maxM}%;background:var(--low)"></i></div>` : ""}
      </div>
      ${t.swap_to ? `<div class="pt-swap">${icon("i-arrow")}<span>Swap to <b>${esc(t.swap_name)}</b> · ${Math.round(100 * (1 - t.swap_multiplier / t.multiplier))}% lighter</span></div>
        <p class="pt-why">${esc(t.swap_why)}</p>` : `<p class="pt-good">${icon("i-leaf")}Already a light choice.</p>`}
      <div class="brands">${greenerFor(t.swap_to || t.id).map((name) => {
        const b = brandOf(name);
        return `<span class="brand-chip">${b ? logoImg(b.logo) : ""}${esc(name)}</span>`;
      }).join("")}</div>
    </article>`).join("");
}

// ---------------------------------------------------------------------------
// Badges
// ---------------------------------------------------------------------------
function renderBadges() {
  const badges = S.state.badges;
  const earned = badges.filter((b) => b.earned).length;
  $("#badges-intro").innerHTML = `You've earned <b>${earned} of ${badges.length}</b> badges in ${esc(S.state.summary.label)}. Badges are judged month by month, so every month is a fresh start. Tap a badge to watch the turtle draw it.`;
  $("#badges").innerHTML = badges.map((b) => `
    <button class="card badge-card ${b.earned ? "" : "locked"}" type="button" data-badge="${b.id}">
      <div class="badge-art">${S.catalog.badge_art[b.id]}</div>
      <h3>${esc(b.name)}${b.earned ? `<span class="earned-tag">Earned</span>` : ""}</h3>
      <p>${esc(b.blurb)}</p>
      <div class="bar"><i style="--w:${b.progress * 100}%"></i></div>
      <span class="badge-hint">${b.earned ? "Unlocked this month." : esc(b.hint)}</span>
    </button>`).join("");
  requestAnimationFrame(() => requestAnimationFrame(() =>
    $$("#badges .bar > i").forEach((i) => { i.style.width = i.style.getPropertyValue("--w"); })));
}

function spotlightBadge(id, { unlocked = false } = {}) {
  const b = S.state.badges.find((x) => x.id === id) || S.badgeQueue.find((x) => x.id === id);
  if (!b) return;
  $("#badge-eyebrow").textContent = unlocked ? "Badge unlocked" : b.earned ? "Earned this month" : `Locked · ${Math.round(b.progress * 100)}% there`;
  $("#badge-title").textContent = b.name;
  $("#badge-blurb").textContent = b.earned || unlocked ? b.blurb : `${b.blurb} ${b.hint}`;
  const sheet = $("#badge-sheet");
  sheet.showModal();
  if (unlocked) sound.badge(); else sound.tick();
  playTurtle($("#badge-stage"), S.catalog.badge_art[id], { speed: prefs.speed, reduced: reducedMotion(), sound, maxMs: 2800, minMs: 1600 });
}

function nextBadge() {
  if ($("#badge-sheet").open || !S.badgeQueue.length) return;
  const b = S.badgeQueue.shift();
  spotlightBadge(b.id, { unlocked: true });
}

// ---------------------------------------------------------------------------
// Garden
// ---------------------------------------------------------------------------
async function renderTree(force = false) {
  const s = S.state.summary;
  const key = `${S.month}:${s.count}:${s.score}:${s.tiers.high.count}`;
  const stage = $("#tree-stage");
  $("#tree-stats").innerHTML = `
    <div><b>${s.score ?? "–"}</b><span>eco score</span></div>
    <div><b>${s.tiers.low.count}</b><span>light buys</span></div>
    <div><b>${s.tiers.high.count}</b><span>heavy buys</span></div>`;
  if (S.treeKey === key && !force) return;
  S.treeKey = key;
  try {
    const res = await api(`/api/drawing/tree?month=${S.month}`);
    S.treeSvg = res.svg;
    playTurtle(stage, res.svg, { speed: prefs.speed, reduced: reducedMotion(), sound, maxMs: 6500, minMs: 2200 });
  } catch (err) {
    stage.innerHTML = `<p class="hint">${esc(err.message)}</p>`;
  }
}

function renderHistory() {
  const rows = S.state.history;
  const max = Math.max(...rows.map((r) => r.co2), 1);
  $("#history").innerHTML = rows.map((r) => `
    <div class="h-col ${r.month === S.month ? "is-current" : ""}" title="${r.month}: ${kg(r.co2)} kg from ${r.count} purchases">
      <span class="h-val">${r.co2 ? int(r.co2) : "–"}</span>
      <div class="h-track"><i style="--h:${(100 * r.co2) / max}%"></i></div>
      <span class="h-label">${esc(r.label)}</span>
    </div>`).join("");
  requestAnimationFrame(() => requestAnimationFrame(() =>
    $$("#history .h-track i").forEach((i) => { i.style.height = i.style.getPropertyValue("--h"); })));
}

function showQuote(step = 0) {
  const quotes = S.catalog.quotes;
  S.quoteIndex = (S.quoteIndex + step + quotes.length) % quotes.length;
  const q = quotes[S.quoteIndex];
  const el = $("#quote-text");
  el.style.opacity = 0;
  setTimeout(() => {
    el.textContent = q.text;
    $("#quote-author").textContent = `— ${q.author}`;
    el.style.opacity = 1;
  }, step ? 200 : 0);
}

function showTip(step = 1) {
  S.tipIndex = (S.tipIndex + step + S.tips.length) % S.tips.length;
  const el = $("#tip-text");
  el.style.opacity = 0;
  setTimeout(() => { el.textContent = S.tips[S.tipIndex]; el.style.opacity = 1; }, 180);
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------
function paintSlider(el) {
  const min = Number(el.min), max = Number(el.max);
  el.style.setProperty("--p", `${((Number(el.value) - min) / (max - min)) * 100}%`);
}

function renderSettings() {
  const st = S.state.settings;
  if (document.activeElement !== $("#set-name")) $("#set-name").value = st.name || "";
  renderMoneyPickers();
  const co2 = $("#set-co2"), spend = $("#set-spend");
  configureSpendSlider();
  if (document.activeElement !== co2) co2.value = st.co2_budget;
  if (document.activeElement !== spend) spend.value = st.spend_budget;
  $("#set-co2-out").textContent = `${co2.value} kg`;
  $("#set-spend-out").textContent = money(Number(spend.value), { decimals: 0 });
  const theme = prefs.theme || document.documentElement.dataset.theme;
  $$("#set-theme button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.value === theme)));
  $$("#set-text button").forEach((b) => b.setAttribute("aria-checked", String(b.dataset.value === prefs.text)));
  $("#set-sound").checked = prefs.sound;
  $("#set-volume").value = Math.round(prefs.volume * 100);
  $("#set-volume-out").textContent = `${Math.round(prefs.volume * 100)}%`;
  $("#set-motion").checked = prefs.motion === "reduced";
  $("#set-speed").value = prefs.speed;
  $("#set-speed-out").textContent = `${prefs.speed}×`;
  $$(".settings .slider").forEach(paintSlider);
  configureTill();
}

/** Round to a friendly 1-2-5 number (for slider steps in any currency). */
function niceNumber(v) {
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n < 1.5 ? 1 : n < 3.5 ? 2 : n < 7.5 ? 5 : 10) * p;
}

function configureSpendSlider() {
  const rate = S.state.currency.to_gbp;
  const step = niceNumber(25 / rate);
  const el = $("#set-spend");
  el.step = step;
  el.min = niceNumber(50 / rate);
  el.max = Math.round(3000 / rate / step) * step;
}

/** Currency symbol, price-tag range and bubble for the till. */
function configureTill() {
  const cur = S.state.currency;
  const sym = currencySymbol(cur.code, cur.symbol);
  $("#money-sym").textContent = sym;
  $("#price").style.paddingLeft = `${1.3 + sym.length * 0.62}rem`;
  S.priceMax = cur.slider_max;
  S.priceStep = cur.slider_step;
  const price = parseFloat($("#price").value) || 0;
  // The tag's track is a fixed 0–1000 position scale (mapped to price below);
  // set it here so an old cached page can never cap the range.
  const slider = $("#price-slider");
  slider.min = 0;
  slider.max = TAG_RANGE;
  slider.step = 1;
  slider.value = posFromPrice(price);
  S.lastPriceStep = Math.round(Math.min(price, S.priceMax) / S.priceStep);
  updateTagBubble();
}

// The tag runs on an eased scale: low prices get more room on the track, so
// around everyday prices each pixel is about one step (45, 46, 47…).
const TAG_RANGE = 1000;
function priceFromPos(pos) {
  const raw = S.priceMax * Math.pow(pos / TAG_RANGE, 2);
  return Math.round(raw / S.priceStep) * S.priceStep;
}
function posFromPrice(price) {
  return Math.round(TAG_RANGE * Math.sqrt(Math.min(Math.max(price, 0), S.priceMax) / S.priceMax));
}

function setPriceFromTag(price) {
  $("#price").value = price;
  const n = Math.round(price / S.priceStep);
  if (n !== S.lastPriceStep) {
    S.lastPriceStep = n;
    const strong = n % 10 === 0;
    sound.tuck(strong);
    if (strong && navigator.vibrate) navigator.vibrate(6);
  }
  updateTagBubble();
  requestEstimate();
  if (!$("#form-error").hidden) formError("");
}

function updateTagBubble() {
  const slider = $("#price-slider");
  const f = Number(slider.value) / TAG_RANGE;
  slider.style.setProperty("--p", `${f * 100}%`);
  $("#tag-bubble").style.setProperty("--x", `calc(${f} * (100% - 38px) + 19px)`);
  const price = parseFloat($("#price").value) || 0;
  $("#tag-bubble").textContent = money(price, { decimals: price % 1 ? 2 : 0 });
}

// ---------------------------------------------------------------------------
// Swaps view: greener brands & shops, with logos
// ---------------------------------------------------------------------------
function renderLogoWall() {
  const greener = S.catalog.brands.filter((b) => b.greener).sort((a, b) => a.name.localeCompare(b.name));
  const shown = S.showAllBrands ? greener : greener.slice(0, 24);
  $("#logo-wall").innerHTML = shown.map((b) => `
    <div class="logo-card">${logoImg(b.logo)}<div><b>${esc(b.name)}</b>
      <small>${esc(b.types.slice(0, 2).map((id) => S.types[id]?.name).filter(Boolean).join(" · "))}</small></div></div>`).join("") +
    (greener.length > 24 ? `<button type="button" class="btn btn-quiet logo-more" id="logo-wall-more">${S.showAllBrands ? "Show fewer" : `Show all ${greener.length}`}</button>` : "");
  $("#logo-wall-more")?.addEventListener("click", () => { S.showAllBrands = !S.showAllBrands; renderLogoWall(); sound.tick(); });
}

const saveSettings = debounce(async (values) => {
  try {
    S.state = await api(`/api/settings?month=${S.month}`, { method: "POST", body: values });
    renderAll({ keepSettings: true });
  } catch (err) { toast(err.message); }
}, 350);

// ---------------------------------------------------------------------------
// Render everything for the current state
// ---------------------------------------------------------------------------
function renderAll({ keepSettings = false } = {}) {
  renderTitle();
  renderMonthSwitch();
  renderKPIs();
  renderCurve();
  renderGroups();
  renderRecent();
  renderShelf();
  renderLedger();
  renderWhatIf();
  renderTopSwaps();
  renderBadges();
  renderHistory();
  if (!keepSettings) renderSettings(); else renderSettingsLight();
  if (S.view === "garden") renderTree();
}

/** Country (every country in the world) and currency (every currency) pickers. */
function renderMoneyPickers() {
  const st = S.state.settings;
  const country = $("#set-country");
  const currency = $("#set-currency");
  if (!country.options.length) {
    const byCode = Object.fromEntries(S.catalog.countries.map((c) => [c.code, c]));
    const opt = (c) => `<option value="${c.code}">${esc(c.name)} · ${esc(c.currency)}</option>`;
    country.innerHTML = `<option value="" disabled>Choose your country</option>
      <optgroup label="Popular">${S.catalog.popular_countries.map((code) => opt(byCode[code])).join("")}</optgroup>
      <optgroup label="All countries (${S.catalog.countries.length})">${S.catalog.countries.map(opt).join("")}</optgroup>`;
    const named = S.catalog.currencies.map((c) => ({ code: c.code, name: currencyName(c.code), symbol: currencySymbol(c.code, c.symbol) }))
      .sort((a, b) => a.name.localeCompare(b.name));
    currency.innerHTML = named.map((c) =>
      `<option value="${c.code}">${esc(c.name)} (${esc(c.code)}${c.symbol !== c.code ? ` · ${esc(c.symbol)}` : ""})</option>`).join("");
  }
  if (document.activeElement !== country) country.value = st.country || "";
  if (document.activeElement !== currency) currency.value = st.currency;
  const cur = S.state.currency;
  $("#set-currency-out").textContent = cur.code === "GBP" ? "" : `£1 ≈ ${currencySymbol(cur.code, cur.symbol)} ${(1 / cur.to_gbp).toLocaleString(undefined, { maximumFractionDigits: cur.to_gbp > 0.1 ? 2 : 0 })}`;
  const r = S.state.rates;
  $("#rates-note").innerHTML = r?.source === "ExchangeRate-API"
    ? `Live rates, updated ${esc(new Date(r.updated).toLocaleDateString(undefined, { day: "numeric", month: "short" }))}. <a href="https://www.exchangerate-api.com" target="_blank" rel="noopener">Rates by Exchange Rate API</a>.`
    : "Using built-in rates. Live rates load when the server is online.";
}

function renderSettingsLight() {
  renderMoneyPickers();
  configureSpendSlider();
  const spend = $("#set-spend");
  if (document.activeElement !== spend) { spend.value = S.state.settings.spend_budget; paintSlider(spend); }
  $("#set-spend-out").textContent = money(Number(spend.value), { decimals: 0 });
  configureTill();
}

// ---------------------------------------------------------------------------
// Events
// ---------------------------------------------------------------------------
function isTyping(el) {
  return el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
}

function focusTill() {
  showView("overview");
  setTimeout(() => {
    $("#till").scrollIntoView({ behavior: reducedMotion() ? "auto" : "smooth", block: "start" });
    openPicker();
  }, 60);
}

async function loadDemo() {
  if (S.state.total_count && !confirm("Replace all your purchases with a sample month? This can't be undone.")) return;
  try {
    S.state = await api("/api/demo", { method: "POST" });
    S.month = S.state.month;
    S.treeKey = null;
    renderAll();
    showView("overview");
    sound.ring("low");
    toast("Sample month loaded — 15 purchases this month, 7 last month.");
    const latest = S.state.purchases[0];
    if (latest) {
      const kind = { low: "sprig", medium: "steps", high: "deep_step" }[latest.tier];
      const art = await api(`/api/drawing/${kind}`);
      printReceipt(latest, { svg: art.svg, message: "Latest purchase in the sample month." }, null, true);
    }
  } catch (err) { toast(err.message); }
}

function bindEvents() {
  // Unlock audio on the first real interaction.
  const unlock = () => { sound.unlocked = true; };
  addEventListener("pointerdown", unlock, { once: true, capture: true });
  addEventListener("keydown", unlock, { once: true, capture: true });

  // Navigation
  document.addEventListener("click", (e) => {
    const nav = e.target.closest("[data-nav]");
    if (nav) { showView(nav.dataset.nav, { focus: nav.classList.contains("nav-btn") }); return; }
    const sw = e.target.closest("[data-swap]");
    if (sw) { openSwap(sw.dataset.swap); return; }
    const del = e.target.closest("[data-delete]");
    if (del) { deletePurchase(Number(del.dataset.delete)); return; }
    const badge = e.target.closest("[data-badge]");
    if (badge) { spotlightBadge(badge.dataset.badge); return; }
    const action = e.target.closest("[data-action]");
    if (action?.dataset.action === "demo") { loadDemo(); return; }
    if (action?.dataset.action === "focus-till") { focusTill(); return; }
    const group = e.target.closest("[data-group]");
    if (group) { S.catalogGroup = group.dataset.group; renderCatalog(); sound.tick(); return; }
    // Close picker on outside click.
    if (!$("#picker").hidden && !e.target.closest(".field-type")) closePicker(false);
    if (!$("#brand-pop").hidden && !e.target.closest(".field-brand")) closeBrandPop();
  });
  addEventListener("hashchange", () => showView(location.hash.slice(1)));

  $("#month-prev").addEventListener("click", () => { loadMonth(shiftMonth(S.month, -1)); sound.tick(); });
  $("#month-next").addEventListener("click", () => { loadMonth(shiftMonth(S.month, 1)); sound.tick(); });

  // Sound + theme quick toggles
  $("#sound-toggle").addEventListener("click", () => {
    prefs.sound = !prefs.sound; savePrefs(); applyPrefs(); renderSettings();
    sound.unlocked = true; sound.toggle(prefs.sound);
  });
  $("#theme-toggle").addEventListener("click", () => {
    const current = document.documentElement.dataset.theme;
    prefs.theme = current === "light" ? "dark" : "light";
    savePrefs(); applyPrefs(); renderSettings(); sound.toggle(prefs.theme === "light");
    requestAnimationFrame(renderCurve);
  });

  // Till
  $("#till").addEventListener("submit", ringUp);
  $("#type-btn").addEventListener("click", () => ($("#picker").hidden ? openPicker() : closePicker()));
  $("#type-btn").addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); openPicker(); }
  });
  $("#picker-search").addEventListener("input", (e) => renderPicker(e.target.value));
  $("#picker-search").addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActiveOption(S.pickerActive + 1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActiveOption(S.pickerActive - 1); }
    else if (e.key === "Enter") {
      e.preventDefault();
      const opt = $$("#picker-list .picker-opt")[S.pickerActive];
      if (opt) { selectType(opt.dataset.id); closePicker(false); sound.tick(); $("#price").focus(); }
    } else if (e.key === "Escape") { e.preventDefault(); closePicker(); }
    else if (e.key === "Tab") closePicker(false);
  });
  $("#picker-list").addEventListener("click", (e) => {
    const opt = e.target.closest(".picker-opt");
    if (!opt) return;
    selectType(opt.dataset.id);
    closePicker(false);
    sound.tick();
    $("#price").focus();
  });
  $("#picker-list").addEventListener("mousemove", (e) => {
    const opt = e.target.closest(".picker-opt");
    if (opt) setActiveOption($$("#picker-list .picker-opt").indexOf(opt));
  });

  // Price tag slider: drag it and the price follows, "tuck" by "tuck".
  const slider = $("#price-slider");
  const track = $("#tag-track");
  slider.addEventListener("input", () => setPriceFromTag(priceFromPos(Number(slider.value))));
  slider.addEventListener("keydown", (e) => {
    // Arrow keys move exactly one price step (Shift = ten steps): 45, 46, 47…
    const dir = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[e.key];
    if (!dir) return;
    e.preventDefault();
    const current = parseFloat($("#price").value) || 0;
    const step = S.priceStep * (e.shiftKey ? 10 : 1);
    const next = Math.min(Math.max(Math.round((current + dir * step) / S.priceStep) * S.priceStep, 0), S.priceMax);
    slider.value = posFromPrice(next);
    setPriceFromTag(next);
  });
  slider.addEventListener("pointerdown", () => track.classList.add("is-dragging"));
  addEventListener("pointerup", () => track.classList.remove("is-dragging"));
  addEventListener("pointercancel", () => track.classList.remove("is-dragging"));
  $("#price").addEventListener("input", () => {
    const v = parseFloat($("#price").value) || 0;
    slider.value = posFromPrice(v);
    S.lastPriceStep = Math.round(Math.min(v, S.priceMax) / S.priceStep);
    updateTagBubble();
    requestEstimate();
    if (!$("#form-error").hidden) formError("");
  });

  // Every range slider in the app clicks softly as it moves through its steps.
  document.addEventListener("input", (e) => {
    const el = e.target;
    if (el.type !== "range" || el.id === "price-slider") return; // the price tag has its own
    const n = Math.round(Number(el.value) / (Number(el.step) || 1));
    if (n === el._lastStep) return;
    el._lastStep = n;
    const strong = n % 10 === 0;
    sound.tuck(strong);
    if (strong && navigator.vibrate) navigator.vibrate(6);
  });

  // Brand combobox
  const brand = $("#brand");
  brand.addEventListener("focus", openBrandPop);
  brand.addEventListener("click", () => { if ($("#brand-pop").hidden) openBrandPop(); });
  brand.addEventListener("input", () => {
    if ($("#brand-pop").hidden) openBrandPop(); else renderBrandPop();
    updateBrandLogo();
    requestEstimate();
  });
  brand.addEventListener("keydown", (e) => {
    const open = !$("#brand-pop").hidden;
    if (e.key === "ArrowDown") { e.preventDefault(); if (!open) openBrandPop(); else setActiveBrand(S.brandActive + 1); }
    else if (e.key === "ArrowUp" && open) { e.preventDefault(); setActiveBrand(S.brandActive <= 0 ? -1 : S.brandActive - 1); }
    else if (e.key === "Enter" && open) {
      e.preventDefault();
      const picked = S.brandResults[S.brandActive];
      if (picked) chooseBrand(picked);
      else { closeBrandPop(); $("#price").focus(); }
    } else if (e.key === "Escape" && open) { e.preventDefault(); closeBrandPop(); }
    else if (e.key === "Tab") closeBrandPop();
  });
  $("#brand-options").addEventListener("mousedown", (e) => e.preventDefault()); // keep focus in the input
  $("#brand-options").addEventListener("click", (e) => {
    const opt = e.target.closest(".brand-opt");
    if (opt) chooseBrand(S.brandResults[Number(opt.dataset.i)]);
  });
  $("#brand-options").addEventListener("mousemove", (e) => {
    const opt = e.target.closest(".brand-opt");
    if (opt && Number(opt.dataset.i) !== S.brandActive) setActiveBrand(Number(opt.dataset.i));
  });

  // Swap sheet: tap a greener brand to fill it in.
  $("#swap-brand-picks").addEventListener("click", (e) => {
    const chip = e.target.closest("[data-pick]");
    if (!chip) return;
    const on = chip.getAttribute("aria-pressed") !== "true";
    $$("#swap-brand-picks .pick-chip").forEach((c) => c.setAttribute("aria-pressed", "false"));
    chip.setAttribute("aria-pressed", String(on));
    $("#swap-brand").value = on ? chip.dataset.pick : "";
    sound.tick();
  });

  // A logo that fails to load (offline, say) quietly disappears.
  document.addEventListener("error", (e) => {
    if (e.target.tagName === "IMG" && e.target.closest(".blogo, .brand-logo, .rc-brand, .brand-chip, .pick-chip, .logo-card") ) e.target.style.visibility = "hidden";
  }, true);

  // Ledger controls
  $("#ledger-search").addEventListener("input", (e) => { S.ledger.q = e.target.value; renderLedger(); });
  $$(".toolbar .chip input").forEach((c) => c.addEventListener("change", () => {
    c.checked ? S.ledger.tiers.add(c.value) : S.ledger.tiers.delete(c.value);
    renderLedger(); sound.tick();
  }));
  $("#ledger-sort").addEventListener("change", (e) => { S.ledger.sort = e.target.value; renderLedger(); });

  // Swaps
  $("#whatif").addEventListener("input", renderWhatIf);
  $("#swap-sheet").addEventListener("close", () => {
    if ($("#swap-sheet").returnValue === "confirm") confirmSwap();
    S.swapTarget = $("#swap-sheet").returnValue === "confirm" ? S.swapTarget : null;
  });
  $("#badge-sheet").addEventListener("close", () => { sound.penStop(); setTimeout(nextBadge, 250); });

  // Garden
  $("#tree-replay").addEventListener("click", () => {
    if (S.treeSvg) playTurtle($("#tree-stage"), S.treeSvg, { speed: prefs.speed, reduced: reducedMotion(), sound, maxMs: 6500, minMs: 2200 });
  });
  $("#quote-next").addEventListener("click", () => { showQuote(1); sound.tick(); });
  $("#tip-next").addEventListener("click", () => { showTip(1); sound.tick(); });

  // Settings
  $("#set-name").addEventListener("input", (e) => saveSettings({ name: e.target.value }));
  $("#set-currency").addEventListener("change", (e) => { saveSettings({ currency: e.target.value }); sound.tick(); });
  $("#set-country").addEventListener("change", (e) => {
    const c = S.catalog.countries.find((x) => x.code === e.target.value);
    if (!c) return;
    $("#set-currency").value = c.currency; // show the switch straight away
    saveSettings({ country: c.code });
    sound.tick();
    toast(`${c.name} — prices now in ${currencyName(c.currency)}.`);
  });
  $("#set-co2").addEventListener("input", (e) => {
    paintSlider(e.target); $("#set-co2-out").textContent = `${e.target.value} kg`;
    saveSettings({ co2_budget: Number(e.target.value) });
  });
  $("#set-spend").addEventListener("input", (e) => {
    paintSlider(e.target); $("#set-spend-out").textContent = money(Number(e.target.value), { decimals: 0 });
    saveSettings({ spend_budget: Number(e.target.value) });
  });
  $$("#set-theme button").forEach((b) => b.addEventListener("click", () => {
    prefs.theme = b.dataset.value; savePrefs(); applyPrefs(); renderSettings(); sound.tick();
    requestAnimationFrame(renderCurve);
  }));
  $$("#set-text button").forEach((b) => b.addEventListener("click", () => {
    prefs.text = b.dataset.value; savePrefs(); applyPrefs(); renderSettings(); sound.tick();
    requestAnimationFrame(renderCurve);
  }));
  $("#set-sound").addEventListener("change", (e) => {
    prefs.sound = e.target.checked; savePrefs(); applyPrefs(); sound.toggle(prefs.sound);
  });
  $("#set-volume").addEventListener("input", (e) => {
    prefs.volume = Number(e.target.value) / 100; savePrefs(); paintSlider(e.target);
    $("#set-volume-out").textContent = `${e.target.value}%`; sound.setVolume(prefs.volume);
  });
  $("#set-volume").addEventListener("change", () => sound.ring("low"));
  $("#set-motion").addEventListener("change", (e) => { prefs.motion = e.target.checked ? "reduced" : "full"; savePrefs(); applyPrefs(); });
  $("#set-speed").addEventListener("input", (e) => {
    prefs.speed = Number(e.target.value); savePrefs(); paintSlider(e.target); $("#set-speed-out").textContent = `${prefs.speed}×`;
  });
  $("#demo-btn").addEventListener("click", loadDemo);
  $("#reset-btn").addEventListener("click", async () => {
    if (!confirm("Erase every purchase you've logged? This can't be undone.")) return;
    try {
      S.state = await api("/api/reset", { method: "POST" });
      S.month = S.state.month;
      S.treeKey = null;
      renderAll();
      printReceipt(null, { svg: S.sprigSvg }, null, false);
      sound.remove();
      toast("All purchases erased.");
    } catch (err) { toast(err.message); }
  });

  // Keyboard shortcuts
  addEventListener("keydown", (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey || isTyping(document.activeElement) || document.querySelector("dialog[open]")) return;
    const k = e.key.toLowerCase();
    if (k === "n") { e.preventDefault(); focusTill(); }
    else if (k === "m") { $("#sound-toggle").click(); }
    else if (k === "arrowleft") { $("#month-prev").click(); }
    else if (k === "arrowright" && !$("#month-next").disabled) { $("#month-next").click(); }
    else if (/^[1-6]$/.test(k)) { showView(VIEW_ORDER[Number(k) - 1]); }
  });

  // Re-draw the curve when its box changes size.
  let lastW = 0;
  new ResizeObserver(debounce((entries) => {
    const w = Math.round(entries[0].contentRect.width);
    if (w !== lastW) { lastW = w; renderCurve(); }
  }, 120)).observe($("#curve"));
}

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
async function init() {
  applyPrefs();
  try {
    const [catalog, state, sprig] = await Promise.all([
      api("/api/catalog"), api("/api/state"), api("/api/drawing/sprig"),
    ]);
    S.catalog = catalog;
    S.catalog.types.forEach((t) => { S.types[t.id] = t; });
    S.catalog.groups.forEach((g) => { S.groups[g.id] = g; });
    S.catalog.brands.forEach((b) => {
      S.brandByName[b.name.toLowerCase()] = b;
      b.types.forEach((t) => (S.typeBrands[t] ||= []).push(b.name.toLowerCase()));
    });
    S.state = state;
    S.month = state.month;
    S.sprigSvg = sprig.svg;
    S.tips = Object.values(catalog.tips).flat();
    S.tipIndex = Math.floor(Math.random() * S.tips.length);
    S.quoteIndex = catalog.quotes.findIndex((q) => q.text === state.quote?.text);
    if (S.quoteIndex < 0) S.quoteIndex = 0;
  } catch (err) {
    $("#view-title").textContent = "ShopImpact can't reach its server";
    $("#view-eyebrow").textContent = err.message;
    return;
  }
  $("#date").value = todayISO();
  selectType(null);
  bindEvents();
  renderCatalog();
  renderLogoWall();
  renderAll();
  showTip(0);
  showQuote(0);
  showView(location.hash.slice(1) || "overview", { silent: true });
  // Month-long badges from a month that just ended are celebrated once.
  if (S.state.celebrate?.length) { S.badgeQueue.push(...S.state.celebrate); setTimeout(nextBadge, 1200); }

  // First receipt: the latest purchase, or a welcome slip with a turtle sprig.
  const latest = S.state.purchases[0];
  if (latest) {
    const kind = { low: "sprig", medium: "steps", high: "deep_step" }[latest.tier];
    const art = kind === "sprig" ? { svg: S.sprigSvg } : await api(`/api/drawing/${kind}`);
    printReceipt(latest, { svg: art.svg, message: "Your latest purchase." }, null, false);
  } else {
    await printReceipt(null, null, null, false);
    playTurtle($("#receipt-well [data-stamp]"), S.sprigSvg, { speed: prefs.speed, reduced: reducedMotion(), maxMs: 2600 });
  }
}

init();
