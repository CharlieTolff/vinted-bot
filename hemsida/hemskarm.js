// Lägg Märkesbörsen på hemskärmen: knappar med data-hemskarm visas bara när det går,
// och visar webbläsarens egen fråga (Android, Chrome, Edge) eller hur man gör på iPhone.
(() => {
if ("serviceWorker" in navigator && location.pathname.startsWith("/borsen/")) navigator.serviceWorker.register("/borsen/sw.js").catch(() => {});
let fraga = null;
const installerad = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
const iphone = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
const visa = () => document.querySelectorAll("[data-hemskarm]").forEach(b => b.hidden = installerad() || !(fraga || iphone));
window.Hemskarm = {kan: () => !installerad() && !!(fraga || iphone)};
addEventListener("beforeinstallprompt", e => { e.preventDefault(); fraga = e; visa(); });
addEventListener("appinstalled", () => { fraga = null; visa(); });
function instruktion(){
  let d = document.getElementById("hemskarmdialog");
  if (!d) {
    d = document.createElement("dialog"); d.id = "hemskarmdialog"; d.className = "litendialog";
    d.innerHTML = `<h2 style="margin-top:0">Lägg börsen på hemskärmen</h2>
      <ol style="margin:0 0 14px;padding-left:20px;line-height:1.6">
        <li>Tryck på <b>Dela</b> <svg viewBox="0 0 24 24" width="18" height="18" style="vertical-align:-3px" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-label="Dela-knappen"><path d="M12 3v12M8 7l4-4 4 4"/><path d="M6 11H5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1"/></svg> längst ner i Safari.</li>
        <li>Välj <b>Lägg till på hemskärmen</b>.</li>
        <li>Tryck på <b>Lägg till</b>. Nu finns Märkesbörsen bland dina appar.</li>
      </ol>
      <div style="display:flex;justify-content:flex-end"><button type="button" class="knapp primar">Okej</button></div>`;
    d.querySelector("button").onclick = () => d.close();
    document.body.appendChild(d);
  }
  d.showModal();
}
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-hemskarm]"); if (!b) return;
  e.preventDefault();
  if (fraga) { fraga.prompt(); try { await fraga.userChoice; } catch {} fraga = null; visa(); }
  else instruktion();
});
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", visa); else visa();
})();
