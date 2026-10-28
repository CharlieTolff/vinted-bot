// Bokföring: håll koll på det du köper in och säljer. Allt sparas i
// webbläsaren (localStorage). Ett plagg kan läggas in för hand eller från en
// skärmbild av en försäljning på Vinted eller Tradera; texten läses av med
// Tesseract (OCR) direkt i webbläsaren, så bilden skickas aldrig någonstans.
(() => {
const NYCKEL = "bokforing-v1";
const TESS = "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js";
const STATUS = ["I lager", "Upplagd", "Såld"];
const KOPT = ["Vinted", "Tradera", "Plick", "Loppis", "Second hand-butik", "Leverantör", "Annat"];
const SALD = ["Vinted", "Tradera", "Plick", "Annat"];
const VANLIGA_MARKEN = ["Acne Studios", "Adidas", "Arket", "Barbour", "Belstaff", "Boss", "Canada Goose", "Carhartt", "COS", "Diesel", "Dsquared2",
  "Filippa K", "Fred Perry", "Gant", "Hollister", "J.Lindeberg", "Jack & Jones", "Lacoste", "Levi's", "Lyle & Scott", "Moncler", "Morris",
  "Nike", "Nudie Jeans", "Oscar Jacobson", "Our Legacy", "Parajumpers", "Patagonia", "Polo Ralph Lauren", "Ralph Lauren", "Replay",
  "Sail Racing", "Stone Island", "Superdry", "The North Face", "Tiger of Sweden", "Tommy Hilfiger", "Wood Wood"];

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const krText = v => v == null || isNaN(v) ? "–" : Math.round(v).toLocaleString("sv-SE") + " kr";
const tecken = v => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(Math.round(v)).toLocaleString("sv-SE") + " kr";
const tal = s => { const v = parseFloat(String(s ?? "").replace(/\s/g, "").replace(",", ".")); return isNaN(v) ? null : v; };
const idag = () => new Date().toLocaleDateString("sv-SE");

let poster = [];
function las(){ try { poster = JSON.parse(localStorage.getItem(NYCKEL)) || []; } catch { poster = []; } }
function spara(){
  try { localStorage.setItem(NYCKEL, JSON.stringify(poster)); }
  catch { alert("Det gick inte att spara. Webbläsaren kanske är i privat läge."); }
}
let filter = "alla", period = "allt", utv = "max", sok = "", visa = 12;
try {
  filter = localStorage.getItem("bokforing-filter") || "alla"; period = localStorage.getItem("bokforing-period") || "allt";
  utv = localStorage.getItem("bokforing-utv") || "max";
} catch {}
if (!["allt", "manad", "vecka"].includes(period)) period = "allt";

const DAG = 864e5;
const dagTid = d => d ? new Date(d + "T12:00:00").getTime() : null;
const kortDatum = d => d ? new Date(d + "T12:00:00").toLocaleDateString("sv-SE", {day: "numeric", month: "short"}) : "";
const vinst = p => p.status === "Såld" && p.salj != null ? p.salj - (p.inkop || 0) - (p.kostnad || 0) : null;
const FAST_DAGAR = 21;  // så länge ett plagg får ligga osålt innan det räknas som fastnat
function periodStart(){
  const n = new Date();
  if (period === "manad") return new Date(n.getFullYear(), n.getMonth(), 1).getTime();
  if (period === "vecka") return new Date(n.getFullYear(), n.getMonth(), n.getDate() - (n.getDay() + 6) % 7).getTime();
  return null;
}
const iPeriod = d => { const s = periodStart(); return s == null || (d && dagTid(d) >= s); };
const dagar = p => {
  const fran = dagTid(p.inkopsdatum); if (!fran) return null;
  return Math.max(0, Math.round((((p.status === "Såld" ? dagTid(p.saljdatum) : null) ?? Date.now()) - fran) / DAG));
};

// ---------- Bilder på plaggen ----------
// Sparas i webbläsaren (IndexedDB), så de stannar på den här enheten och följer med i säkerhetskopian.
const BILD = {};
let bildDb = null;
function db(){
  return bildDb ??= new Promise((ok, fel) => {
    const r = indexedDB.open("bokforing-bilder", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("bilder");
    r.onsuccess = () => ok(r.result); r.onerror = () => fel(r.error);
  });
}
async function bildlager(metod, ...arg){
  const d = await db();
  return new Promise((ok, fel) => {
    const q = d.transaction("bilder", metod.startsWith("get") ? "readonly" : "readwrite").objectStore("bilder")[metod](...arg);
    q.onsuccess = () => ok(q.result); q.onerror = () => fel(q.error);
  });
}
async function laddaBilder(){
  try {
    for (const id of await bildlager("getAllKeys")) {
      const blob = await bildlager("get", id);
      if (blob) { if (BILD[id]) URL.revokeObjectURL(BILD[id]); BILD[id] = URL.createObjectURL(blob); }
    }
  } catch {}
  ritaVaror();
}
async function forminska(fil){
  const bild = await createImageBitmap(fil, {imageOrientation: "from-image"});
  const f = Math.min(1, 1000 / Math.max(bild.width, bild.height));
  const c = document.createElement("canvas"); c.width = Math.round(bild.width * f); c.height = Math.round(bild.height * f);
  c.getContext("2d").drawImage(bild, 0, 0, c.width, c.height);
  return new Promise(ok => c.toBlob(ok, "image/jpeg", 0.85));
}
async function sparaBild(id, fil){
  try {
    const blob = await forminska(fil);
    await bildlager("put", blob, id);
    if (BILD[id]) URL.revokeObjectURL(BILD[id]);
    BILD[id] = URL.createObjectURL(blob);
  } catch { alert("Det gick inte att spara bilden. Prova en annan bild, eller kolla att webbläsaren inte är i privat läge."); }
}
async function taBortBild(id){
  try { await bildlager("delete", id); } catch {}
  if (BILD[id]) { URL.revokeObjectURL(BILD[id]); delete BILD[id]; }
}

// ---------- Ritning ----------
const IKON = {
  vinst: '<path d="M4 17l5-5 4 4 7-8"/><path d="M15 8h5v5"/>',
  oms: '<path d="M4 7h13l3 3-3 3H4z"/><path d="M8 17h12"/>',
  lager: '<path d="M4 8l8-4 8 4v8l-8 4-8-4z"/><path d="M4 8l8 4 8-4M12 12v8"/>',
  kopt: '<path d="M6 7h12l-1 13H7z"/><path d="M9 7a3 3 0 016 0"/>',
};
// Siffrorna räknas upp från noll när de visas.
function raknaUpp(el, slut, fmt){
  if (matchMedia("(prefers-reduced-motion: reduce)").matches || !slut) { el.textContent = fmt(slut); return; }
  const start = performance.now();
  const steg = nu => { const f = Math.min(1, (nu - start) / 900); el.textContent = fmt(slut * (1 - Math.pow(1 - f, 3))); if (f < 1) requestAnimationFrame(steg); };
  requestAnimationFrame(steg);
}
const segment = (el, val, valt, attr) => { el.innerHTML = val.map(([k, n]) => `<button data-${attr}="${k}" class="${k === valt ? "vald" : ""}">${n}</button>`).join(""); };

function rita(){ ritaTopp(); ritaVaror(true); }
function ritaTopp(){
  const salda = poster.filter(p => p.status === "Såld" && p.salj != null && iPeriod(p.saljdatum));
  const summaVinst = salda.reduce((s, p) => s + vinst(p), 0), saltFor = salda.reduce((s, p) => s + p.salj, 0);
  const medInkop = salda.filter(p => p.inkop > 0), kost = medInkop.reduce((s, p) => s + p.inkop + (p.kostnad || 0), 0);
  const roi = kost ? 100 * medInkop.reduce((s, p) => s + vinst(p), 0) / kost : null;
  const lager = poster.filter(p => p.status !== "Såld"), upplagda = lager.filter(p => p.status === "Upplagd").length;
  const kopta = poster.filter(p => iPeriod(p.inkopsdatum));
  const nar = {allt: "totalt", manad: "i " + new Date().toLocaleDateString("sv-SE", {month: "long"}), vecka: "den här veckan"}[period];
  segment($("bfperiod"), [["allt", "Totalt"], ["manad", "Månaden"], ["vecka", "Veckan"]], period, "p");
  const ruta = (klass, ikon, et, id, under) => `<div class="bfhruta ${klass}"><div class="bfetikett"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IKON[ikon]}</svg>${et}</div><b id="${id}"></b><small>${under}</small></div>`;
  const st = (n, en, fler) => `${n} ${n === 1 ? en : fler}`;
  $("bfrutor").innerHTML =
    ruta("stjarna", "vinst", "Vinst " + nar, "bfvinst", salda.length ? `${roi == null ? "" : `<span class="upp">${roi > 0 ? "+" : ""}${Math.round(roi)} %</span> avkastning · `}${st(salda.length, "sålt plagg", "sålda plagg")}` : "när du har sålt något") +
    ruta("", "oms", "Sålt för", "bfsalt", st(salda.length, "affär", "affärer")) +
    ruta("", "lager", "I lager nu", "bflager", lager.length ? `${st(lager.length, "plagg", "plagg")}${upplagda ? ` · ${upplagda} upplagda` : ""}` : "inget i lager") +
    ruta("", "kopt", "Inköpt", "bfkopt", `${st(kopta.length, "plagg", "plagg")} ${nar}`);
  $("bfvinst").className = summaVinst < 0 ? "ned" : "";
  raknaUpp($("bfvinst"), summaVinst, v => salda.length ? tecken(v) : "0 kr"); raknaUpp($("bfsalt"), saltFor, krText);
  raknaUpp($("bflager"), lager.reduce((s, p) => s + (p.inkop || 0), 0), krText); raknaUpp($("bfkopt"), kopta.reduce((s, p) => s + (p.inkop || 0), 0), krText);
  segment($("bfutv"), [["1m", "1 mån"], ["3m", "3 mån"], ["1a", "1 år"], ["max", "Max"]], utv, "u");
  ritaUtveckling();
}

// Vinsten dag för dag: hoppar uppåt den dag något säljs.
function ritaUtveckling(){
  const el = $("bfdiagram"), salda = poster.filter(p => p.status === "Såld" && p.salj != null);
  const tider = poster.flatMap(p => [dagTid(p.inkopsdatum), dagTid(p.saljdatum)]).filter(Boolean);
  if (!salda.length || !tider.length) { el.innerHTML = `<div class="tomt">Här växer din vinst fram när du sålt något.</div>`; return; }
  const perDag = {}; let sum = salda.filter(p => !dagTid(p.saljdatum)).reduce((s, p) => s + vinst(p), 0);
  for (const p of salda) { const t = dagTid(p.saljdatum); if (t) perDag[t] = (perDag[t] || 0) + vinst(p); }
  const nu = dagTid(idag()), pts = [];
  for (let t = Math.min(...tider, nu); t <= nu; t += DAG) { sum += perDag[t] || 0; pts.push([t, sum, perDag[t] || 0]); }
  const vis = pts.filter(q => q[0] >= nu - ({"1m": 30, "3m": 91, "1a": 365}[utv] ?? 1e6) * DAG);
  const W = Math.max(280, el.clientWidth - 6), H = W < 500 ? 180 : 220, pad = {l: 62, r: 10, t: 12, b: 26};
  const x0 = vis[0][0], x1 = Math.max(vis.at(-1)[0], x0 + DAG);
  let y0 = Math.min(0, ...vis.map(q => q[1])), y1 = Math.max(0, ...vis.map(q => q[1]));
  const luft = (y1 - y0) * 0.1 || 100; y1 += luft; if (y0 < 0) y0 -= luft;
  const X = x => pad.l + (W - pad.l - pad.r) * (x - x0) / (x1 - x0), Y = y => H - pad.b - (H - pad.t - pad.b) * (y - y0) / (y1 - y0);
  const farg = vis.at(-1)[1] >= (vis[0][1] - vis[0][2]) ? "var(--plus)" : "var(--minus)";
  const kort = t => new Date(t).toLocaleDateString("sv-SE", {day: "numeric", month: "short"});
  const grid = [];
  for (let i = 0; i <= 4; i++) { const v = y0 + (y1 - y0) * i / 4, y = Y(v); grid.push(`<line x1="${pad.l}" x2="${W - pad.r}" y1="${y}" y2="${y}" stroke="var(--linje)" stroke-opacity=".55" ${i ? 'stroke-dasharray="2 4"' : ""}/><text x="${pad.l - 8}" y="${y + 4}" text-anchor="end">${krText(v)}</text>`); }
  const nX = Math.min(5, Math.max(2, Math.floor((W - pad.l) / 90)));
  for (let i = 0; i < nX; i++) { const t = x0 + (x1 - x0) * i / (nX - 1); grid.push(`<text x="${X(t)}" y="${H - 7}" text-anchor="${i === 0 ? "start" : i === nX - 1 ? "end" : "middle"}">${kort(t)}</text>`); }
  let d = `M${X(vis[0][0]).toFixed(1)} ${Y(vis[0][1]).toFixed(1)}`;
  for (let i = 1; i < vis.length; i++) d += `H${X(vis[i][0]).toFixed(1)}V${Y(vis[i][1]).toFixed(1)}`;
  el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" height="${H}" role="img" aria-label="Din vinst över tid">
    <defs><linearGradient id="bffyll" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${farg}" stop-opacity=".38"/><stop offset="1" stop-color="${farg}" stop-opacity="0"/></linearGradient></defs>
    ${grid.join("")}
    <path d="${d}V${Y(Math.max(y0, 0))}H${X(vis[0][0])}Z" fill="url(#bffyll)"/>
    <path d="${d}" fill="none" stroke="${farg}" stroke-width="2.6" stroke-linejoin="round" style="filter:drop-shadow(0 0 6px ${farg})"/>
    ${vis.filter(q => q[2]).map(q => `<circle cx="${X(q[0])}" cy="${Y(q[1])}" r="3.2" fill="${q[2] >= 0 ? "var(--plus)" : "var(--minus)"}" stroke="var(--kort)" stroke-width="1.5"/>`).join("")}
    <line id="bfsikte" y1="${pad.t}" y2="${H - pad.b}" stroke="var(--text)" stroke-opacity=".35" visibility="hidden"/>
    <rect id="bffanga" x="${pad.l}" y="0" width="${W - pad.l - pad.r}" height="${H}" fill="transparent"/>
  </svg><div class="tips" id="bftips" hidden></div>`;
  const svg = el.querySelector("svg"), sikte = el.querySelector("#bfsikte"), tips = el.querySelector("#bftips");
  el.querySelector("#bffanga").addEventListener("pointermove", e => {
    const r = svg.getBoundingClientRect(), t = x0 + ((e.clientX - r.left) * W / r.width - pad.l) / (W - pad.l - pad.r) * (x1 - x0);
    const q = vis.reduce((b, x) => Math.abs(x[0] - t) < Math.abs(b[0] - t) ? x : b, vis[0]);
    sikte.setAttribute("x1", X(q[0])); sikte.setAttribute("x2", X(q[0])); sikte.setAttribute("visibility", "visible");
    tips.innerHTML = `<div style="opacity:.75">${kort(q[0])}</div><div>Total vinst: <b>${tecken(q[1])}</b></div>` +
      salda.filter(p => dagTid(p.saljdatum) === q[0]).map(p => `<div class="rad">${esc(p.namn || p.marke)}: ${tecken(vinst(p))}</div>`).join("");
    tips.hidden = false;
    tips.style.left = Math.min(Math.max(0, X(q[0]) * r.width / W + 12), r.width - tips.offsetWidth - 4) + "px"; tips.style.top = "8px";
  });
  el.querySelector("#bffanga").addEventListener("pointerleave", () => { tips.hidden = true; sikte.setAttribute("visibility", "hidden"); });
}

const kamera = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/></svg>';
function varkort(p){
  const sald = p.status === "Såld", d = dagar(p), fast = !sald && d != null && d >= FAST_DAGAR, src = BILD[p.id];
  const badge = sald ? `<span class="bfkbadge sald">Såld</span>` : fast ? `<span class="bfkbadge fast">Fastnat</span>`
    : `<span class="bfkbadge ${p.status === "Upplagd" ? "upplagd" : "lager"}">${esc(p.status)}</span>`;
  const vi = vinst(p), marg = vi != null && p.salj ? Math.round(100 * vi / p.salj) + " %" : "";
  const under = [p.marke, p.storlek && "stl " + p.storlek, sald ? (p.saljdatum && "såld " + kortDatum(p.saljdatum)) : (p.inkopsdatum && "köpt " + kortDatum(p.inkopsdatum))].filter(Boolean).join(" · ");
  return `<article class="bfvara" data-id="${esc(p.id)}">
    <div class="bfkbild${src ? " harbild" : ""}">${src ? `<img src="${src}" alt="${esc(p.namn)}" loading="lazy">` : ""}${badge}
      ${sald && p.saldPa ? `<span class="bfktagg">${esc(p.saldPa)}</span>` : ""}
      <button class="bfkamera" data-bild="${esc(p.id)}" title="${src ? "Byt bild" : "Lägg till bild"}">${kamera}<span class="bt">${src ? "Byt bild" : "Lägg till bild"}</span></button>
      <div class="bfkmarke${(p.marke || "").length > 13 ? " lang" : ""}">${esc(p.marke || "Plagg")}</div><div class="bfkkat">${esc(p.kategori || "")}</div>
      ${d != null ? `<span class="bfkdagar" title="${sald ? "Dagar från köp till försäljning" : "Dagar sedan du köpte det"}">${d} d</span>` : ""}</div>
    <div class="bfkinfo">
      <div class="bfknamn" title="${esc(p.namn)}">${esc(p.namn || p.marke || "Plagg")}<small>${esc(under)}</small></div>
      <div class="bfksiffror">
        <div><small>Inköp</small><b>${krText(p.inkop)}</b></div>
        <div><small>Sålt</small><b>${sald ? krText(p.salj) : "–"}</b></div>
        <div class="bfkvinst">${sald ? `<small>Vinst</small><b class="${vi > 0 ? "plus" : vi < 0 ? "minus" : ""}">${vi == null ? "–" : tecken(vi)}</b><em>${marg}</em>` : `<button class="bfsaltknapp" data-salj="${esc(p.id)}">Sålt</button>`}</div>
      </div>
    </div></article>`;
}
function ritaVaror(tona){
  const ord = sok.toLowerCase().split(/\s+/).filter(Boolean);
  const senast = p => p.saljdatum || p.inkopsdatum || p.skapad || "";
  const alla = [...poster].sort((a, b) => senast(b).localeCompare(senast(a)));
  const urval = {alla, "I lager": alla.filter(p => p.status === "I lager"), Upplagd: alla.filter(p => p.status === "Upplagd"), "Såld": alla.filter(p => p.status === "Såld")};
  if (!urval[filter]) filter = "alla";
  $("bffilter").innerHTML = [["alla", "Alla"], ["I lager", "I lager"], ["Upplagd", "Upplagda"], ["Såld", "Sålda"]]
    .map(([k, n]) => `<button data-f="${k}" class="${k === filter ? "vald" : ""}">${n} <span class="antal">${urval[k].length}</span></button>`).join("");
  const lista = urval[filter].filter(p => { const t = [p.namn, p.marke, p.kategori, p.storlek, p.saldPa].join(" ").toLowerCase(); return ord.every(o => t.includes(o)); });
  const lager = poster.filter(p => p.status !== "Såld");
  $("bfinfo").textContent = poster.length ? `${poster.length} plagg · ${lager.length} i lager · ${poster.length - lager.length} sålda` : "";
  const g = $("bfvaror");
  g.classList.toggle("tona", !!tona);
  g.innerHTML = !poster.length ? `<div class="tomt" style="grid-column:1/-1">Här hamnar allt du köper och säljer. Börja med att lägga till ett plagg, eller ta en skärmbild när du har sålt något på Vinted eller Tradera.</div>`
    : lista.length ? lista.slice(0, visa).map(varkort).join("") : `<div class="tomt" style="grid-column:1/-1">${ord.length ? "Inga plagg matchar sökningen." : "Inga plagg här än."}</div>`;
  const kvar = lista.length - visa;
  $("bfmer").innerHTML = kvar > 0 ? `<button id="bfvisafler">Visa fler (${kvar} till)</button>` : "";
}

// ---------- Formuläret ----------
function marken(){
  const s = new Set(VANLIGA_MARKEN);
  try { for (const kalla of Object.values(B?.marke || {})) for (const kat of Object.values(kalla || {})) for (const m of Object.keys(kat || {})) s.add(m); } catch {}
  try { for (const k of Object.values(B?.marknad?.kategorier || {})) for (const r of k.marken || []) s.add(r.m); } catch {}
  for (const p of poster) if (p.marke) s.add(p.marke);
  return [...s].sort((a, b) => a.localeCompare(b, "sv"));
}
window.BokforMarken = () => marken();
function kategorier(){
  const s = new Set();
  try { for (const k of B?.kategorier || []) if (!k.vantar) s.add(k.namn); } catch {}
  ["Tröjor", "Hoodies", "T-shirts", "Jackor", "Byxor", "Skor", "Accessoarer"].forEach(k => s.add(k));
  for (const p of poster) if (p.kategori) s.add(p.kategori);
  return [...s, "Övrigt"].filter((v, i, a) => a.indexOf(v) === i);
}
// Gissar kategori från plaggets namn, så att man slipper välja själv.
const KATORD = [[/kofta|cardigan/i, "Koftor"], [/stick|merino|kashmir|lammull/i, "Stickade"], [/hoodie|huvtröja|sweatshirt|sweater|college|tröja/i, "Tröjor"],
  [/overshirt|skjortjacka/i, "Overshirts"], [/skjorta/i, "Skjortor"], [/dunjacka|dunväst|\bdun\b|puffer/i, "Dunjackor"], [/jeans/i, "Jeans"],
  [/jacka|parka|kavaj|blazer|väst/i, "Jackor"], [/t-shirt|tshirt|\btee\b|piké|pike/i, "T-shirts"], [/byxa|byxor|chinos|shorts/i, "Byxor"],
  [/sko|sneaker|kängor|boots|loafers/i, "Skor"], [/keps|mössa|halsduk|bälte|plånbok|väska|solglasögon/i, "Accessoarer"]];
function gissaKategori(namn){
  const lista = kategorier();
  for (const [re, kat] of KATORD) if (re.test(namn || "")) { const k = lista.find(x => x.toLowerCase().startsWith(kat.toLowerCase())); if (k) return k; }
  return "";
}
const alternativ = (lista, valt) => lista.map(v => `<option${v === valt ? " selected" : ""}>${esc(v)}</option>`).join("");
let redigerar = null, nyBild = null;
function visaFormBild(src){
  $("bfformbild").hidden = !src; if (src) $("bfformbild").src = src;
  $("bfformbildknapp").textContent = src ? "Byt bild" : "Lägg till bild på plagget";
}
function oppna(p, notis, bild, fokus){
  redigerar = p?.id || null; nyBild = null;
  visaFormBild(redigerar ? BILD[redigerar] : null);
  const f = $("bfform");
  f.reset();
  delete f.kategori.dataset.vald;
  $("bfmarken").innerHTML = marken().map(m => `<option value="${esc(m)}">`).join("");
  f.kategori.innerHTML = `<option value="">–</option>` + alternativ(kategorier(), p?.kategori ?? gissaKategori(p?.namn));
  f.status.innerHTML = alternativ(STATUS, p?.status || "I lager");
  f.kopt.innerHTML = `<option value="">–</option>` + alternativ(KOPT, p?.kopt);
  f.saldPa.innerHTML = alternativ(SALD, p?.saldPa || "Vinted");
  for (const k of ["namn", "marke", "storlek", "inkopsdatum", "saljdatum", "anteckning"]) f[k].value = p?.[k] || "";
  for (const k of ["inkop", "salj", "kostnad"]) f[k].value = p?.[k] ?? "";
  if (!p?.inkopsdatum && !redigerar) f.inkopsdatum.value = "";
  $("bfnotis").innerHTML = notis || "";
  $("bfnotis").hidden = !notis;
  $("bfbild").hidden = !bild;
  if (bild) $("bfbild").src = bild;
  $("bftitel").textContent = redigerar ? "Ändra plagg" : "Lägg till plagg";
  $("bftabort").hidden = !redigerar;
  visaSalj();
  $("bfdialog").showModal();
  (f[fokus] || (notis ? f.inkop : f.namn)).focus();
}
function visaSalj(){
  const f = $("bfform"), sald = f.status.value === "Såld";
  $("bfform").querySelectorAll(".bfsald").forEach(e => e.hidden = !sald);
  if (sald && !f.saljdatum.value) f.saljdatum.value = idag();
  const v = tal(f.salj.value) - (tal(f.inkop.value) || 0) - (tal(f.kostnad.value) || 0);
  const r = $("bfresultat");
  if (sald && tal(f.salj.value) != null) {
    r.hidden = false;
    r.className = "bfresultat " + (v >= 0 ? "plus" : "minus");
    r.innerHTML = `Din vinst: <b>${tecken(v)}</b>` + (tal(f.salj.value) ? ` <span>(${Math.round(100 * v / tal(f.salj.value))} % av säljpriset)</span>` : "");
  } else r.hidden = true;
}
function sparaForm(e){
  e.preventDefault();
  const f = $("bfform");
  const p = {
    id: redigerar || (Date.now().toString(36) + Math.random().toString(36).slice(2, 6)),
    namn: f.namn.value.trim(), marke: f.marke.value.trim(), kategori: f.kategori.value, storlek: f.storlek.value.trim(),
    status: f.status.value, inkop: tal(f.inkop.value), kopt: f.kopt.value, inkopsdatum: f.inkopsdatum.value,
    salj: f.status.value === "Såld" ? tal(f.salj.value) : null, saldPa: f.status.value === "Såld" ? f.saldPa.value : "",
    saljdatum: f.status.value === "Såld" ? f.saljdatum.value : "", kostnad: f.status.value === "Såld" ? tal(f.kostnad.value) : null,
    anteckning: f.anteckning.value.trim(),
  };
  const gammal = poster.find(x => x.id === p.id);
  p.skapad = gammal?.skapad || new Date().toISOString();
  poster = gammal ? poster.map(x => x.id === p.id ? p : x) : [...poster, p];
  spara();
  $("bfdialog").close();
  (nyBild ? sparaBild(p.id, nyBild) : Promise.resolve()).then(rita);
}

// ---------- Skärmbild ----------
let tessLaddas = null;
function laddaTesseract(){
  if (window.Tesseract) return Promise.resolve();
  return tessLaddas ??= new Promise((ok, fel) => {
    const s = document.createElement("script");
    s.src = TESS; s.onload = ok;
    s.onerror = () => { tessLaddas = null; fel(new Error("ladda")); };
    document.head.appendChild(s);
  });
}
async function forbered(fil){
  // Gråskala, och mörkt läge görs om till ljust, så läser OCR:en bättre.
  const bild = await createImageBitmap(fil);
  const f = Math.min(1, 2000 / Math.max(bild.width, bild.height));
  const c = document.createElement("canvas");
  c.width = Math.round(bild.width * f); c.height = Math.round(bild.height * f);
  const g = c.getContext("2d");
  g.drawImage(bild, 0, 0, c.width, c.height);
  const px = g.getImageData(0, 0, c.width, c.height), d = px.data;
  let sum = 0;
  for (let i = 0; i < d.length; i += 4) sum += d[i] * 0.299 + d[i + 1] * 0.587 + d[i + 2] * 0.114;
  const mork = sum / (d.length / 4) < 110;
  for (let i = 0; i < d.length; i += 4) {
    let l = d[i] * 0.299 + d[i + 1] * 0.587 + d[i + 2] * 0.114;
    if (mork) l = 255 - l;
    d[i] = d[i + 1] = d[i + 2] = l;
  }
  g.putImageData(px, 0, 0);
  return c;
}
async function franSkarmbild(fil){
  const knapp = $("bfskarm"), text = knapp.textContent;
  knapp.disabled = true;
  const visa = t => { knapp.textContent = t; };
  const bildUrl = URL.createObjectURL(fil);
  try {
    visa("Läser skärmbilden …");
    await laddaTesseract();
    const worker = await Tesseract.createWorker(["swe", "eng"], 1, {
      logger: m => { if (m.status === "recognizing text") visa(`Läser skärmbilden … ${Math.round(m.progress * 100)} %`); },
    });
    const {data} = await worker.recognize(await forbered(fil));
    await worker.terminate();
    const t = window.BokforTolka(data.text, marken());
    const hittat = [t.pris != null && "pris", t.marke && "märke", t.storlek && "storlek"].filter(Boolean);
    const notis = hittat.length
      ? `Jag läste av skärmbilden (${hittat.join(", ")}). Kolla att allt stämmer och fyll i <b>vad du köpte plagget för</b>.`
      : `Jag hittade inte priset på skärmbilden. Fyll i det själv, och prova gärna en skärmbild där priset syns tydligt.`;
    const sale = {status: "Såld", salj: t.pris, saldPa: t.kalla || "Vinted", saljdatum: t.datum || idag()};
    const lager = hittaILager(t);
    if (lager) oppna({...lager, ...sale}, `Jag hittade <b>${esc(lager.namn || lager.marke)}</b> i ditt lager och markerar den som såld. Kolla att priset stämmer. Fel plagg? Tryck Avbryt och lägg till det själv.`, bildUrl, "salj");
    else oppna({...sale, namn: t.namn, marke: t.marke, storlek: t.storlek}, notis, bildUrl);
  } catch (e) {
    console.error(e);
    oppna({status: "Såld", saljdatum: idag()}, "Det gick inte att läsa skärmbilden just nu. Fyll i uppgifterna själv i stället.", bildUrl);
  } finally {
    knapp.disabled = false; knapp.textContent = text;
  }
}

// Snabbt sätt att markera ett plagg som sålt: bara priset och var.
let saltId = null, saltPa = "Vinted";
function oppnaSalt(p){
  saltId = p.id; saltPa = p.saldPa || "Vinted";
  $("bfsalttitel").textContent = `Sålt: ${p.namn || p.marke || "plagget"}`;
  $("bfsaltpris").value = "";
  $("bfsaltpa").innerHTML = SALD.map(v => `<button type="button" class="chip${v === saltPa ? " vald" : ""}" data-pa="${esc(v)}">${esc(v)}</button>`).join("");
  visaSaltVinst();
  $("bfsaltdialog").showModal();
  $("bfsaltpris").focus();
}
function visaSaltVinst(){
  const p = poster.find(x => x.id === saltId), pris = tal($("bfsaltpris").value), r = $("bfsaltvinst");
  if (pris == null || !p) { r.textContent = p?.inkop != null ? `Du köpte den för ${krText(p.inkop)}.` : ""; r.className = "bfresultat"; return; }
  const v = pris - (p.inkop || 0) - (p.kostnad || 0);
  r.className = "bfresultat " + (v >= 0 ? "plus" : "minus");
  r.innerHTML = `Din vinst: <b>${tecken(v)}</b>`;
}
function sparaSalt(e){
  e.preventDefault();
  const pris = tal($("bfsaltpris").value);
  if (pris == null) { $("bfsaltpris").focus(); return; }
  poster = poster.map(p => p.id === saltId ? {...p, status: "Såld", salj: pris, saldPa: saltPa, saljdatum: idag()} : p);
  spara(); rita();
  $("bfsaltdialog").close();
}

// Ett sålt plagg finns oftast redan i lagret: samma märke, och samma storlek om den syns.
function hittaILager(t){
  const n = x => String(x || "").toLowerCase().replace(/[^a-z0-9åäö]/g, "");
  if (!t.marke) return null;
  const kand = poster.filter(p => p.status !== "Såld" && n(p.marke) === n(t.marke));
  const sammaStl = kand.filter(p => t.storlek && n(p.storlek) === n(t.storlek));
  const lista = sammaStl.length ? sammaStl : t.storlek ? kand.filter(p => !p.storlek) : kand;
  return lista.sort((a, b) => (a.inkopsdatum || "").localeCompare(b.inkopsdatum || ""))[0] || null;
}

// ---------- Export och säkerhetskopia ----------
function laddaNer(namn, typ, innehall){
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([innehall], {type: typ}));
  a.download = namn; document.body.appendChild(a); a.click(); a.remove();
}
function exportera(){
  const kol = [["namn", "Plagg"], ["marke", "Märke"], ["kategori", "Kategori"], ["storlek", "Storlek"], ["status", "Status"],
    ["kopt", "Köpt på"], ["inkopsdatum", "Inköpsdatum"], ["inkop", "Inköp (kr)"], ["saldPa", "Såld på"], ["saljdatum", "Säljdatum"],
    ["salj", "Säljpris (kr)"], ["kostnad", "Frakt och avgifter (kr)"], ["vinst", "Vinst (kr)"], ["anteckning", "Anteckning"]];
  const cell = v => { const s = typeof v === "number" ? String(v).replace(".", ",") : String(v ?? ""); return /[;"\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const rader = [kol.map(k => k[1]).join(";"), ...poster.map(p => kol.map(([k]) => cell(k === "vinst" ? vinst(p) : p[k])).join(";"))];
  laddaNer(`bokforing-${idag()}.csv`, "text/csv;charset=utf-8", "﻿" + rader.join("\r\n"));
}

function init(){
  if (!$("bfform")) return;
  las(); rita();
  $("bfny").addEventListener("click", () => oppna(null));
  $("bfskarm").addEventListener("click", () => $("bfskarmfil").click());
  $("bfskarmfil").addEventListener("change", e => { const f = e.target.files[0]; e.target.value = ""; if (f) franSkarmbild(f); });
  $("bfform").addEventListener("submit", sparaForm);
  $("bfform").addEventListener("input", e => {
    // Kategorin följer namnet tills man själv väljer en.
    if (e.target.name === "namn" && !$("bfform").kategori.dataset.vald) { const k = gissaKategori(e.target.value); if (k) $("bfform").kategori.value = k; }
    if (e.target.name === "kategori") $("bfform").kategori.dataset.vald = "1";
    visaSalj();
  });
  $("bfform").addEventListener("change", visaSalj);
  $("bfavbryt").addEventListener("click", () => $("bfdialog").close());
  $("bftabort").addEventListener("click", () => {
    if (!confirm("Ta bort plagget från bokföringen?")) return;
    const id = redigerar;
    poster = poster.filter(p => p.id !== id); spara(); taBortBild(id); rita(); $("bfdialog").close();
  });
  $("bfformbildknapp").addEventListener("click", () => $("bfformbildfil").click());
  $("bfformbildfil").addEventListener("change", e => { const f = e.target.files[0]; e.target.value = ""; if (!f) return; nyBild = f; visaFormBild(URL.createObjectURL(f)); });
  let bildFor = null;
  $("bfvaror").addEventListener("click", e => {
    const k = e.target.closest("[data-bild]");
    if (k) { bildFor = k.dataset.bild; return $("bfbildfil").click(); }
    const s = e.target.closest("[data-salj]");
    if (s) return oppnaSalt(poster.find(x => x.id === s.dataset.salj));
    const v = e.target.closest(".bfvara[data-id]"); if (v) oppna(poster.find(p => p.id === v.dataset.id));
  });
  $("bfbildfil").addEventListener("change", async e => { const f = e.target.files[0]; e.target.value = ""; if (f && bildFor) { await sparaBild(bildFor, f); ritaVaror(); } });
  $("bfmer").addEventListener("click", e => { if (e.target.closest("#bfvisafler")) { visa += 12; ritaVaror(); } });
  $("bfsok").addEventListener("input", e => { sok = e.target.value; visa = 12; ritaVaror(); });
  $("bffilter").addEventListener("click", e => { const b = e.target.closest("[data-f]"); if (!b) return; filter = b.dataset.f; visa = 12; try { localStorage.setItem("bokforing-filter", filter); } catch {} ritaVaror(true); });
  $("bfperiod").addEventListener("click", e => { const b = e.target.closest("[data-p]"); if (!b) return; period = b.dataset.p; try { localStorage.setItem("bokforing-period", period); } catch {} ritaTopp(); });
  $("bfutv").addEventListener("click", e => { const b = e.target.closest("[data-u]"); if (!b) return; utv = b.dataset.u; try { localStorage.setItem("bokforing-utv", utv); } catch {}
    $("bfutv").querySelectorAll("[data-u]").forEach(x => x.classList.toggle("vald", x === b)); ritaUtveckling(); });
  let storlek = 0;
  addEventListener("resize", () => { clearTimeout(storlek); storlek = setTimeout(ritaUtveckling, 150); });
  // Diagrammet behöver veta hur brett det är, så det ritas om när bokföringen visas.
  new IntersectionObserver(e => { if (e.some(x => x.isIntersecting)) ritaUtveckling(); }).observe($("bfdiagram"));
  laddaBilder();
  $("bfsaltform").addEventListener("submit", sparaSalt);
  $("bfsaltpris").addEventListener("input", visaSaltVinst);
  $("bfsaltavbryt").addEventListener("click", () => $("bfsaltdialog").close());
  $("bfsaltpa").addEventListener("click", e => { const b = e.target.closest("[data-pa]"); if (!b) return; saltPa = b.dataset.pa; $("bfsaltpa").querySelectorAll("[data-pa]").forEach(x => x.classList.toggle("vald", x === b)); });
  $("bfexport").addEventListener("click", exportera);
  $("bfkopia").addEventListener("click", async () => {
    const bilder = {};
    for (const p of poster) if (BILD[p.id]) {
      try { const b = await bildlager("get", p.id); if (b) bilder[p.id] = await new Promise(ok => { const r = new FileReader(); r.onload = () => ok(r.result); r.readAsDataURL(b); }); } catch {}
    }
    laddaNer(`bokforing-sakerhetskopia-${idag()}.json`, "application/json", JSON.stringify({poster, bilder}, null, 1));
  });
  $("bfaterstall").addEventListener("click", () => $("bfaterfil").click());
  $("bfaterfil").addEventListener("change", async e => {
    const f = e.target.files[0]; e.target.value = ""; if (!f) return;
    try {
      const json = JSON.parse(await f.text());
      // Äldre säkerhetskopior är bara listan med plagg, nyare har bilderna med.
      const data = Array.isArray(json) ? json : json?.poster, bilder = Array.isArray(json) ? {} : json?.bilder || {};
      if (!Array.isArray(data)) throw 0;
      const finns = new Set(poster.map(p => p.id));
      const nya = data.filter(p => p && p.id && !finns.has(p.id));
      poster = [...poster, ...nya]; spara();
      for (const p of nya) if (typeof bilder[p.id] === "string" && bilder[p.id].startsWith("data:image/")) {
        try { const b = await (await fetch(bilder[p.id])).blob(); await bildlager("put", b, p.id); } catch {}
      }
      await laddaBilder(); rita();
      alert(nya.length ? `${nya.length} plagg lades till från säkerhetskopian.` : "Allt i säkerhetskopian fanns redan.");
    } catch { alert("Filen gick inte att läsa. Välj en säkerhetskopia som du laddat ner härifrån."); }
  });
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();

// Tolkar texten från en skärmbild av en försäljning (Vinted, Tradera, Plick).
// Fristående funktion så att den går att testa utan webbläsare.
(function (rot) {
const MANADER = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
const INTE_PRIS = /köparskydd|skydd|avgift|frakt|porto|leverans|totalt|summa|moms|rabatt|saldo|plånbok|utbetal|tillgängligt|bud\b|budgivning/i;
const PRISORD = /slutpris|såld för|sålt för|vinnande bud|varans pris|artikelpris|pris\b|price/i;
const BRUS = /^(\d{1,2}[:.]\d{2}|beställning|order|sålda?|meddelanden?|inkorg|översikt|detaljer|kvitto|betalning.*|frakt.*|leverans.*|spåra.*|tillbaka|vinted|tradera|plick|kr|sek)$/i;
const norm = s => s.toLowerCase().replace(/[^a-z0-9åäö]/g, "");

function belopp(rad){
  const ut = [];
  const re = /(?:(?:SEK|kr)\s*)?(\d{1,3}(?:[ . ]\d{3})+|\d+)(?:[,.](\d{2}))?\s*(?:kr|SEK|:-)|(?:SEK|kr)\s*(\d{1,3}(?:[ . ]\d{3})+|\d+)(?:[,.](\d{2}))?/gi;
  let m;
  while ((m = re.exec(rad))) {
    const hel = (m[1] || m[3]).replace(/[ . ]/g, ""), dec = m[2] || m[4] || "0";
    const v = parseInt(hel, 10) + parseInt(dec, 10) / 100;
    if (v > 0 && v < 200000) ut.push(v);
  }
  return ut;
}
function tolka(text, marken){
  const rader = String(text || "").split(/\r?\n/).map(r => r.replace(/\s+/g, " ").trim()).filter(Boolean);
  const hel = rader.join("\n"), ut = {namn: "", marke: "", storlek: "", pris: null, datum: "", kalla: ""};
  ut.kalla = /tradera/i.test(hel) ? "Tradera" : /plick/i.test(hel) ? "Plick" : /vinted|köparskydd/i.test(hel) ? "Vinted" : "";

  // Pris: först rader som säger att det är priset, sedan första beloppet som inte är frakt, avgift eller totalt.
  let pris = null;
  for (let i = 0; i < rader.length && pris == null; i++) {
    if (!PRISORD.test(rader[i]) || INTE_PRIS.test(rader[i])) continue;
    const b = belopp(rader[i]).concat(i + 1 < rader.length && !INTE_PRIS.test(rader[i + 1]) ? belopp(rader[i + 1]) : []);
    if (b.length) pris = b[0];
  }
  if (pris == null) for (const r of rader) { if (INTE_PRIS.test(r)) continue; const b = belopp(r); if (b.length) { pris = b[0]; break; } }
  ut.pris = pris;

  // Märke: det längsta kända märket som finns i texten.
  const nh = norm(hel);
  for (const m of marken || []) { const n = norm(m); if (n.length >= 3 && nh.includes(n) && n.length > norm(ut.marke).length) ut.marke = m; }

  // Storlek
  const s = hel.match(/storlek[:\s]*((?:W\s?\d{2}(?:\s?L\s?\d{2})?)|(?:XXXL|XXL|XL|XS|XXS|[SML])\b|\d{2}(?:[,.]5)?\b)/i)
    || hel.match(/\b(W\s?\d{2}\s?L\s?\d{2})\b/i)
    || hel.match(/(?:^|[·|•,\/\n]\s*)(XXXL|XXL|XL|XS|XXS|S|M|L)(?=\s*(?:[·|•,\/\n]|$))/);
  if (s) ut.storlek = s[1].toUpperCase().replace(/\s+/g, " ");

  // Datum
  let d = hel.match(/\b(20\d{2})-(\d{2})-(\d{2})\b/);
  if (d) ut.datum = `${d[1]}-${d[2]}-${d[3]}`;
  else if ((d = hel.match(/\b(\d{1,2})\s+(jan|feb|mar|apr|maj|jun|jul|aug|sep|okt|nov|dec)[a-zé]*\.?(?:\s+(20\d{2}))?/i))) {
    const ar = d[3] || String(new Date().getFullYear());
    ut.datum = `${ar}-${String(MANADER.indexOf(d[2].toLowerCase().slice(0, 3)) + 1).padStart(2, "0")}-${d[1].padStart(2, "0")}`;
  } else if ((d = hel.match(/\b(\d{1,2})[\/.](\d{1,2})[\/.](20\d{2})\b/))) ut.datum = `${d[3]}-${d[2].padStart(2, "0")}-${d[1].padStart(2, "0")}`;
  else if (/\bigår\b/i.test(hel)) { const x = new Date(Date.now() - 864e5); ut.datum = x.toLocaleDateString("sv-SE"); }

  // Namn: raden med märket, annars första raden som ser ut som en annonsrubrik.
  const ok = r => /[a-zåäö]{3}/i.test(r) && !BRUS.test(r) && !belopp(r).length && !INTE_PRIS.test(r) && !/storlek|skick|^du |har sålt|köpare|säljare/i.test(r) && r.length <= 80;
  const mn = norm(ut.marke);
  ut.namn = (mn && rader.find(r => ok(r) && norm(r).includes(mn))) || rader.find(r => ok(r) && r.split(" ").length >= 2) || "";
  return ut;
}
rot.BokforTolka = tolka;
if (typeof module !== "undefined") module.exports = tolka;
})(typeof window !== "undefined" ? window : globalThis);
