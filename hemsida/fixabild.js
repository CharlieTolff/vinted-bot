// Fixa bilder: byter bakgrunden på annonsbilder mot en vit studiobakgrund.
// Samma metod som vit_bakgrund.py, men allt körs i webbläsaren, så bilderna
// lämnar aldrig användarens mobil eller dator. Plagget och personen ändras inte,
// bara det som ligger bakom.
(() => {
const ORT = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.1/dist/";
const MAPP = location.pathname.includes("/borsen/") ? "../modeller/" : "modeller/";
const MODELLER = {
  isnet: {fil: "isnet-general-use.onnx", mb: 47, storlek: 1024, medel: [0.5, 0.5, 0.5], std: [1, 1, 1]},
  human: {fil: "u2net_human_seg.onnx", mb: 44, storlek: 320, medel: [0.485, 0.456, 0.406], std: [0.229, 0.224, 0.225]},
};
const MAX_SIDA = 2400;  // större bilder krymps, Vinted och Tradera visar ändå inte mer

// Utseende. Grunden kommer från vit_bakgrund.py, men här står motivet en bit
// framför en papprulle i en studio: väggens gamla skuggor tonas ner och
// ersätts av en mjuk kastskugga snett bakom, ljuset från motivets kanter
// sprids lite (som i en riktig bild) och bakgrunden får samma brus som bilden.
const VIT_MITT = 250, VIT_KANT = 222, SIDLJUS = 0.05, BG_TON = [1.0, 0.96, 0.91];
const SKUGGSTYRKA = 0.3, VITBALANS = 0.6, SKUGGLYFT = 0.85, KONTRAST = 0.05;
const KASTSKUGGA = 0.2, KAST_X = 0.03, KAST_Y = 0.02, KAST_MJUK = 1 / 20, NARSKUGGA = 0.06, LJUSKANT = 0.35;
const LUM = [0.299, 0.587, 0.114];

const $ = id => document.getElementById(id);
const vila = () => new Promise(r => setTimeout(r, 50));  // ger webbläsaren tid att visa ny text
let lage = "person";
try { lage = localStorage.getItem("fixabild-lage") || "person"; } catch {}

// ---------- Laddning av bildverktyget ----------
let ortLaddas = null;
function laddaOrt(){
  if (window.ort) return Promise.resolve(window.ort);
  return ortLaddas ??= new Promise((ok, fel) => {
    const s = document.createElement("script");
    s.src = ORT + "ort.min.js";
    s.onload = () => { ort.env.wasm.wasmPaths = ORT; ok(ort); };
    s.onerror = () => { ortLaddas = null; fel(Object.assign(new Error("Kunde inte ladda bildverktyget. Kolla att du är uppkopplad."), {visa: true})); };
    document.head.appendChild(s);
  });
}

async function hamtaModell(namn, visa){
  const m = MODELLER[namn], url = MAPP + m.fil;
  let cache = null;
  try { cache = await caches.open("fixabild-1"); const finns = await cache.match(url); if (finns) return new Uint8Array(await finns.arrayBuffer()); } catch { cache = null; }
  const svar = await fetch(url);
  if (!svar.ok) throw Object.assign(new Error("Bildverktyget finns inte på servern än. Försök igen om en stund."), {visa: true});
  const total = +svar.headers.get("content-length") || m.mb * 1e6;
  const delar = []; let fatt = 0;
  const las = svar.body.getReader();
  for (;;) {
    const {done, value} = await las.read();
    if (done) break;
    delar.push(value); fatt += value.length;
    visa(fatt / total);
  }
  const data = new Uint8Array(fatt); let i = 0;
  for (const d of delar) { data.set(d, i); i += d.length; }
  try { await cache?.put(url, new Response(data)); } catch {}
  return data;
}

// Modellerna körs på processorn (wasm). Grafikkortsläget (WebGPU) klarar inte
// alla delar av dem och fastnade i Chrome.
const sessioner = {};
async function session(namn, visa){
  if (sessioner[namn]) return sessioner[namn];
  await laddaOrt();
  const data = await hamtaModell(namn, visa);
  visa(1, "Startar bildverktyget …"); await vila();
  return sessioner[namn] = await ort.InferenceSession.create(data, {executionProviders: ["wasm"]});
}
async function kor(namn, matning){
  const sess = sessioner[namn];
  return (await sess.run({[sess.inputNames[0]]: matning}))[sess.outputNames[0]];
}

// ---------- Bildmatte ----------
function boxRadier(sigma){
  // Tre lådoskärpor i rad ger nästan exakt en gaussisk oskärpa.
  const n = 3, ideal = Math.sqrt(12 * sigma * sigma / n + 1);
  let wl = Math.floor(ideal); if (wl % 2 === 0) wl--;
  const m = Math.round((12 * sigma * sigma - n * wl * wl - 4 * n * wl - 3 * n) / (-4 * wl - 4));
  return [0, 1, 2].map(i => ((i < m ? wl : wl + 2) - 1) / 2);
}
function lada(src, dst, w, h, r, horisontell){
  const n = horisontell ? w : h, rader = horisontell ? h : w, steg = horisontell ? 1 : w, ny = horisontell ? w : 1;
  const del = 1 / (2 * r + 1);
  for (let k = 0; k < rader; k++) {
    const bas = k * ny;
    const v = i => src[bas + (i < 0 ? 0 : i >= n ? n - 1 : i) * steg];
    let s = 0;
    for (let i = -r; i <= r; i++) s += v(i);
    for (let i = 0; i < n; i++) {
      dst[bas + i * steg] = s * del;
      s += v(i + r + 1) - v(i - r);
    }
  }
}
function gauss(a, w, h, sigma){
  const ut = Float32Array.from(a);
  if (sigma < 0.5) return ut;
  const tmp = new Float32Array(a.length);
  for (const r of boxRadier(sigma)) {
    if (r < 1) continue;
    lada(ut, tmp, w, h, r, true);
    lada(tmp, ut, w, h, r, false);
  }
  return ut;
}
function nblur(v, vikt, w, h, sigma){
  // Oskärpa som bara räknar med pixlar där vikt > 0 (fyller hål).
  const vv = new Float32Array(v.length);
  for (let i = 0; i < v.length; i++) vv[i] = v[i] * vikt[i];
  const a = gauss(vv, w, h, sigma), b = gauss(vikt, w, h, sigma);
  for (let i = 0; i < a.length; i++) a[i] /= Math.max(b[i], 1e-4);
  return a;
}
function skala(a, sw, sh, w, h){
  // Bilinjär storleksändring av en karta.
  const ut = new Float32Array(w * h);
  for (let y = 0; y < h; y++) {
    const fy = Math.min(Math.max((y + 0.5) * sh / h - 0.5, 0), sh - 1), y0 = Math.floor(fy), y1 = Math.min(y0 + 1, sh - 1), ty = fy - y0;
    for (let x = 0; x < w; x++) {
      const fx = Math.min(Math.max((x + 0.5) * sw / w - 0.5, 0), sw - 1), x0 = Math.floor(fx), x1 = Math.min(x0 + 1, sw - 1), tx = fx - x0;
      ut[y * w + x] = (a[y0 * sw + x0] * (1 - tx) + a[y0 * sw + x1] * tx) * (1 - ty) + (a[y1 * sw + x0] * (1 - tx) + a[y1 * sw + x1] * tx) * ty;
    }
  }
  return ut;
}
const klipp = (x, a, b) => x < a ? a : x > b ? b : x;

async function korModell(namn, bild, w, h){
  const m = MODELLER[namn], s = m.storlek;
  const c = new OffscreenCanvas(s, s), g = c.getContext("2d");
  g.imageSmoothingQuality = "high";
  g.drawImage(bild, 0, 0, s, s);
  const px = g.getImageData(0, 0, s, s).data;
  let max = 1e-6;
  for (let i = 0; i < px.length; i++) if ((i & 3) !== 3 && px[i] > max) max = px[i];
  const x = new Float32Array(3 * s * s);
  for (let i = 0; i < s * s; i++) for (let k = 0; k < 3; k++) x[k * s * s + i] = (px[i * 4 + k] / max - m.medel[k]) / m.std[k];
  const ut = await kor(namn, new ort.Tensor("float32", x, [1, 3, s, s]));
  const o = ut.data.subarray(0, s * s);
  let lo = Infinity, hi = -Infinity;
  for (const v of o) { if (v < lo) lo = v; if (v > hi) hi = v; }
  const n = new Float32Array(s * s), d = Math.max(hi - lo, 1e-6);
  for (let i = 0; i < n.length; i++) n[i] = (o[i] - lo) / d;
  return skala(n, s, s, w, h);
}

async function maskFor(bild, w, h){
  const isnet = await korModell("isnet", bild, w, h);
  if (lage !== "person") {
    for (let i = 0; i < isnet.length; i++) isnet[i] = klipp((isnet[i] - 0.1) / 0.8, 0, 1);
    return isnet;
  }
  const human = await korModell("human", bild, w, h);
  // Människomodellen avgör vad som hör till motivet (så element o.d. åker bort),
  // den skarpare isnet-modellen ger kanterna.
  const grov = gauss(human.map(v => v > 0.5 ? 1 : 0), w, h, 6);
  const alfa = new Float32Array(w * h);
  for (let i = 0; i < alfa.length; i++) {
    const a = grov[i] > 0.2 ? klipp((isnet[i] - 0.1) / 0.8, 0, 1) : 0;
    // isnet tappar ibland hud; där människomodellen är säker får den bestämma.
    alfa[i] = Math.max(a, klipp((human[i] - 0.6) / 0.3, 0, 1));
  }
  return alfa;
}

async function gorVit(bild, w, h, steg){
  const c = new OffscreenCanvas(w, h), g = c.getContext("2d");
  g.drawImage(bild, 0, 0, w, h);
  const px = g.getImageData(0, 0, w, h);
  const N = w * h, I = [0, 1, 2].map(k => { const a = new Float32Array(N); for (let i = 0; i < N; i++) a[i] = px.data[i * 4 + k]; return a; });
  steg("Hittar plagget … det kan ta upp till en halv minut"); await vila();
  const alfa = await maskFor(bild, w, h);
  steg("Byter bakgrund …"); await vila();
  const lum = new Float32Array(N);
  for (let i = 0; i < N; i++) lum[i] = LUM[0] * I[0][i] + LUM[1] * I[1][i] + LUM[2] * I[2][i];

  // Väggpixlar som säkert är vägg (inte motiv, inte saker som element/lister).
  const ga = gauss(alfa, w, h, 4), bort = new Uint8Array(N);
  for (let i = 0; i < N; i++) bort[i] = ga[i] < 0.02;
  const sm = Math.max(w, h);
  let vikt = Float32Array.from(bort);
  for (let k = 0; k < 2; k++) {
    // Saker på väggen skiljer sig i ljus från väggen runt omkring och räknas bort.
    const jamfor = nblur(lum, vikt, w, h, sm / 25), v = new Float32Array(N);
    for (let i = 0; i < N; i++) v[i] = bort[i] && Math.abs(lum[i] / Math.max(jamfor[i], 1) - 1) < 0.12 ? 1 : 0;
    const gv = gauss(v, w, h, 4);
    for (let i = 0; i < N; i++) vikt[i] = gv[i] > 0.97 ? 1 : 0;
    await vila();
  }

  // Väggens ljus utan detaljer: storskaligt (belysning) och lokalt (skuggor nära motivet).
  const ljusStor = nblur(lum, vikt, w, h, sm / 6), tackning = gauss(vikt, w, h, sm / 50), ljusLok = nblur(lum, vikt, w, h, sm / 50);
  const kvot = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const lok = tackning[i] > 0.05 ? ljusLok[i] : ljusStor[i], t = klipp((tackning[i] - 0.1) / 0.4, 0, 1);
    kvot[i] = klipp((t * lok + (1 - t) * ljusStor[i]) / Math.max(ljusStor[i], 1), 0.8, 1);
  }
  const skugga = gauss(kvot, w, h, sm / 50), nara = gauss(alfa, w, h, sm / 40);
  // Kastskugga: ljuset kommer snett ovanifrån från vänster och motivet står
  // en bit från väggen, så skuggan hamnar till höger och nedåt och blir mjuk.
  // Utanför bilden fortsätter motivet rakt ut (armar och ben som skärs av).
  // Ett plagg som ligger eller hänger är nära underlaget, så skuggan blir kortare och skarpare.
  const nar = lage === "person" ? 1 : 0.3;
  const dx = Math.round(sm * KAST_X * nar), dy = Math.round(sm * KAST_Y * nar), forskj = new Float32Array(N);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) forskj[y * w + x] = alfa[klipp(y - dy, 0, h - 1) * w + klipp(x - dx, 0, w - 1)];
  const kast = gauss(forskj, w, h, sm * KAST_MJUK * nar), narKast = gauss(alfa, w, h, sm / 90);
  // Ljuskant: bakgrundens ljus sprids in en liten bit över motivets kant.
  const kant = gauss(alfa.map(a => 1 - a), w, h, Math.max(1.5, sm / 350));
  // Brus: bakgrunden får samma korn som resten av bilden, annars ser den
  // för slät och redigerad ut.
  const hp = gauss(lum, w, h, 1.2), avv = [];
  for (let i = 0; i < N; i += 7) if (alfa[i] > 0.97) avv.push(Math.abs(lum[i] - hp[i]));
  avv.sort((p, q) => p - q);
  const brus = klipp(avv.length > 200 ? 1.4826 * avv[avv.length >> 1] * 1.6 : 1.5, 0.8, 5);
  await vila();

  // Studioljus: mjuk radiell avtoning från strax ovanför mitten.
  const bg = [new Float32Array(N), new Float32Array(N), new Float32Array(N)], ljus = new Float32Array(N);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = y * w + x;
    const r = Math.hypot((x - w / 2) / (w * 0.75), (y - h * 0.42) / (h * 0.85));
    const studio = (VIT_MITT - (VIT_MITT - VIT_KANT) * Math.pow(klipp(r, 0, 1), 1.6)) * (1 + SIDLJUS / 2 - SIDLJUS * x / w);
    const sk = (1 - SKUGGSTYRKA * klipp(nara[i] * 6, 0, 1) * (1 - skugga[i])) * (1 - KASTSKUGGA * kast[i]) * (1 - NARSKUGGA * narKast[i]);
    ljus[i] = studio * sk;  // sparas så att bakgrundsfärgen kan bytas utan att räkna om allt
    for (let k = 0; k < 3; k++) bg[k][i] = studio * sk * BG_TON[k];
  }

  // Rensa bort väggfärg i kanterna på motivet.
  const vikt2 = vikt.map(v => v + 1e-3);
  const fg = I.map(Ik => { const vagg = nblur(Ik, vikt2, w, h, sm / 60), f = new Float32Array(N);
    for (let i = 0; i < N; i++) { const a = alfa[i]; f[i] = a > 0.05 ? (Ik[i] - (1 - a) * vagg[i]) / Math.max(a, 0.05) : Ik[i]; }
    return f; });
  await vila();

  // Vitbalans: motivet neutraliseras mot rummets ljus (som syns på väggen),
  // men aldrig så mycket att det blir kallare (blåare) än neutralt.
  const vm = [0, 0, 0], mm = [0, 0, 0]; let nv = 0, nm = 0;
  for (let i = 0; i < N; i++) {
    if (vikt[i] > 0) { nv++; for (let k = 0; k < 3; k++) vm[k] += I[k][i]; }
    if (alfa[i] > 0.9) { nm++; for (let k = 0; k < 3; k++) mm[k] += fg[k][i]; }
  }
  let forst = [1, 1, 1];
  if (nv > 100 && nm > 100) {
    for (let k = 0; k < 3; k++) { vm[k] /= nv; mm[k] /= nm; }
    const snitt = (vm[0] + vm[1] + vm[2]) / 3;
    for (let styrka = VITBALANS; styrka > -0.001; styrka -= 0.05) {
      forst = vm.map(v => Math.pow(snitt / Math.max(v, 1), styrka));
      const l = forst[0] * LUM[0] + forst[1] * LUM[1] + forst[2] * LUM[2];
      forst = forst.map(f => f / l);
      if (mm[2] * forst[2] <= mm[0] * forst[0] * BG_TON[2]) break;
    }
  }

  // Lyft skuggorna lite och ge en svag kontrastkurva, lägg ihop med bakgrunden.
  const ut = [new Float32Array(N), new Float32Array(N), new Float32Array(N)], bak = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    const f = [0, 1, 2].map(k => klipp(fg[k][i] * forst[k], 0, 255));
    const fl = Math.max(f[0] * LUM[0] + f[1] * LUM[1] + f[2] * LUM[2], 0.5) / 255;
    let nl = Math.pow(fl, SKUGGLYFT); nl += KONTRAST * nl * (1 - nl) * (nl - 0.5) * 4;
    const a = alfa[i], lk = a * LJUSKANT * kant[i], korn = slump() * brus * (1 - a);
    bak[i] = 1 - a + lk;
    for (let k = 0; k < 3; k++) ut[k][i] = klipp(Math.round(klipp(f[k] * nl / fl, 0, 255) * (a - lk) + bg[k][i] * (1 - a + lk) + korn), 0, 255);
  }
  await vila();

  // Skärpning bara på motivet, bakgrunden ska förbli mjuk.
  for (let k = 0; k < 3; k++) {
    const b = gauss(ut[k], w, h, 2);
    for (let i = 0; i < N; i++) {
      const d = ut[k][i] - b[i];
      if (Math.abs(d) >= 2) ut[k][i] = klipp(ut[k][i] + 0.7 * d, 0, 255) * alfa[i] + ut[k][i] * (1 - alfa[i]);
    }
  }
  for (let i = 0; i < N; i++) { px.data[i * 4] = ut[0][i]; px.data[i * 4 + 1] = ut[1][i]; px.data[i * 4 + 2] = ut[2][i]; px.data[i * 4 + 3] = 255; }
  return {px, alfa, bak, ljus, w, h};
}
// ---------- Bakgrundsfärg ----------
// Färgen anges som den ljusaste punkten på bakgrunden; skuggor och studioljus
// följer med, så även en färgad bakgrund ser ut som en riktig vägg.
const FARGER = [
  ["Vit", BG_TON.map(t => t * VIT_MITT)], ["Kritvit", [255, 255, 255]], ["Ljusgrå", [228, 228, 226]],
  ["Grå", [190, 191, 192]], ["Mörkgrå", [92, 94, 97]], ["Svart", [34, 34, 36]],
  ["Beige", [236, 222, 200]], ["Sand", [214, 194, 160]], ["Kamel", [184, 146, 102]],
  ["Ljusrosa", [244, 214, 216]], ["Persika", [246, 204, 176]], ["Terrakotta", [190, 110, 82]],
  ["Ljusgul", [246, 234, 180]], ["Mint", [204, 232, 214]], ["Salvia", [170, 186, 160]],
  ["Skogsgrön", [52, 84, 64]], ["Ljusblå", [200, 220, 238]], ["Himmelsblå", [140, 182, 222]],
  ["Marinblå", [36, 52, 86]], ["Lavendel", [214, 204, 236]], ["Vinröd", [112, 40, 52]],
];
const hex = c => "#" + c.map(v => Math.round(v).toString(16).padStart(2, "0")).join("");
function farga(r, farg){
  const {px, bak, ljus, w, h, bas} = r, d = px.data, c0 = FARGER[0][1];
  for (let i = 0, n = w * h; i < n; i++) {
    const t = bak[i] * ljus[i] / VIT_MITT;
    for (let k = 0; k < 3; k++) d[i * 4 + k] = bas[i * 4 + k] + t * (farg[k] - c0[k]);
  }
  const c = new OffscreenCanvas(w, h);
  c.getContext("2d").putImageData(px, 0, 0);
  return c.convertToBlob({type: "image/jpeg", quality: 0.93});
}

// Normalfördelat brus (filmkorn), samma varje gång.
let fro = 12345;
function slump(){
  const u = () => ((fro = (fro * 1103515245 + 12345) >>> 0) + 1) / 4294967297;
  return Math.sqrt(-2 * Math.log(u())) * Math.cos(2 * Math.PI * u());
}

// ---------- Sidan ----------
const ko = [];
let jobbar = false;
function ritaLage(){
  $("fblage").querySelectorAll("[data-l]").forEach(b => b.classList.toggle("vald", b.dataset.l === lage));
  const mb = MODELLER.isnet.mb + (lage === "person" ? MODELLER.human.mb : 0);
  $("fbstorlek").textContent = `Första gången laddas bildverktyget ner (ungefär ${mb} MB), sedan går det fort.`;
}
function nyttKort(fil){
  const k = document.createElement("div");
  k.className = "fbkort";
  k.innerHTML = `<div class="fbbild"><img alt=""><span class="fbstatus">Väntar …</span></div>
    <div class="fbfarger" hidden></div>
    <div class="fbknappar"><button class="knapp fbfore" disabled>Visa före</button><button class="knapp primar fbspara" disabled>Spara bild</button></div>`;
  const url = URL.createObjectURL(fil);
  k.querySelector("img").src = url;
  $("fbresultat").prepend(k);
  return {k, fil, fore: url};
}
async function koa(filer){
  for (const fil of filer) if (fil.type.startsWith("image/")) ko.push(nyttKort(fil));
  $("fbsparaalla").hidden = true;
  if (jobbar) return;
  jobbar = true;
  while (ko.length) await fixa(ko.shift());
  jobbar = false;
  $("fbsparaalla").hidden = $("fbresultat").querySelectorAll(".fbkort.klar").length < 2;
}
async function fixa(j){
  const status = j.k.querySelector(".fbstatus"), steg = t => { status.textContent = t; };
  try {
    const visa = (andel, text) => steg(text || `Laddar ner bildverktyget … ${Math.round(andel * 100)} %`);
    await session("isnet", visa);
    if (lage === "person") await session("human", visa);
    const bild = await createImageBitmap(j.fil);
    const f = Math.min(1, MAX_SIDA / Math.max(bild.width, bild.height));
    const w = Math.round(bild.width * f), h = Math.round(bild.height * f);
    const r = await gorVit(bild, w, h, steg);
    r.bas = Uint8ClampedArray.from(r.px.data);
    const img = j.k.querySelector("img"), grund = j.fil.name.replace(/\.[^.]+$/, "");
    let visarFore = false, version = 0;
    async function visaFarg(namn, farg){
      const v = ++version, blob = await farga(r, farg);
      if (v !== version) return;  // en nyare färg hann väljas
      if (j.efter) URL.revokeObjectURL(j.efter);
      j.efter = URL.createObjectURL(blob); j.blob = blob;
      j.namn = `${grund}-${namn.toLowerCase().replace(/[^a-z0-9åäö]+/g, "-")}.jpg`;
      if (!visarFore) img.src = j.efter;
    }
    await visaFarg(FARGER[0][0], FARGER[0][1]);
    status.remove();
    j.k.classList.add("klar");
    const fore = j.k.querySelector(".fbfore"), spara = j.k.querySelector(".fbspara");
    fore.disabled = spara.disabled = false;
    fore.addEventListener("click", () => {
      visarFore = !visarFore;
      img.src = visarFore ? j.fore : j.efter;
      fore.textContent = visarFore ? "Visa efter" : "Visa före";
    });
    const rutor = j.k.querySelector(".fbfarger");
    rutor.innerHTML = FARGER.map(([n, c], i) => `<button class="${i ? "" : "vald"}" data-i="${i}" title="${n}" aria-label="${n}" style="background:${hex(c)}"></button>`).join("") +
      `<label class="egen" title="Egen färg" aria-label="Egen färg"><input type="color" value="#9ab0c8">+</label>`;
    rutor.hidden = false;
    const markera = el => { rutor.querySelectorAll(".vald").forEach(b => b.classList.remove("vald")); el.classList.add("vald"); };
    rutor.addEventListener("click", e => {
      const b = e.target.closest("button[data-i]"); if (!b) return;
      markera(b);
      const [n, c] = FARGER[+b.dataset.i]; visaFarg(n, c);
    });
    const egen = rutor.querySelector("input");
    egen.addEventListener("input", () => {
      markera(egen.parentElement); egen.parentElement.style.background = egen.value;
      visaFarg("egen-farg", [1, 3, 5].map(i => parseInt(egen.value.slice(i, i + 2), 16)));
    });
    spara.addEventListener("click", () => sparaBilder([j]));
    j.k.jobb = j;
  } catch (e) {
    console.error(e);
    status.textContent = e && e.visa ? e.message : "Det gick inte att fixa bilden. Prova en annan bild eller ladda om sidan.";
    status.classList.add("fel");
  }
}
async function sparaBilder(jobb){
  const filer = jobb.map(j => new File([j.blob], j.namn, {type: "image/jpeg"}));
  // På mobilen går bilderna att spara direkt i bildgalleriet via dela-menyn.
  if (matchMedia("(pointer:coarse)").matches && navigator.canShare && navigator.canShare({files: filer})) {
    try { await navigator.share({files: filer}); return; } catch (e) { if (e.name === "AbortError") return; }
  }
  for (const j of jobb) {
    const a = document.createElement("a");
    a.href = j.efter; a.download = j.namn;
    document.body.appendChild(a); a.click(); a.remove();
    await new Promise(r => setTimeout(r, 300));
  }
}

function init(){
  const in_ = $("fbfil");
  if (!in_) return;
  in_.addEventListener("change", () => { koa([...in_.files]); in_.value = ""; });
  const zon = $("fbzon");
  zon.addEventListener("dragover", e => { e.preventDefault(); zon.classList.add("over"); });
  zon.addEventListener("dragleave", () => zon.classList.remove("over"));
  zon.addEventListener("drop", e => { e.preventDefault(); zon.classList.remove("over"); koa([...e.dataTransfer.files]); });
  $("fblage").addEventListener("click", e => {
    const b = e.target.closest("[data-l]"); if (!b) return;
    lage = b.dataset.l; try { localStorage.setItem("fixabild-lage", lage); } catch {}
    ritaLage();
  });
  $("fbsparaalla").addEventListener("click", () => sparaBilder([...$("fbresultat").querySelectorAll(".fbkort.klar")].map(k => k.jobb)));
  ritaLage();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
