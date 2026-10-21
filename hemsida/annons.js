// Skriv beskrivning: gör en färdig annonstext att kopiera in på Vinted eller
// Tradera. Strukturen: inledning, punkter med skick, material, detaljer och
// mått, ärlig rad om eventuella fel och en kort avslutning.
(() => {
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
function init(){
  if (!$("abform")) return;
  $("abskick").innerHTML = Object.keys(SKICK).map(s => `<button type="button" class="chip" data-s="${s}">${s}</button>`).join("");
  $("abform").addEventListener("input", rita);
  $("abform").addEventListener("change", rita);
  $("abskick").addEventListener("click", e => { const b = e.target.closest("[data-s]"); if (!b) return; skick = b.dataset.s; rita(); });
  $("abkopiera").addEventListener("click", kopiera);
  $("abrensa").addEventListener("click", () => { $("abform").reset(); skick = "Mycket bra"; rita(); });
  rita();
}
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
})();
