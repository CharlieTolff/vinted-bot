// Fota lappen: ta en bild på lappen (och gärna på plagget), så visar börsen vad plagget brukar säljas för.
// Lappen läses med Tesseract i webbläsaren och plaggets sort med den lilla AI:n (CLIP), båda från annons.js.
// Inget skickas någonstans. Märket och kategorin går alltid att ändra för hand.
(() => {
const $ = id => document.getElementById(id);
if (!$("vdzon")) return;

// AI:ns plagg -> börsens kategori. Plagg som börsen inte mäter saknas här.
const TILL_KAT = {"Kofta": "koftor", "Stickad tröja": "stickat", "Halvzip-tröja": "stickat", "Skjorta": "skjortor", "Overshirt": "overshirts",
  "Dunjacka": "dun", "Väst": "dun", "Jeans": "jeans", "Sneakers": "skor", "Kängor": "skor", "Skor": "skor"};
const KAT_SAKER = 0.5;  // så säker måste AI:n vara på kategorin för att välja den själv
const INTE = ["övriga", "okänt", "no brand", "vintage", "handgjord", "diverse"];
const norm = s => String(s || "").toLowerCase().normalize("NFD").replace(/[^a-z0-9]/g, "");
const avr = v => Math.max(10, Math.round(v / 10) * 10);
let vd = {marke: "", kat: "", plagg: "", bild: "", x: null};

function kats(){ return (B && B.kategorier || []).filter(k => !k.vantar); }
function allaMarken(){
  const s = new Set();
  for (const kalla of ["tradera", "vinted"]) for (const mm of Object.values((B.marke || {})[kalla] || {})) for (const m of Object.keys(mm)) s.add(m);
  for (const v of Object.values(B.tradera_veckor || {})) for (const p of v.slice(-9)) for (const m of Object.keys(p[2] || {})) s.add(m);
  return [...s].filter(m => !INTE.includes(m.toLowerCase())).sort((a, b) => a.localeCompare(b, "sv"));
}
// Det kunden skriver blir börsens stavning av märket, om det finns.
function hittaMarke(text){
  const n = norm(text);
  if (!n) return "";
  return allaMarken().find(m => norm(m) === n) || text.trim();
}

// ---------- Siffrorna för ett märke i en kategori ----------
function veckor(m, kat){
  // Hela veckor (den pågående räknas inte): sålda och mittenpris för märket.
  const v = ((B.tradera_veckor || {})[kat] || []).slice(0, -1);
  return v.map(p => { const x = (p[2] || {})[m]; return {d: p[0], n: x ? x[0] : 0, pris: x ? x[1] : null, alla: p[1]}; });
}
function analys(m, kat){
  const tr = markePunkter("tradera", kat, m), vi = markePunkter("vinted", kat, m);
  const t = tr.at(-1), v = vi.at(-1), vk = veckor(m, kat);
  const salda = t && t[2] && t[1] >= 3;
  if (!salda && !(v && v[2])) return null;
  const x = salda
    ? {kalla: "tradera", median: t[2], p25: t[3], n: t[1], d: t[0], perVecka: t[5] ?? null, begart: v && v[2] || null}
    : {kalla: "vinted", median: v[2], p25: v[3], n: v[1], d: v[0], perVecka: v[6] != null ? v[6] * 7 : null, begart: v[2]};
  // Priset nu jämfört med för en månad sedan.
  const pts = salda ? tr : vi, manad = new Date(dag(x.d) - 28 * 864e5).toISOString().slice(0, 10);
  const forr = fore(pts, manad);
  x.prisUtv = forr && forr[2] && forr[0] < x.d ? 100 * (x.median - forr[2]) / forr[2] : null;
  // Sålda de fyra senaste hela veckorna jämfört med de fyra innan.
  const sum = a => a.reduce((s, w) => s + w.n, 0), nu = vk.slice(-4), innan = vk.slice(-8, -4);
  x.antalNu = nu.length === 4 ? sum(nu) : null;
  x.antalUtv = nu.length === 4 && innan.length === 4 && sum(innan) >= 4 ? 100 * (sum(nu) - sum(innan)) / sum(innan) : null;
  x.veckor = vk.slice(-12);
  return x;
}
function andraKategorier(m){
  return kats().filter(k => analys(m, k.id)).map(k => k.id);
}

// ---------- Diagram: sålda per vecka (staplar) och mittenpris (linje) ----------
function diagram(vk){
  const w = 640, h = 220, pl = 8, pr = 8, pt = 40, pb = 34;
  if (vk.filter(x => x.n).length < 2) return "";
  const maxN = Math.max(...vk.map(x => x.n), 1), priser = vk.map(x => x.pris).filter(p => p != null);
  const minP = Math.min(...priser), maxP = Math.max(...priser), spann = Math.max(1, maxP - minP);
  const bw = (w - pl - pr) / vk.length, y0 = h - pb;
  const yN = n => y0 - (n / maxN) * (h - pt - pb) * 0.85;
  const yP = p => pt + 6 + (1 - (p - minP) / spann) * (h - pt - pb) * 0.6;
  const staplar = vk.map((x, i) => `<rect x="${(pl + i * bw + bw * 0.18).toFixed(1)}" y="${yN(x.n).toFixed(1)}" width="${(bw * 0.64).toFixed(1)}" height="${(y0 - yN(x.n)).toFixed(1)}" rx="3" class="vdstapel"><title>${x.n} sålda veckan från ${esc(x.d)}</title></rect>`).join("");
  const linje = vk.map((x, i) => x.pris == null ? null : [pl + i * bw + bw / 2, yP(x.pris)]).filter(Boolean);
  const punkter = linje.map(([a, b]) => `${a.toFixed(1)},${b.toFixed(1)}`).join(" ");
  const etikett = i => new Date(dag(vk[i].d)).toLocaleDateString("sv-SE", {day: "numeric", month: "short"});
  const sist = linje.at(-1);
  return `<div class="vddiagram"><div class="vdforklaring"><span><i class="vdruta"></i>Sålda per vecka</span><span><i class="vdstreck"></i>Mittenpris</span></div>
    <svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Sålda per vecka och mittenpris">
      ${staplar}
      ${linje.length > 1 ? `<polyline points="${punkter}" class="vdlinje"/>` : ""}
      ${linje.map(([a, b]) => `<circle cx="${a.toFixed(1)}" cy="${b.toFixed(1)}" r="3.5" class="vdpunkt"/>`).join("")}
      ${sist ? `<text x="${Math.min(sist[0], w - 40).toFixed(1)}" y="${(sist[1] - 14).toFixed(1)}" class="vdtext" text-anchor="middle">${esc(kr(vk.at(-1).pris))}</text>` : ""}
      <text x="${pl}" y="${h - 6}" class="vdaxel">${esc(etikett(0))}</text>
      <text x="${w - pr}" y="${h - 6}" class="vdaxel" text-anchor="end">${esc(etikett(vk.length - 1))}</text>
    </svg></div>`;
}

// ---------- Rita ----------
function utv(v){
  if (v == null) return "";
  const r = Math.round(v);
  return `<span class="${r > 0 ? "upp" : r < 0 ? "ned" : ""}">${r > 0 ? "▲ +" : r < 0 ? "▼ −" : ""}${Math.abs(r)} %</span>`;
}
function trendText(x){
  if (x.antalUtv == null) return "";
  const r = Math.round(x.antalUtv);
  return r >= 10 ? "Säljer mer nu än förra månaden" : r <= -10 ? "Säljer mindre nu än förra månaden" : "Säljer ungefär lika mycket som förra månaden";
}
function ritaChips(){
  $("vdkat").innerHTML = kats().map(k => `<button type="button" class="chip${k.id === vd.kat ? " vald" : ""}" data-k="${k.id}">${esc(k.namn)}</button>`).join("");
}
function ritaVardera(){
  if (!B || !B.kategorier) return;
  if (!$("vdmarken").options.length) $("vdmarken").innerHTML = allaMarken().map(m => `<option value="${esc(m)}">`).join("");
  ritaChips();
  const el = $("vdanalys"), m = vd.marke, kat = kats().find(k => k.id === vd.kat);
  vd.x = null;
  if (!m || !kat) {
    el.innerHTML = `<p class="vdtom">${!m && !kat ? "Ta en bild på lappen, eller skriv märket och välj kategori, så visas analysen här." : !m ? "Skriv vilket märke det är." : "Välj vilken sorts plagg det är."}</p>`;
    return;
  }
  const x = analys(m, kat.id);
  if (!x) {
    const andra = andraKategorier(m).map(id => kats().find(k => k.id === id));
    el.innerHTML = `<p class="vdtom">Börsen har inga priser för <b>${esc(m)}</b> i ${esc(kat.namn.toLowerCase())} än.${andra.length ? ` Det finns priser i ${andra.map(k => `<button type="button" class="lankknapp" data-k="${k.id}">${esc(k.namn.toLowerCase())}</button>`).join(", ")}.` : " Kolla stavningen, eller prova ett liknande märke."}</p>`;
    return;
  }
  const tr = x.kalla === "tradera", forslag = avr(x.median * 1.1), betalt = $("vdpris") ? $("vdpris").value : "";
  vd.x = x;
  el.innerHTML = `
    <div class="vdtopp">
      ${vd.bild ? `<img src="${vd.bild}" alt="" class="vdbild">` : ""}
      <div><div class="svag">${esc(kat.namn)}${vd.plagg && TILL_KAT[vd.plagg] === kat.id ? ` · ${esc(vd.plagg.toLowerCase())}` : ""}</div><h3>${esc(m)}</h3>
      <div class="svag">${tr ? `Från ${x.n} sålda senaste 30 dagarna` : `Från ${x.n} annonser, inga slutpriser än`} · mätt ${esc(datumLang(dag(x.d)))}</div></div>
    </div>
    <div class="vsvar vdsvar">
      <div class="resultat"><span>${tr ? "Säljs normalt för" : "Begärs normalt"}</span><b class="tal">${kr(x.median)}</b><small>${x.prisUtv == null ? "mittenpris" : Math.round(x.prisUtv) === 0 ? "oförändrat på en månad" : `${utv(x.prisUtv)} på en månad`}</small></div>
      <div><span>Lägg ut för</span><b class="tal">${kr(forslag)}</b><small>så finns det plats att pruta</small></div>
      <div><span>Säljs ofta från</span><b class="tal">${kr(x.p25)}</b><small>en fjärdedel säljs billigare</small></div>
      <div><span>Sålda per vecka</span><b class="tal">${x.perVecka != null ? Math.round(x.perVecka).toLocaleString("sv-SE") : "–"}</b><small>${x.antalUtv != null ? `${utv(x.antalUtv)} mot förra månaden` : tr ? "på " + esc(KALLOR.tradera.namn) : "uppskattat"}</small></div>
    </div>
    ${trendText(x) ? `<p class="vdtrend">${esc(trendText(x))}.</p>` : ""}
    ${diagram(x.veckor)}
    <div class="vdvinst">
      <label>Vad betalade du? (kr)<input id="vdpris" type="number" inputmode="decimal" min="0" step="1" placeholder="199" value="${esc(betalt)}"></label>
      <div><span>Din vinst</span><b class="tal" id="vdvinst">–</b><small id="vdvinstinfo">skriv vad du betalade</small></div>
    </div>
    <p class="hjalp">Skick, storlek och modell påverkar priset. Siffrorna är vägledning, inte en garanti.</p>
    <div class="abknappar"><button type="button" class="knapp primar" id="vdbeskriv">Skriv annonsen</button><button type="button" class="knapp" id="vdborsen">Se märket i börsen</button></div>`;
  ritaVinsten();
}
function ritaVinsten(){
  const x = vd.x, b = $("vdvinst"), info = $("vdvinstinfo");
  if (!x || !b) return;
  const betalt = parseFloat($("vdpris").value);
  const tecken = n => (n > 0 ? "+" : n < 0 ? "−" : "") + kr(Math.abs(n));
  if (isNaN(betalt)) { b.textContent = "–"; b.className = "tal"; info.textContent = "skriv vad du betalade"; return; }
  const vinst = x.median - betalt, lag = x.p25 ? x.p25 - betalt : null;
  b.textContent = tecken(vinst); b.className = "tal " + (vinst > 0 ? "plus" : vinst < 0 ? "minus" : "");
  info.textContent = lag == null ? "före frakt och avgifter" : `${tecken(lag)} om det säljs i underkant`;
}
window.ritaVardera = ritaVardera;

// ---------- Läsa bilderna ----------
async function franBilder(filer){
  filer = [...filer].filter(f => /^image\//.test(f.type)).slice(0, 3);
  if (!filer.length || !window.AnnonsBild) return;
  const {laddaTesseract, gra, kannIgen, tolka} = window.AnnonsBild;
  const zon = $("vdzon"), rubrik = zon.querySelector("b"), notis = $("vdnotis"), text = rubrik.textContent;
  const visa = t => { rubrik.textContent = t; };
  zon.classList.add("laser"); notis.hidden = true;
  try {
    visa("Läser lappen …");
    await laddaTesseract();
    const worker = await Tesseract.createWorker(["swe", "eng"], 1);
    const lasta = [];
    for (let n = 0; n < filer.length; n++) {
      if (filer.length > 1) visa(`Läser bild ${n + 1} av ${filer.length} …`);
      const bild = await createImageBitmap(filer[n]);
      const {data} = await worker.recognize(gra(bild));
      const ord = (data.words || []).filter(w => w.confidence > 60 && /[a-zåäö]{2}|\d+\s*%/i.test(w.text)).length;
      lasta.push({fil: filer[n], bild, text: data.text || "", ord});
    }
    await worker.terminate();
    const t = tolka(lasta.map(l => l.text).join("\n"), allaMarken());
    // Bilden med minst text är bilden på själva plagget.
    const plagg = [...lasta].sort((a, b) => a.ord - b.ord)[0];
    const harPlagg = lasta.length > 1 || plagg.ord < 4;
    let katVald = "", sakerhet = 0;
    vd.plagg = "";
    if (harPlagg) {
      try {
        visa("Känner igen plagget …");
        const ai = await kannIgen(plagg.bild, p => visa(p < 1 ? `Laddar ner AI:n … ${Math.round(p * 100)} %` : "Känner igen plagget …"));
        const perKat = {};
        for (const [namn, andel] of Object.entries(ai.p || {})) if (TILL_KAT[namn]) perKat[TILL_KAT[namn]] = (perKat[TILL_KAT[namn]] || 0) + andel;
        [katVald, sakerhet] = Object.entries(perKat).sort((a, b) => b[1] - a[1])[0] || ["", 0];
        vd.plagg = ai.plagg;
      } catch (e) { console.error(e); }
    }
    if (vd.bild) URL.revokeObjectURL(vd.bild);
    vd.bild = URL.createObjectURL(plagg.fil);
    if (t.marke) { vd.marke = t.marke; $("vdmarke").value = t.marke; }
    const sakerKat = katVald && sakerhet >= KAT_SAKER && kats().some(k => k.id === katVald);
    vd.kat = sakerKat ? katVald : "";
    const saknas = [!t.marke && "skriva märket", !sakerKat && "trycka på vilken sorts plagg det är"].filter(Boolean);
    notis.innerHTML = t.marke && sakerKat ? `Jag hittade <b>${esc(t.marke)}</b>. Stämmer inte märket eller kategorin? Ändra här under.`
      : t.marke ? `Jag hittade <b>${esc(t.marke)}</b>. Nu behöver du ${saknas.join(" och ")}.`
      : `Jag kunde inte läsa märket på lappen. ${saknas.length ? "Du behöver " + saknas.join(" och ") + "." : ""} Tips: en skarp bild rakt framifrån i bra ljus.`;
    notis.hidden = false;
    ritaVardera();
    if (!t.marke) $("vdmarke").focus();
  } catch (e) {
    console.error(e);
    notis.textContent = "Det gick inte att läsa bilderna just nu. Skriv märket och välj kategori själv i stället.";
    notis.hidden = false;
  } finally {
    visa(text); zon.classList.remove("laser"); $("vdfil").value = "";
  }
}

// ---------- Händelser ----------
$("vdfil").addEventListener("change", e => franBilder(e.target.files));
const zon = $("vdzon");
zon.addEventListener("dragover", e => { e.preventDefault(); zon.classList.add("over"); });
zon.addEventListener("dragleave", () => zon.classList.remove("over"));
zon.addEventListener("drop", e => { e.preventDefault(); zon.classList.remove("over"); franBilder(e.dataTransfer.files); });
$("vdmarke").addEventListener("change", () => { vd.marke = hittaMarke($("vdmarke").value); $("vdmarke").value = vd.marke; ritaVardera(); });
$("vdkat").addEventListener("click", e => {
  const b = e.target.closest("[data-k]"); if (!b) return;
  vd.kat = b.dataset.k;
  // Uppmaningen att välja kategori är gjord, så den tas bort när märket redan finns.
  const n = $("vdnotis");
  if (vd.marke && n.textContent.includes("vilken sorts plagg")) n.hidden = true;
  ritaVardera();
});
$("vdanalys").addEventListener("click", e => {
  const k = e.target.closest("[data-k]");
  if (k) { vd.kat = k.dataset.k; ritaVardera(); return; }
  if (e.target.closest("#vdborsen")) { oppnaMarke(vd.marke, vd.kat, "tradera"); return; }
  if (e.target.closest("#vdbeskriv")) {
    window.AnnonsFyll?.({abmarke: vd.marke, abplagg: vd.plagg});
    visaVy("beskrivning"); scrollTo({top: 0, behavior: "smooth"});
  }
});
$("vdanalys").addEventListener("input", e => { if (e.target.id === "vdpris") ritaVinsten(); });
})();
