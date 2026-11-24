// Guiden: första gången någon öppnar börsen visas en kort rundtur. Det som förklaras lyses upp i en ruta,
// resten av sidan blir suddig, och en ruta bredvid visar med en liten animation hur det fungerar.
// Man går vidare med ett tryck var som helst, mellanslag, Enter eller piltangenten. Esc hoppar över.
// Guiden visas bara en gång (sparas i webbläsaren) och kan startas igen från menyn.
(() => {
const SEDD = "bors-guidad-v1";
const STEG = [
  {rubrik: "Välkommen till Märkesbörsen", text: "Här är en snabb rundtur genom allt du kan göra. Tryck var som helst, eller på mellanslag, för att gå vidare.", demo: "valkommen"},
  {mal: '.grupp[data-grupp="vardera"]', rubrik: "Fota lappen", text: "Ta en bild på lappen i plagget. Börsen läser märket och visar vad det brukar säljas för.", demo: "lapp"},
  {mal: '.grupp[data-grupp="marknad"]', rubrik: "Marknaden", text: "Se vilka märken som säljer mest, vilka som ökar och var marginalen är störst. Tryck på Bevaka märket, så får du ett mejl när priset ändras.", demo: "marknad"},
  {mal: '.grupp[data-grupp="vinst"]', rubrik: "Räkna din vinst", text: "Skriv vad du betalar och se direkt vad du får över när plagget säljs.", demo: "vinst"},
  {mal: '.grupp[data-grupp="bokforing"]', rubrik: "Bokföring", text: "Lägg in det du köper och säljer, så räknar börsen ihop vinsten åt dig.", demo: "bokforing"},
  {mal: '.grupp[data-grupp="bilder"]', rubrik: "Fixa annonsen", text: "Gör bakgrunden vit och få en färdig annonstext att kopiera, så ser annonsen proffsig ut.", demo: "annons"},
  {rubrik: "Nu är du redo", text: "Börja med att fota lappen på ett plagg du har hemma. Vill du se guiden igen finns den längst ner i menyn.", demo: "klart", sist: true},
];

const DEMO = {
  valkommen: `<div class="gdv gdvalk"><i></i><i></i><i></i><span>Märkesbörsen</span></div>`,
  lapp: `<div class="gdv gdlapp">
      <div class="gdlappen"><b>RALPH LAUREN</b><small>100% COTTON · M</small><i class="gdskanna"></i></div>
      <div class="gdsvar"><small>Hittade</small><b>Ralph Lauren · Stickat</b><small>Säljs normalt för</small><b class="gdguld">350 kr</b></div>
    </div>`,
  marknad: `<div class="gdv gdmarknad">
      <div><span>Ralph Lauren</span><i style="--b:88%"></i><b class="gdupp">+18 %</b></div>
      <div><span>Nudie Jeans</span><i style="--b:66%"></i><b class="gdupp">+12 %</b></div>
      <div><span>Morris</span><i style="--b:48%"></i><b class="gdupp">+9 %</b></div>
    </div>`,
  vinst: `<div class="gdv gdvinst">
      <div><small>Du betalar</small><b>199 kr</b></div><span>→</span>
      <div><small>Säljs för</small><b>350 kr</b></div><span>=</span>
      <div class="gdres"><small>Din vinst</small><b>+151 kr</b></div>
    </div>`,
  bokforing: `<div class="gdv gdbok">
      <div class="gdboktopp"><small>Vinst den här månaden</small><b>+2 340 kr</b></div>
      <svg viewBox="0 0 200 60" preserveAspectRatio="none" aria-hidden="true"><path d="M2 54 L30 48 L58 50 L86 36 L114 38 L142 22 L170 18 L198 6"/></svg>
    </div>`,
  annons: `<div class="gdv gdannons">
      <div class="gdfoto"><svg viewBox="0 0 64 64" aria-hidden="true"><path d="M22 10l10 6 10-6 14 8-5 12-6-3v27H19V27l-6 3-5-12z"/></svg></div>
      <div class="gdtext"><i style="--b:92%"></i><i style="--b:78%"></i><i style="--b:85%"></i><i style="--b:50%"></i></div>
    </div>`,
  klart: `<div class="gdv gdklart"><svg viewBox="0 0 52 52" aria-hidden="true"><circle cx="26" cy="26" r="23"/><path d="M15 27l7 7 15-16"/></svg></div>`,
};

const CSS = `
.gdpanel{position:fixed;z-index:9000;background:rgba(6,10,6,.58);-webkit-backdrop-filter:blur(5px);backdrop-filter:blur(5px);transition:all .35s ease;cursor:pointer}
.gdring{position:fixed;z-index:9001;border:2px solid #e6c47c;border-radius:14px;box-shadow:0 0 0 4px rgba(230,196,124,.18),0 0 28px rgba(230,196,124,.45);transition:all .35s ease;cursor:pointer;pointer-events:auto}
.gdring.tom{opacity:0}
.gdkort{position:fixed;z-index:9002;width:min(360px,calc(100vw - 32px));background:#1b2419;color:#eef1e6;border:1px solid #34412f;border-radius:18px;
  box-shadow:0 2px 4px #0006,0 30px 60px -20px #000;padding:16px 16px 14px;transition:top .35s ease,left .35s ease,opacity .25s ease;font-size:14.5px;line-height:1.45}
.gdkort h2{font-family:"Playfair Display",Georgia,serif;font-size:21px;margin:12px 0 4px;color:#eef1e6}
.gdkort p{margin:0;color:#c9d1bf}
.gdkort .gdfot{display:flex;align-items:center;gap:10px;margin-top:14px}
.gdkort .gdprickar{display:flex;gap:5px;margin-right:auto}
.gdkort .gdprickar i{width:6px;height:6px;border-radius:50%;background:#34412f}
.gdkort .gdprickar i.pa{background:#e6c47c;width:16px;border-radius:3px}
.gdkort button{font:inherit;font-size:13.5px;border-radius:10px;padding:8px 14px;cursor:pointer;border:1px solid #34412f;background:#222d20;color:#eef1e6}
.gdkort button.gdnasta{background:linear-gradient(135deg,#f0d491,#c9a24f 55%,#a8823a);color:#1a1408;border-color:transparent;font-weight:700}
.gdkort button.gdhoppa{background:none;border-color:transparent;color:#9ba890;padding:8px 6px}
.gdkort button.gdhem{display:block;width:100%;margin-top:12px;text-align:left;background:#222d20;color:#e6c47c;font-weight:600}
.gdkort .gdtips{font-size:12px;color:#9ba890;margin-top:8px}
.gdexempel{position:absolute;z-index:1;top:22px;right:24px;font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:#9ba890}
@media (prefers-reduced-motion:reduce){.gdpanel,.gdring,.gdkort{transition:none}}
`;

let steg = 0, el = null, aktiv = false, fokusFore = null;

function bygg(){
  if (el) return el;
  const s = document.createElement("style"); s.textContent = CSS; document.head.appendChild(s);
  // Animationerna i rutan delas med startsidan (demo.css).
  if (!document.querySelector('link[href$="demo.css"]')) document.head.appendChild(Object.assign(document.createElement("link"), {rel: "stylesheet", href: "demo.css"}));
  el = {paneler: [0, 1, 2, 3].map(() => Object.assign(document.createElement("div"), {className: "gdpanel"})),
        ring: Object.assign(document.createElement("div"), {className: "gdring"}),
        kort: Object.assign(document.createElement("div"), {className: "gdkort"})};
  el.kort.setAttribute("role", "dialog"); el.kort.setAttribute("aria-modal", "true"); el.kort.setAttribute("aria-label", "Guide");
  for (const p of [...el.paneler, el.ring]) p.addEventListener("click", nasta);
  el.kort.addEventListener("click", e => {
    if (e.target.closest(".gdhoppa") || e.target.closest("[data-hemskarm]")) return stang();  // hemskärmen sköts av hemskarm.js
    if (e.target.closest(".gdfota")) { stang(); window.visaVy?.("vardera"); scrollTo({top: 0}); return; }
    if (e.target.closest(".gdbak")) return ga(steg - 1);
    nasta();  // ett tryck var som helst på rutan går också vidare
  });
  return el;
}

function ritaKort(){
  const s = STEG[steg], k = el.kort;
  k.innerHTML = `<span class="gdexempel">${s.demo === "valkommen" || s.demo === "klart" ? "" : "Exempel"}</span>${DEMO[s.demo]}
    <h2>${s.rubrik}</h2><p aria-live="polite">${s.text}</p>
    ${s.sist && window.Hemskarm?.kan() ? `<button type="button" class="gdhem" data-hemskarm>Lägg börsen på hemskärmen, så öppnar du den som en app</button>` : ""}
    <div class="gdfot"><div class="gdprickar" aria-hidden="true">${STEG.map((_, i) => `<i class="${i === steg ? "pa" : ""}"></i>`).join("")}</div>
      ${s.sist ? `<button type="button" class="gdhoppa">Utforska själv</button><button type="button" class="gdnasta gdfota">Fota en lapp</button>`
        : `<button type="button" class="gdhoppa">Hoppa över</button><button type="button" class="gdnasta">${steg === 0 ? "Visa mig" : "Nästa"}</button>`}</div>
    ${steg === 0 ? `<div class="gdtips">${matchMedia("(hover:none)").matches ? "Tryck var som helst för att gå vidare." : "Tryck på mellanslag eller klicka för att gå vidare."}</div>` : ""}`;
  k.querySelector(".gdnasta").focus({preventScroll: true});
}

function placera(){
  if (!aktiv) return;
  const s = STEG[steg], m = s.mal && document.querySelector(s.mal);
  const vw = innerWidth, vh = innerHeight, kort = el.kort, kb = kort.offsetWidth, kh = kort.offsetHeight;
  let r = null;
  if (m && m.offsetParent) {
    const b = m.getBoundingClientRect(), pad = 6;
    r = {x: Math.max(0, b.left - pad), y: Math.max(0, b.top - pad), w: b.width + 2 * pad, h: b.height + 2 * pad};
  }
  // Fyra suddiga paneler runt hålet. Utan mål täcker den första hela skärmen.
  const [a, b, c, d] = el.paneler;
  const satt = (p, x, y, w, h) => Object.assign(p.style, {left: x + "px", top: y + "px", width: Math.max(0, w) + "px", height: Math.max(0, h) + "px"});
  if (r) {
    satt(a, 0, 0, vw, r.y); satt(b, 0, r.y + r.h, vw, vh - r.y - r.h);
    satt(c, 0, r.y, r.x, r.h); satt(d, r.x + r.w, r.y, vw - r.x - r.w, r.h);
    satt(el.ring, r.x, r.y, r.w, r.h); el.ring.classList.remove("tom");
  } else {
    satt(a, 0, 0, vw, vh); satt(b, 0, vh, vw, 0); satt(c, 0, 0, 0, 0); satt(d, vw, 0, 0, 0);
    satt(el.ring, vw / 2, vh / 2, 0, 0); el.ring.classList.add("tom");
  }
  // Rutan med förklaringen: bredvid målet på en stor skärm, under (eller över) det på mobilen, annars i mitten.
  let x = (vw - kb) / 2, y = (vh - kh) / 2;
  if (r) {
    if (vw >= 900 && r.x + r.w + 24 + kb <= vw - 16) { x = r.x + r.w + 24; y = Math.min(Math.max(16, r.y + r.h / 2 - kh / 2), vh - kh - 16); }
    else if (r.y + r.h + 16 + kh <= vh - 12) y = r.y + r.h + 16;
    else if (r.y - 16 - kh >= 12) y = r.y - 16 - kh;
  }
  Object.assign(kort.style, {left: Math.round(Math.max(16, x)) + "px", top: Math.round(Math.max(12, y)) + "px"});
}

function ga(i){
  if (i < 0) return;
  if (i >= STEG.length) return stang();
  steg = i;
  const m = STEG[steg].mal && document.querySelector(STEG[steg].mal);
  if (m) m.scrollIntoView({block: "nearest", inline: "nearest"});
  ritaKort(); placera();
}
function nasta(){ ga(steg + 1); }

function tangent(e){
  if (!aktiv) return;
  if (e.key === "Escape") { e.preventDefault(); return stang(); }
  if (e.key === "ArrowLeft") { e.preventDefault(); return ga(steg - 1); }
  if (e.target.closest && e.target.closest(".gdkort button")) return;  // knappen sköter sig själv
  if (e.key === " " || e.key === "Enter" || e.key === "ArrowRight") { e.preventDefault(); nasta(); }
}

function starta(){
  if (aktiv) return;
  bygg(); aktiv = true; fokusFore = document.activeElement;
  document.body.append(...el.paneler, el.ring, el.kort);
  ga(0);
}
function stang(){
  if (!aktiv) return;
  aktiv = false;
  for (const n of [...el.paneler, el.ring, el.kort]) n.remove();
  try { localStorage.setItem(SEDD, "1"); } catch {}
  if (fokusFore && fokusFore.focus) fokusFore.focus({preventScroll: true});
}

addEventListener("keydown", tangent, true);
addEventListener("resize", placera);
addEventListener("scroll", placera, {passive: true});

const sedd = () => { try { return !!localStorage.getItem(SEDD); } catch { return true; } };
window.Guide = {
  starta,
  // Anropas när börsen har laddat: första gången (eller med ?guide i adressen) startar guiden.
  forsta(){ if (!this.vantar && (/[?&]guide\b/.test(location.search) || !sedd())) { this.vantar = true; setTimeout(starta, 500); } },
};
if (window.BORS_KLAR) window.Guide.forsta();
document.getElementById("visaguide")?.addEventListener("click", e => { e.preventDefault(); starta(); });
})();
