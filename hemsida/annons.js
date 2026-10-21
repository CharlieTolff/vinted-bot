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
function tolka(text, marken){
  const rader = String(text || "").split(/\r?\n/).map(r => r.replace(/\s+/g, " ").trim()).filter(Boolean);
  const hel = rader.join("\n"), ut = {marke: "", storlek: "", material: ""};
  const nh = norm(hel);
  for (const m of marken || []) { const n = norm(m); if (n.length >= 3 && nh.includes(n) && n.length > norm(ut.marke).length) ut.marke = m; }
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
rot.AnnonsFarg = fargnamn;
if (typeof document === "undefined") { if (typeof module !== "undefined") module.exports = {tolka, fargnamn}; return; }
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
function rita2(bild, max){
  const f = Math.min(1, max / Math.max(bild.width, bild.height));
  const c = document.createElement("canvas");
  c.width = Math.max(1, Math.round(bild.width * f)); c.height = Math.max(1, Math.round(bild.height * f));
  const g = c.getContext("2d", {willReadFrequently: true});
  g.drawImage(bild, 0, 0, c.width, c.height);
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
  "Jacka": ["Jacka", "Dunjacka", "Jeansjacka", "Skinnjacka", "Rock", "Trenchcoat", "Väst", "Kavaj", "Fleecetröja"],
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
  return {plagg: valjPlagg(andelar(etiketter.plagg, vn)), monster: valjMonster(andelar(etiketter.monster, vn))};
}
const lista = v => v.length > 1 ? v.slice(0, -1).join(", ") + " och " + v[v.length - 1] : v.join("");
async function franBilder(filer){
  filer = [...filer].filter(f => /^image\//.test(f.type)).slice(0, 4);
  if (!filer.length) return;
  const zon = $("abzon"), rubrik = zon.querySelector("b"), notis = $("abnotis"), text = rubrik.textContent;
  const visa = t => { rubrik.textContent = t; };
  zon.classList.add("laser"); notis.hidden = true;
  try {
    visa("Läser bilderna …");
    await laddaTesseract();
    const worker = await Tesseract.createWorker(["swe", "eng"], 1);
    const lasta = [];
    for (let n = 0; n < filer.length; n++) {
      visa(filer.length > 1 ? `Läser bild ${n + 1} av ${filer.length} …` : "Läser bilden …");
      const bild = await createImageBitmap(filer[n]);
      const {data} = await worker.recognize(gra(bild));
      const ord = (data.words || []).filter(w => w.confidence > 60 && /[a-zåäö]{2}|\d+\s*%/i.test(w.text)).length;
      lasta.push({bild, text: data.text || "", ord});
    }
    await worker.terminate();
    const marken = window.BokforMarken ? window.BokforMarken() : [];
    const t = tolka(lasta.map(l => l.text).join("\n"), marken);
    // Bilden med minst text är bilden på själva plagget.
    const plagg = [...lasta].sort((a, b) => a.ord - b.ord)[0];
    const harPlagg = lasta.length > 1 || plagg.ord < 4;
    const farg = harPlagg ? plaggfarg(plagg.bild) : "";
    let ai = {plagg: "", monster: ""};
    if (harPlagg) {
      try {
        visa("Känner igen plagget …");
        ai = await kannIgen(plagg.bild, p => visa(p < 1 ? `Laddar ner AI:n … ${Math.round(p * 100)} %` : "Känner igen plagget …"));
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
