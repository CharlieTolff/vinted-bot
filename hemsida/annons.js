// Skriv beskrivning: gör en färdig annonstext att kopiera in på Vinted eller
// Tradera. Strukturen: inledning, punkter med skick, material, detaljer och
// mått, ärlig rad om eventuella fel och en kort avslutning.
// Bilder: texten på lappen läses med Tesseract (OCR) i webbläsaren för märke,
// storlek och material, och färgen tas från bilden på plagget. Inget skickas
// någonstans.
(rot => {
const MATERIAL = [[/^(merino)/, "merinoull"], [/^(cotton|coton|baumwolle|bomull|algod)/, "bomull"], [/^(wool|wolle|laine|ull|lana)/, "ull"],
  [/^(cashmere|kaschmir|kashmir|cachemire)/, "kashmir"], [/^(polyester|polyest)/, "polyester"], [/^(elastan|spandex|lycra)/, "elastan"],
  [/^(viscose|viskos|viscosa)/, "viskos"], [/^(polyamid|nylon)/, "polyamid"], [/^(linen|leinen|lin$|linne)/, "linne"], [/^(silk|seide|soie|siden)/, "siden"],
  [/^(acryl|akryl)/, "akryl"], [/^(leather|leder|cuir|läder)/, "läder"], [/^(lyocell|tencel)/, "lyocell"], [/^(modal)/, "modal"], [/^(down|daun|dun)$/, "dun"], [/^(feather|federn|fjäder)/, "fjäder"]];
const norm = s => String(s || "").toLowerCase().normalize("NFD").replace(/[^a-z0-9]/g, "");
// ---------- Märket på lappen ----------
// Samma nyckel som marken.py: "Samsøe & Samsøe" -> ["samsoe", "samsoe"] ("och" räknas inte, OCR tappar ofta &).
const nyckel = s => (String(s || "").toLowerCase().replace(/ø/g, "o").replace(/æ/g, "ae").replace(/ß/g, "ss")
  .normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/['’´`]/g, "").match(/[a-z0-9]+/g) || []).filter(t => t !== "and");
function avstand(a, b, max){
  // Levenshtein, men ger upp (max + 1) så fort det blir för långt.
  if (Math.abs(a.length - b.length) > max) return max + 1;
  let f = Array.from({length: b.length + 1}, (_, j) => j);
  for (let i = 1; i <= a.length; i++) {
    const n = [i]; let minst = i;
    for (let j = 1; j <= b.length; j++) { n[j] = Math.min(f[j] + 1, n[j - 1] + 1, f[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); minst = Math.min(minst, n[j]); }
    if (minst > max) return max + 1;
    f = n;
  }
  return f[b.length];
}
// Märken som också är vanliga ord (Only, Next, Selected …) räknas bara när de står stort på lappen.
const VANLIGA_ORD = new Set(["cotton", "wool", "made", "size", "linen", "silk", "down", "wash", "dry", "clean", "only", "next", "house", "hope", "sand",
  "tiger", "on", "frame", "basic", "classic", "denim", "jeans", "sport", "original", "premium", "selected", "reserved", "champion", "guess", "kappa",
  "lee", "gap", "mango", "jordan", "represent", "palace", "supreme", "columbia", "velour", "jules", "mustang", "playboy", "needles", "kapital",
  "converse", "edwin", "riley", "brothers", "divided", "celio", "schott", "veja", "asket", "logg", "casablanca", "polo", "hugo", "nudie"]);
let alias = {};  // variant -> märke (BOSS -> Hugo Boss), från marken-alias.json
function sattAlias(a){ alias = a || {}; }
// ord: Tesseracts ord [{t: text, c: säkerhet, h: höjd}] för en bild. Ger {marke, poang} eller null.
function marketIOrd(ord, marken){
  const finns = new Map();
  for (const m of marken || []) { const k = nyckel(m).join(""); if (k) finns.set(k, m); }
  for (const [v, m] of Object.entries(alias)) { const k = nyckel(v).join(""), namn = finns.get(nyckel(m).join("")); if (k && namn && !finns.has(k)) finns.set(k, namn); }
  const st = [];
  for (const o of ord || []) for (const t of nyckel(o.t)) st.push({t, h: o.h || 1, c: o.c ?? 90});
  const hoga = st.filter(x => x.c >= 40 && x.t.length >= 2).map(x => x.h).sort((a, b) => b - a);
  const maxH = hoga[0] || 1;
  const nycklar = [...finns.keys()].filter(k => k.length >= 5);
  let bast = null;
  for (let i = 0; i < st.length; i++) {
    for (let n = 1; n <= 4 && i + n <= st.length; n++) {
      const del = st.slice(i, i + n), k = del.map(x => x.t).join("");
      const storlek = del.reduce((s, x) => s + x.h, 0) / n / maxH, sak = del.reduce((s, x) => s + x.c, 0) / n;
      let namn = finns.get(k), exakt = true;
      if (!namn && k.length >= 5 && sak >= 30 && storlek >= 0.5) {
        // Ett eller två felläsningar (RALPH LAUREM, NUDlE) är okej på långa namn.
        const tal = k.length >= 10 ? 2 : 1;
        let b = tal + 1;
        for (const v of nycklar) { const a = avstand(k, v, tal); if (a < b) { b = a; namn = finns.get(v); } }
        if (b > tal) namn = null;
        exakt = false;
      }
      if (!namn) continue;
      const nk = nyckel(namn).join("");
      // Korta namn (COS, RRL) kan lika gärna vara brus, så de måste stå stort och tydligt.
      if (k.length < 3 || (k.length === 3 && !(exakt && storlek >= 0.7 && sak >= 85))) continue;
      if ((VANLIGA_ORD.has(k) || VANLIGA_ORD.has(nk)) && !(exakt && storlek >= 0.6)) continue;
      const poang = Math.min(k.length, 12) * storlek * (exakt ? 1 : 0.6) * (sak >= 50 ? 1 : 0.7);
      if (!bast || poang > bast.poang) bast = {marke: namn, poang, sak: Math.round(sak), exakt, storlek: Math.round(storlek * 100) / 100, las: del.map(x => x.t).join(" ")};
    }
  }
  // Under 2,5 poäng är det oftast brus från tyget (testat på riktiga plaggbilder), inte ett märke.
  return bast && bast.poang >= 2.5 ? bast : null;
}
// Texten (och orden, om de finns) från en eller flera bilder.
function tolka(text, marken, ordPerBild){
  const rader = String(text || "").split(/\r?\n/).map(r => r.replace(/\s+/g, " ").trim()).filter(Boolean);
  const hel = rader.join("\n"), ut = {marke: "", storlek: "", material: ""};
  const bilder = ordPerBild && ordPerBild.length ? ordPerBild : [rader.flatMap(r => r.split(" ").map(t => ({t, h: 1, c: 90})))];
  const bast = bilder.map(o => marketIOrd(o, marken)).filter(Boolean).sort((a, b) => b.poang - a.poang)[0];
  if (bast) ut.marke = bast.marke;
  const s = hel.match(/(?:size|storlek|taille|gr(?:ö|o)(?:ß|ss)e|talla|gr\.)[:\s]*(W\s?\d{2}(?:\s?L\s?\d{2})?|XXXL|XXL|XL|XS|XXS|[SML]\b|\d{2,3}\b)/i)
    || hel.match(/\b(W\s?\d{2}\s?L\s?\d{2})\b/i)
    || hel.match(/^[^A-Za-z0-9]*(XXXL|XXL|XL|XS|XXS|S|M|L)(?=[\s\/|·.,-]|$)/m)
    || hel.match(/\b(?:EUR?|EU)\s?(\d{2})\b/);
  if (s) ut.storlek = s[1].toUpperCase().replace(/\s+/g, " ");
  // Lappar upprepar samma sak på flera språk, så sluta när det blir 100 %.
  const delar = [], sett = new Set();
  let summa = 0;
  for (const m of hel.matchAll(/(\d{1,3})\s*%\s*([A-Za-zÅÄÖåäöéÉüÜ]+)/g)) {
    const p = +m[1], ord = m[2].toLowerCase();
    const hit = MATERIAL.find(([r]) => r.test(ord));
    if (summa >= 100) break;
    if (!hit || p < 1 || p > 100 || summa + p > 100 || sett.has(hit[1])) continue;
    sett.add(hit[1]); delar.push([p, hit[1]]); summa += p;
  }
  if (delar.length) ut.material = delar.sort((a, b) => b[0] - a[0]).map(([p, n]) => `${p} % ${n}`).join(", ");
  return ut;
}
function fargnamn(r, g, b){
  r /= 255; g /= 255; b /= 255;
  const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, d = mx - mn;
  const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
  let h = 0;
  if (d) h = mx === r ? 60 * (((g - b) / d) % 6) : mx === g ? 60 * ((b - r) / d + 2) : 60 * ((r - g) / d + 4);
  if (h < 0) h += 360;
  if (l < 0.13) return "Svart";
  if (s < 0.14 || (s < 0.22 && l < 0.25)) return l > 0.86 ? "Vit" : l > 0.68 ? "Ljusgrå" : l < 0.3 ? "Mörkgrå" : "Grå";
  if (l > 0.9) return "Vit";
  if (h < 14 || h >= 345) return l < 0.3 ? "Vinröd" : l > 0.72 ? "Rosa" : "Röd";
  if (h < 45) return (l > 0.68 && s < 0.6) || (l > 0.6 && s < 0.4) ? "Beige" : l < 0.42 || s < 0.45 ? "Brun" : "Orange";
  if (h < 68) return l > 0.65 && s < 0.6 ? "Beige" : l < 0.4 || s < 0.4 ? "Olivgrön" : "Gul";
  if (h < 165) return l < 0.28 ? "Mörkgrön" : s < 0.3 ? "Olivgrön" : l > 0.68 ? "Ljusgrön" : "Grön";
  if (h < 200) return l < 0.3 ? "Petrol" : "Turkos";
  if (h < 250) return l < 0.3 ? "Marinblå" : l > 0.68 ? "Ljusblå" : "Blå";
  if (h < 290) return l > 0.7 ? "Ljuslila" : "Lila";
  return l < 0.3 ? "Vinröd" : "Rosa";
}
rot.AnnonsTolka = tolka;
rot.AnnonsAlias = sattAlias;
rot.AnnonsFarg = fargnamn;
if (typeof document === "undefined") { if (typeof module !== "undefined") module.exports = {tolka, fargnamn, marketIOrd, sattAlias, nyckel}; return; }
const $ = id => document.getElementById(id);
const SKICK = {
  "Ny med lappar": "Ny med lappar kvar, aldrig använd",
  "Som ny": "Som ny, knappt använd",
  "Mycket bra": "Mycket bra, använd några gånger",
  "Bra": "Bra, använd men välskött",
  "Okej": "Okej, tydligt använd",
};
let skick = "Mycket bra";

function text(){
  const v = id => $(id).value.trim();
  const plagg = v("abplagg").toLowerCase(), marke = v("abmarke"), stl = v("abstorlek"), farg = v("abfarg").toLowerCase();
  const material = v("abmaterial"), detaljer = v("abdetaljer"), fel = v("abfel"), varfor = v("abvarfor");
  const langd = v("ablangd"), bredd = v("abbredd");
  if (!plagg && !marke) return "";
  const vad = [farg, plagg || "plagg"].filter(Boolean).join(" ");
  const artikel = /jeans|byxor|shorts|chinos|skor|sneakers|kängor|boots|loafers|vantar|handskar/.test(plagg) ? "ett par" : /linne|set|bälte|halsband|armband/.test(plagg) ? "ett" : "en";
  const rader = [`Säljer ${artikel} ${vad}${marke ? ` från ${marke}` : ""}${stl ? ` i storlek ${stl}` : ""}.`, ""];
  rader.push(`• Skick: ${SKICK[skick]}${fel ? "" : ", inga fläckar eller hål"}`);
  if (material) rader.push(`• Material: ${material}`);
  if (detaljer) rader.push(`• Detaljer: ${detaljer}`);
  const matt = [langd && `längd ${langd} cm`, bredd && `bredd armhåla till armhåla ${bredd} cm`].filter(Boolean);
  if (matt.length) rader.push(`• Mått (mätt liggande): ${matt.join(", ")}`);
  if (fel) rader.push(`• Att veta: ${fel} (syns på bilderna)`);
  if (varfor) rader.push("", varfor.replace(/^./, c => c.toUpperCase()).replace(/[^.!?]$/, m => m + "."));
  const slut = [];
  if ($("absamkop").checked) slut.push("Fler plagg på min profil, samköp ger rabatt.");
  slut.push("Skickas snabbt" + ($("abemoji").checked ? " ✨" : "."));
  rader.push("", ...slut);
  return rader.join("\n");
}
function rita(){
  const t = text();
  $("abtext").value = t;
  $("abkopiera").disabled = !t;
  $("abtom").hidden = !!t;
  $("abtext").hidden = !t;
  $("abskick").querySelectorAll("[data-s]").forEach(b => b.classList.toggle("vald", b.dataset.s === skick));
}
async function kopiera(){
  const t = $("abtext").value, knapp = $("abkopiera");
  try { await navigator.clipboard.writeText(t); }
  catch { $("abtext").select(); document.execCommand("copy"); }
  knapp.textContent = "Kopierad ✓";
  setTimeout(() => { knapp.textContent = "Kopiera beskrivningen"; }, 1800);
}
// ---------- Fyll i från bilder ----------
const TESS = "https://cdn.jsdelivr.net/npm/tesseract.js@5.1.1/dist/tesseract.min.js";
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
function rita2(bild, max, mitten){
  // mitten: bara mittersta 60 %, där lappen brukar vara (då blir texten större).
  const sx = mitten ? Math.round(bild.width * 0.2) : 0, sy = mitten ? Math.round(bild.height * 0.2) : 0;
  const sw = bild.width - 2 * sx, sh = bild.height - 2 * sy;
  const f = Math.min(1, max / Math.max(sw, sh));
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(sw * f)); c.height = Math.max(1, Math.round(sh * f));
  const g = c.getContext("2d", {willReadFrequently: true});
  g.drawImage(bild, sx, sy, sw, sh, 0, 0, c.width, c.height);
  return [c, g];
}
function gra(bild){
  // Gråskala, och ljus text på mörk lapp görs om till mörk text på ljus.
  const [c, g] = rita2(bild, 2000);
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
function troskel(bild, ljus, mitten){
  // Svart där pixeln är tydligt mörkare (ljus: ljusare) än omgivningen, annars vitt. Då försvinner
  // tyget runt lappen och bara texten blir kvar, även på färgade och mörka lappar.
  const [c, g] = rita2(bild, 2000, mitten), w = c.width, h = c.height, R = 25, C = 12;
  const px = g.getImageData(0, 0, w, h), d = px.data, l = new Float32Array(w * h), I = new Float64Array((w + 1) * (h + 1));
  for (let i = 0; i < w * h; i++) { const v = d[4 * i] * 0.299 + d[4 * i + 1] * 0.587 + d[4 * i + 2] * 0.114; l[i] = ljus ? 255 - v : v; }
  for (let y = 0; y < h; y++) { let rad = 0; for (let x = 0; x < w; x++) { rad += l[y * w + x]; I[(y + 1) * (w + 1) + x + 1] = I[y * (w + 1) + x + 1] + rad; } }
  for (let y = 0; y < h; y++) {
    const y0 = Math.max(0, y - R), y1 = Math.min(h, y + R + 1);
    for (let x = 0; x < w; x++) {
      const x0 = Math.max(0, x - R), x1 = Math.min(w, x + R + 1);
      const m = (I[y1 * (w + 1) + x1] - I[y0 * (w + 1) + x1] - I[y1 * (w + 1) + x0] + I[y0 * (w + 1) + x0]) / ((y1 - y0) * (x1 - x0));
      const i = 4 * (y * w + x); d[i] = d[i + 1] = d[i + 2] = l[y * w + x] < m - C ? 0 : 255; d[i + 3] = 255;
    }
  }
  g.putImageData(px, 0, 0);
  return c;
}
function vrid(c, grader){
  const r = document.createElement("canvas"); r.width = c.height; r.height = c.width;
  const g = r.getContext("2d"); g.translate(r.width / 2, r.height / 2); g.rotate(grader * Math.PI / 180); g.drawImage(c, -c.width / 2, -c.height / 2);
  return r;
}
const ordFran = data => (data.words || []).map(o => ({t: o.text, c: o.confidence, h: o.bbox ? o.bbox.y1 - o.bbox.y0 : 1}));
// Försöken när märket inte syns direkt, i den ordning som gav flest rätt märken per sekund på testlapparna:
// g = gråskala, c = mittersta delen, t = hela bilden, 0/1 = mörk/ljus text, r90/r270 = vriden en kvarts varv.
// 3 = vanlig sida, 11 = utspridd text. Inget av försöken gav fel märke på testlapparna.
const FORSOK = [["gr90", "3"], ["gr270", "3"], ["c0", "3"], ["c1", "3"], ["c0", "11"], ["t1", "11"], ["t0", "11"], ["c1", "11"],
  ["c0r90", "3"], ["c0r270", "3"], ["c1r90", "11"], ["c1r270", "11"]];
const LAS_TID = 20000;  // ms för alla extraförsök: längre än så väntar ingen, och då är bilden oftast för suddig ändå
const TAK_FORSTA = 20000, TAK_FORSOK = 8000;  // ms för en enda läsning, sedan ges den upp
// Läser en bild men ger upp efter ms (stickat tyg kan ta en minut). Då startas en ny OCR i stället.
async function lasMedTak(w, bild, ms){
  let timer;
  const jobb = w.worker.recognize(bild);
  jobb.catch(() => {});
  const r = await Promise.race([jobb, new Promise(ok => { timer = setTimeout(() => ok(null), ms); })]);
  clearTimeout(timer);
  if (r) return r;
  await w.worker.terminate().catch(() => {});
  w.worker = await Tesseract.createWorker(["swe", "eng"], 1);
  w.psm = "3";
  return null;
}
async function lasMarke(w, bild, marken, visa, tyg){
  const klar = {}, start = Date.now();
  const variant = v => {
    if (klar[v]) return klar[v];
    const [bas, grader] = v.split("r");
    return klar[v] = grader ? vrid(variant(bas), +grader) : bas === "g" ? gra(bild) : troskel(bild, bas[1] === "1", bas[0] === "c");
  };
  try {
    for (let i = 0; i < FORSOK.length && Date.now() - start < LAS_TID; i++) {
      const [v, p] = FORSOK[i];
      // Mycket "text" betyder att tyget läses som bokstäver. Då provas bara mitten av bilden (där lappen är).
      if (tyg && !v.startsWith("c")) continue;
      visa?.(i / FORSOK.length);
      if (p !== w.psm) { await w.worker.setParameters({tessedit_pageseg_mode: p}); w.psm = p; }
      const t0 = Date.now(), data = (await lasMedTak(w, variant(v), Math.min(TAK_FORSOK, LAS_TID - (Date.now() - start) + 1000)))?.data;
      window.LAS_LOGG?.push([v, p, Date.now() - t0, data ? (data.words || []).length : "tak"]);
      if (!data) continue;
      if ((data.words || []).length > 120) tyg = true;
      const b = marketIOrd(ordFran(data), marken);
      if (b) return {...b, text: data.text || ""};
    }
  } finally {
    if (w.psm !== "3") { await w.worker.setParameters({tessedit_pageseg_mode: "3"}).catch(() => {}); w.psm = "3"; }
  }
  return null;
}
let aliasLaddas = null;
function laddaAlias(){
  // Varianterna av märkena (BOSS -> Hugo Boss) byggs från marken.py när hemsidan byggs.
  return aliasLaddas ??= fetch("marken-alias.json").then(r => r.ok ? r.json() : {}).catch(() => ({})).then(a => { sattAlias(a); return a; });
}
// Alla märken som går att känna igen: börsens egna plus de kända från marken.py.
async function kandaMarken(marken){ return [...new Set([...(marken || []), ...Object.values(await laddaAlias())])]; }
// Det någon skriver ("boss", "levis") blir märkets riktiga namn om det är känt.
function kanon(text, marken){
  const k = nyckel(text).join("");
  if (!k) return "";
  const hit = (marken || []).find(m => nyckel(m).join("") === k);
  if (hit) return hit;
  const v = Object.entries(alias).find(([a]) => nyckel(a).join("") === k);
  if (v) return (marken || []).find(m => nyckel(m).join("") === nyckel(v[1]).join("")) || v[1];
  return String(text).trim();
}
// Så säker måste AI:n vara på märket för att det ska räknas (inga fel på testlapparna från 80 %).
const CLIP_MARKE_SAKER = 0.8;
// Läser bilderna. AI:n (CLIP) tittar först: vilket plagg det är, vilken bild som är lappen och märket om
// det syns tydligt. Lappen läses sedan med OCR (texten, och märket om AI:n inte var säker).
// text: false hoppar över OCR när AI:n redan sett märket (Fota lappen behöver inte storlek och material).
async function lasBilder(filer, marken, visa, {text = true} = {}){
  marken = await kandaMarken(marken);
  const lasta = [];
  for (const fil of filer) lasta.push({fil, bild: await createImageBitmap(fil), text: "", ord: 0, ordlista: [], ai: null});
  for (let n = 0; n < lasta.length; n++) {
    try {
      lasta[n].ai = await kannIgen(lasta[n].bild, p => visa(p < 1 ? `Laddar ner AI:n … ${Math.round(p * 100)} %`
        : lasta.length > 1 ? `Tittar på bild ${n + 1} av ${lasta.length} …` : "Tittar på bilden …"));
    } catch (e) { console.error(e); break; }  // utan AI:n går det ändå med OCR
  }
  const medAi = lasta.every(l => l.ai && l.ai.lapp != null);
  // Plaggbilden: den som AI:n tycker minst ser ut som en lapp (utan AI:n: den med minst text, se nedan).
  let plagg = medAi ? [...lasta].sort((a, b) => a.ai.lapp - b.ai.lapp)[0] : null;
  const lappar = medAi ? lasta.filter(l => lasta.length === 1 || l !== plagg) : lasta;
  const t = {marke: "", storlek: "", material: ""};
  const sedd = lappar.map(l => l.ai && l.ai.marke).filter(m => m && m.p >= CLIP_MARKE_SAKER).sort((a, b) => b.p - a.p)[0];
  if (sedd) t.marke = (marken.find(m => nyckel(m).join("") === nyckel(sedd.namn).join("")) || sedd.namn);
  if (!t.marke || text) {
    await laddaTesseract();
    const w = {worker: await Tesseract.createWorker(["swe", "eng"], 1), psm: "3"};
    try {
      for (let n = 0; n < lappar.length; n++) {
        visa(lappar.length > 1 ? `Läser lapp ${n + 1} av ${lappar.length} …` : "Läser lappen …");
        const l = lappar[n], t0 = Date.now(), data = (await lasMedTak(w, gra(l.bild), TAK_FORSTA))?.data;
        window.LAS_LOGG?.push(["bild" + n, "3", Date.now() - t0, data ? (data.words || []).length : "tak"]);
        if (!data) { l.tyg = true; continue; }
        l.text = data.text || ""; l.ordlista = ordFran(data); l.tyg = (data.words || []).length > 120;
        l.ord = (data.words || []).filter(x => x.confidence > 60 && /[a-zåäö]{2}|\d+\s*%/i.test(x.text)).length;
      }
      const o = tolka(lappar.map(l => l.text).join("\n"), marken, lappar.map(l => l.ordlista));
      t.storlek = o.storlek; t.material = o.material;
      if (!t.marke) t.marke = o.marke;
      plagg ??= [...lasta].sort((a, b) => a.ord - b.ord)[0];
      // En bild som AI:n ser som ett helt plagg letas det inte vidare i (tyget läses som bokstäver och tar lång tid).
      const lapp = [...lappar].filter(l => lasta.length === 1 || l !== plagg).sort((a, b) => b.ord - a.ord)[0];
      const baraPlagg = lasta.length === 1 && medAi && lasta[0].ai.lapp < 0.3;
      if (!t.marke && lapp && !baraPlagg) {
        const b = await lasMarke(w, lapp.bild, marken, p => visa(`Letar efter märket … ${Math.round(p * 100)} %`), lapp.tyg);
        if (b) {
          t.marke = b.marke;
          const extra = tolka(b.text, []);
          t.storlek ||= extra.storlek; t.material ||= extra.material;
        }
      }
    } finally {
      await w.worker.terminate().catch(() => {});
    }
  }
  // En ensam bild är ett plagg om AI:n ser ett plagg (eller, utan AI:n, om den har lite text).
  const harPlagg = lasta.length > 1 || (medAi ? lasta[0].ai.lapp < 0.5 : plagg.ord < 4);
  return {lasta, t, plagg, harPlagg, marken};
}
function plaggfarg(bild){
  // Mitten av bilden (bålen), utan pixlar som liknar bakgrunden runt kanten.
  const [c, g] = rita2(bild, 96), w = c.width, h = c.height, d = g.getImageData(0, 0, w, h).data;
  const kant = [];
  for (let x = 0; x < w; x++) for (const y of [0, h - 1]) kant.push(4 * (y * w + x));
  for (let y = 0; y < h; y++) for (const x of [0, w - 1]) kant.push(4 * (y * w + x));
  const med = k => { const v = kant.map(i => d[i + k]).sort((a, b) => a - b); return v[v.length >> 1]; };
  const bg = [med(0), med(1), med(2)];
  const hinkar = new Map();
  for (let y = Math.floor(h * 0.3); y < h * 0.72; y++) for (let x = Math.floor(w * 0.28); x < w * 0.72; x++) {
    const i = 4 * (y * w + x), r = d[i], gg = d[i + 1], b = d[i + 2];
    if (Math.hypot(r - bg[0], gg - bg[1], b - bg[2]) < 45) continue;
    const k = (r >> 5) * 64 + (gg >> 5) * 8 + (b >> 5), e = hinkar.get(k) || [0, 0, 0, 0];
    e[0]++; e[1] += r; e[2] += gg; e[3] += b; hinkar.set(k, e);
  }
  const bast = [...hinkar.values()].sort((a, b) => b[0] - a[0])[0];
  if (!bast || bast[0] < 20) return "";
  return fargnamn(bast[1] / bast[0], bast[2] / bast[0], bast[3] / bast[0]);
}
// Den lilla AI:n (CLIP) som känner igen plagget. Bilddelen körs i
// webbläsaren; plaggens och mönstrens textvektorer är uträknade i förväg
// (clip_etiketter.py), så textdelen behövs inte här.
const ORT = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/";
const MAPP = location.pathname.includes("/borsen/") ? "../modeller/" : "modeller/";
const CLIP_MB = 88;
// Är AI:n osäker mellan liknande plagg (hoodie eller sweatshirt) skrivs det
// allmänna namnet, och är den osäker på allt lämnas rutan tom.
const FAMILJER = {
  "Tröja": ["Långärmad tröja", "Stickad tröja", "Sweatshirt", "Hoodie", "Zip-hoodie", "Kofta", "Halvzip-tröja", "Fleecetröja"],
  "Jacka": ["Jacka", "Dunjacka", "Jeansjacka", "Skinnjacka", "Rock", "Trenchcoat", "Väst", "Kavaj", "Fleecetröja", "Overshirt"],
  "Byxor": ["Jeans", "Byxor", "Mjukisbyxor"],
  "Skor": ["Sneakers", "Kängor", "Skor"],
};
const PLAGG_SAKER = 0.45, FAMILJ_SAKER = 0.6, MONSTER_SAKER = {"Tryck på framsidan": 0.9}, MONSTER_ANNARS = 0.6;
let ortLaddas = null, clipLaddas = null;
function laddaOrt(){
  if (window.ort) return Promise.resolve();
  return ortLaddas ??= new Promise((ok, fel) => {
    const s = document.createElement("script");
    s.src = ORT + "ort.min.js";
    s.onload = () => { ort.env.wasm.wasmPaths = ORT; ok(); };
    s.onerror = () => { ortLaddas = null; fel(new Error("ladda")); };
    document.head.appendChild(s);
  });
}
async function hamta(url, visa){
  let cache = null;
  try { cache = await caches.open("fixabild-1"); const finns = await cache.match(url); if (finns) return new Uint8Array(await finns.arrayBuffer()); } catch { cache = null; }
  const svar = await fetch(url);
  if (!svar.ok) throw new Error("saknas " + url);
  const total = +svar.headers.get("content-length") || CLIP_MB * 1e6, las = svar.body.getReader(), delar = [];
  let fatt = 0;
  for (;;) { const {done, value} = await las.read(); if (done) break; delar.push(value); fatt += value.length; visa?.(fatt / total); }
  const data = new Uint8Array(fatt); let i = 0;
  for (const d of delar) { data.set(d, i); i += d.length; }
  try { await cache?.put(url, new Response(data)); } catch {}
  return data;
}
function laddaClip(visa){
  return clipLaddas ??= (async () => {
    await laddaOrt();
    const [modell, etiketter] = await Promise.all([hamta(MAPP + "clip-bild.onnx", visa), fetch(MAPP + "clip-etiketter.json").then(r => r.json())]);
    visa?.(1);
    // Märkenas vektorer ligger packade som int8 (se clip_etiketter.py).
    const mk = etiketter.marken;
    if (mk && mk.vek) {
      const q = new Int8Array(Uint8Array.from(atob(mk.vek), c => c.charCodeAt(0)).buffer), d = q.length / mk.namn.length;
      etiketter.markeVek = mk.namn.map((_, i) => Float32Array.from(q.subarray(i * d, (i + 1) * d), x => x / 127 * mk.skala[i]));
    }
    return {sess: await ort.InferenceSession.create(modell, {executionProviders: ["wasm"]}), etiketter};
  })().catch(e => { clipLaddas = null; throw e; });
}
const MEDEL = [0.48145466, 0.4578275, 0.40821073], STD = [0.26862954, 0.26130258, 0.27577711];
function andelar(grupp, v){
  // Samma räkning som CLIP själv: likhet gånger 100, sedan softmax.
  const namn = Object.keys(grupp), z = namn.map(n => 100 * grupp[n].reduce((s, x, i) => s + x * v[i], 0));
  const mx = Math.max(...z), e = z.map(x => Math.exp(x - mx)), sum = e.reduce((a, b) => a + b, 0);
  return Object.fromEntries(namn.map((n, i) => [n, e[i] / sum]));
}
const topp = p => Object.entries(p).sort((a, b) => b[1] - a[1])[0];
function valjPlagg(p){
  const [namn, andel] = topp(p);
  if (andel >= PLAGG_SAKER) return namn;
  const [familj, summa] = topp(Object.fromEntries(Object.entries(FAMILJER).map(([f, l]) => [f, l.reduce((s, n) => s + (p[n] || 0), 0)])));
  return summa >= FAMILJ_SAKER ? familj : "";
}
function valjMonster(p){
  const [namn, andel] = topp(p);
  return namn && andel >= (MONSTER_SAKER[namn] ?? MONSTER_ANNARS) ? namn : "";
}
async function kannIgen(bild, visa){
  const {sess, etiketter} = await laddaClip(visa);
  // Kortaste sidan till 224, sedan mitten 224 x 224, som CLIP själv gör.
  const f = 224 / Math.min(bild.width, bild.height), w = Math.max(224, Math.round(bild.width * f)), h = Math.max(224, Math.round(bild.height * f));
  const c = document.createElement("canvas"); c.width = c.height = 224;
  const g = c.getContext("2d", {willReadFrequently: true});
  g.imageSmoothingQuality = "high";
  g.drawImage(bild, -Math.floor((w - 224) / 2), -Math.floor((h - 224) / 2), w, h);
  const d = g.getImageData(0, 0, 224, 224).data, x = new Float32Array(3 * 224 * 224);
  for (let p = 0; p < 224 * 224; p++) for (let k = 0; k < 3; k++) x[k * 224 * 224 + p] = (d[4 * p + k] / 255 - MEDEL[k]) / STD[k];
  const ut = await sess.run({[sess.inputNames[0]]: new ort.Tensor("float32", x, [1, 3, 224, 224])});
  const v = ut[sess.outputNames[0]].data, n = Math.hypot(...v), vn = Array.from(v, a => a / n);
  const p = andelar(etiketter.plagg, vn);
  const ut2 = {plagg: valjPlagg(p), monster: valjMonster(andelar(etiketter.monster, vn)), p, marke: null, lapp: null};
  if (etiketter.vy) ut2.lapp = andelar(etiketter.vy, vn).lapp;
  if (etiketter.markeVek) {
    const z = etiketter.markeVek.map(m => 100 * m.reduce((s, x, i) => s + x * vn[i], 0)), mx = Math.max(...z);
    const e = z.map(x => Math.exp(x - mx)), sum = e.reduce((a, b) => a + b, 0), i = z.indexOf(mx);
    ut2.marke = {namn: etiketter.marken.namn[i], p: e[i] / sum};
  }
  return ut2;
}
const lista = v => v.length > 1 ? v.slice(0, -1).join(", ") + " och " + v[v.length - 1] : v.join("");
async function franBilder(filer){
  filer = [...filer].filter(f => /^image\//.test(f.type)).slice(0, 4);
  if (!filer.length) return;
  const zon = $("abzon"), rubrik = zon.querySelector("b"), notis = $("abnotis"), text = rubrik.textContent;
  const visa = t => { rubrik.textContent = t; };
  zon.classList.add("laser"); notis.hidden = true;
  try {
    const {t, plagg, harPlagg} = await lasBilder(filer, window.BokforMarken ? window.BokforMarken() : [], visa);
    const farg = harPlagg ? plaggfarg(plagg.bild) : "";
    let ai = {plagg: "", monster: ""};
    if (harPlagg) {
      try {
        visa("Känner igen plagget …");
        ai = plagg.ai || await kannIgen(plagg.bild, p => visa(p < 1 ? `Laddar ner AI:n … ${Math.round(p * 100)} %` : "Känner igen plagget …"));
      } catch (e) { console.error(e); }
    }
    const fyllt = [];
    const satt = (id, v, namn) => { if (v) { $(id).value = v; fyllt.push(namn); } };
    satt("abplagg", ai.plagg, "plagg");
    satt("abmarke", t.marke, "märke"); satt("abstorlek", t.storlek, "storlek");
    satt("abmaterial", t.material, "material"); satt("abfarg", farg, "färg");
    if (ai.monster && !$("abdetaljer").value) satt("abdetaljer", ai.monster, "mönster");
    rita();
    const saknas = [!ai.plagg && "vad det är för plagg", !t.marke && "märke", !t.storlek && "storlek", !t.material && "material"].filter(Boolean);
    notis.innerHTML = fyllt.length
      ? `Jag fyllde i ${lista(fyllt)}. Kolla att allt stämmer${saknas.length ? ` och skriv ${lista(saknas)} om du vet` : ""}, välj skick och kopiera.`
      : "Jag kunde inte läsa något från bilderna. Prova en skarp bild på lappen, rakt framifrån och i bra ljus, eller fyll i själv.";
    notis.hidden = false;
    if (!$("abplagg").value) $("abplagg").focus();
  } catch (e) {
    console.error(e);
    notis.textContent = "Det gick inte att läsa bilderna just nu. Fyll i uppgifterna själv i stället.";
    notis.hidden = false;
  } finally {
    visa(text); zon.classList.remove("laser"); $("abfil").value = "";
  }
}
// Fota lappen (vardera.js) läser bilderna på samma sätt.
rot.AnnonsBild = {laddaTesseract, gra, kannIgen, plaggfarg, tolka, lasBilder, laddaAlias, kanon};
// Fyller i beskrivningen från Fota lappen.
rot.AnnonsFyll = (v) => { if (!$("abform")) return; for (const [id, x] of Object.entries(v)) if (x && $(id)) $(id).value = x; rita(); };
function init(){
  if (!$("abform")) return;
  $("abskick").innerHTML = Object.keys(SKICK).map(s => `<button type="button" class="chip" data-s="${s}">${s}</button>`).join("");
  $("abform").addEventListener("input", rita);
  $("abform").addEventListener("change", rita);
  $("abskick").addEventListener("click", e => { const b = e.target.closest("[data-s]"); if (!b) return; skick = b.dataset.s; rita(); });
  $("abkopiera").addEventListener("click", kopiera);
  $("abrensa").addEventListener("click", () => { $("abform").reset(); skick = "Mycket bra"; $("abnotis").hidden = true; rita(); });
  $("abfil").addEventListener("change", e => franBilder(e.target.files));
  const zon = $("abzon");
  zon.addEventListener("dragover", e => { e.preventDefault(); zon.classList.add("over"); });
  zon.addEventListener("dragleave", () => zon.classList.remove("over"));
  zon.addEventListener("drop", e => { e.preventDefault(); zon.classList.remove("over"); franBilder(e.dataTransfer.files); });
  rita();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})(typeof window !== "undefined" ? window : globalThis);
