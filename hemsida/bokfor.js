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
let filter = "alla", period = "allt";
try { filter = localStorage.getItem("bokforing-filter") || "alla"; period = localStorage.getItem("bokforing-period") || "allt"; } catch {}

const vinst = p => p.status === "Såld" && p.salj != null ? p.salj - (p.inkop || 0) - (p.kostnad || 0) : null;
function iPeriod(p){
  if (period === "allt") return true;
  const d = p.status === "Såld" ? p.saljdatum : p.inkopsdatum;
  if (!d) return false;
  const nu = idag();
  return period === "manad" ? d.slice(0, 7) === nu.slice(0, 7) : d.slice(0, 4) === nu.slice(0, 4);
}

// ---------- Ritning ----------
function rita(){
  const urval = poster.filter(iPeriod);
  const salda = urval.filter(p => p.status === "Såld" && p.salj != null);
  const summaVinst = salda.reduce((s, p) => s + vinst(p), 0), saltFor = salda.reduce((s, p) => s + p.salj, 0);
  const lager = poster.filter(p => p.status !== "Såld");
  const v = $("bfvinst");
  v.textContent = salda.length ? tecken(summaVinst) : "0 kr";
  v.className = "tal " + (summaVinst > 0 ? "plus" : summaVinst < 0 ? "minus" : "");
  $("bfvinstinfo").textContent = salda.length && saltFor ? `${Math.round(100 * summaVinst / saltFor)} % av det du sålt för` : "när du har sålt något";
  $("bfsalt").textContent = krText(saltFor);
  $("bfsaltinfo").textContent = salda.length === 1 ? "1 sålt plagg" : `${salda.length} sålda plagg`;
  $("bflager").textContent = lager.length === 1 ? "1 plagg" : `${lager.length} plagg`;
  $("bflagerinfo").textContent = lager.length ? `inköpt för ${krText(lager.reduce((s, p) => s + (p.inkop || 0), 0))}` : "inget i lager";
  const snitt = salda.length ? summaVinst / salda.length : null;
  $("bfsnitt").textContent = snitt == null ? "–" : tecken(snitt);
  $("bffilter").querySelectorAll("[data-f]").forEach(b => b.classList.toggle("vald", b.dataset.f === filter));
  $("bfperiod").querySelectorAll("[data-p]").forEach(b => b.classList.toggle("vald", b.dataset.p === period));

  const lista = urval.filter(p => filter === "alla" || p.status === filter)
    .sort((a, b) => (b.saljdatum || b.inkopsdatum || b.skapad || "").localeCompare(a.saljdatum || a.inkopsdatum || a.skapad || ""));
  const t = $("bftabell");
  if (!poster.length) {
    t.innerHTML = `<tbody><tr><td class="tomt">Här hamnar allt du köper och säljer. Börja med att lägga till ett plagg, eller ta en skärmbild när du har sålt något på Vinted eller Tradera.</td></tr></tbody>`;
    return;
  }
  if (!lista.length) { t.innerHTML = `<tbody><tr><td class="tomt">Inga plagg här än.</td></tr></tbody>`; return; }
  t.innerHTML = `<thead><tr><th>Plagg</th><th>Status</th><th>Inköp</th><th class="dolj-mobil">Såld för</th><th>Vinst</th><th class="dolj-mobil">Datum</th></tr></thead><tbody>` +
    lista.map(p => {
      const vi = vinst(p), extra = [p.marke, p.storlek && "stl " + p.storlek].filter(Boolean).join(" · ");
      return `<tr data-id="${esc(p.id)}">
        <td><div class="bfnamn"><b>${esc(p.namn || p.marke || "Plagg")}</b>${extra ? `<small>${esc(extra)}</small>` : ""}</div></td>
        <td><span class="bfstatus s${STATUS.indexOf(p.status)}">${esc(p.status)}</span></td>
        <td class="tal">${krText(p.inkop)}</td>
        <td class="tal dolj-mobil">${p.status === "Såld" ? krText(p.salj) : "–"}</td>
        <td class="tal ${vi > 0 ? "plus" : vi < 0 ? "minus" : ""}">${p.status === "Såld" ? (vi == null ? "–" : tecken(vi)) : `<button class="knapp bfsaltknapp" data-salj="${esc(p.id)}">Sålt</button>`}</td>
        <td class="dolj-mobil svag">${esc((p.status === "Såld" ? p.saljdatum : p.inkopsdatum) || "")}</td></tr>`;
    }).join("") + "</tbody>";
}

// ---------- Formuläret ----------
function marken(){
  const s = new Set(VANLIGA_MARKEN);
  try { for (const kalla of Object.values(B?.marke || {})) for (const kat of Object.values(kalla || {})) for (const m of Object.keys(kat || {})) s.add(m); } catch {}
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
let redigerar = null;
function oppna(p, notis, bild, fokus){
  redigerar = p?.id || null;
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
  spara(); rita();
  $("bfdialog").close();
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
    poster = poster.filter(p => p.id !== redigerar); spara(); rita(); $("bfdialog").close();
  });
  $("bftabell").addEventListener("click", e => {
    const s = e.target.closest("[data-salj]");
    if (s) return oppnaSalt(poster.find(x => x.id === s.dataset.salj));
    const tr = e.target.closest("tr[data-id]"); if (tr) oppna(poster.find(p => p.id === tr.dataset.id)); });
  $("bffilter").addEventListener("click", e => { const b = e.target.closest("[data-f]"); if (!b) return; filter = b.dataset.f; try { localStorage.setItem("bokforing-filter", filter); } catch {} rita(); });
  $("bfperiod").addEventListener("click", e => { const b = e.target.closest("[data-p]"); if (!b) return; period = b.dataset.p; try { localStorage.setItem("bokforing-period", period); } catch {} rita(); });
  $("bfsaltform").addEventListener("submit", sparaSalt);
  $("bfsaltpris").addEventListener("input", visaSaltVinst);
  $("bfsaltavbryt").addEventListener("click", () => $("bfsaltdialog").close());
  $("bfsaltpa").addEventListener("click", e => { const b = e.target.closest("[data-pa]"); if (!b) return; saltPa = b.dataset.pa; $("bfsaltpa").querySelectorAll("[data-pa]").forEach(x => x.classList.toggle("vald", x === b)); });
  $("bfexport").addEventListener("click", exportera);
  $("bfkopia").addEventListener("click", () => laddaNer(`bokforing-sakerhetskopia-${idag()}.json`, "application/json", JSON.stringify(poster, null, 1)));
  $("bfaterstall").addEventListener("click", () => $("bfaterfil").click());
  $("bfaterfil").addEventListener("change", async e => {
    const f = e.target.files[0]; e.target.value = ""; if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      if (!Array.isArray(data)) throw 0;
      const finns = new Set(poster.map(p => p.id));
      const nya = data.filter(p => p && p.id && !finns.has(p.id));
      poster = [...poster, ...nya]; spara(); rita();
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
