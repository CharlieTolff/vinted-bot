// Gör det man kan klicka på nåbart med tangentbordet: Tab flyttar dit, Enter eller mellanslag klickar.
// Rader, rutor och kort som bara har en klickfunktion i koden hittas på att muspekaren blir en hand.
(function () {
  const NATIVA = "a[href],button,input,select,textarea,summary,label,[tabindex],[contenteditable]";
  const stil = document.createElement("style");
  stil.textContent = ":focus-visible{outline:2px solid #e6c47c!important;outline-offset:2px;box-shadow:0 0 0 6px #1b2219}";
  document.head.appendChild(stil);

  function klickbar(el) {
    if (el.closest(NATIVA)) return false;
    if (getComputedStyle(el).cursor !== "pointer") return false;
    const far = el.parentElement;
    return !far || getComputedStyle(far).cursor !== "pointer";
  }
  function fixa(rot) {
    const lista = rot.nodeType === 1 ? [rot, ...rot.querySelectorAll("*")] : [];
    for (const el of lista) {
      if (!el.isConnected || el.dataset.tangent || !klickbar(el)) continue;
      el.dataset.tangent = "1";
      el.tabIndex = 0;
      // Tabellrader och rubriker behåller sin roll, så att skärmläsare fortfarande läser tabellen rätt.
      if (!/^(TR|TH|TD|LI)$/.test(el.tagName) && !el.getAttribute("role")) el.setAttribute("role", "button");
    }
  }
  let vantar = new Set(), planerad = false;
  new MutationObserver(m => {
    for (const x of m) x.addedNodes.forEach(n => vantar.add(n));
    if (planerad) return;
    planerad = true;
    requestAnimationFrame(() => { planerad = false; const nu = vantar; vantar = new Set(); nu.forEach(fixa); });
  }).observe(document.documentElement, {childList: true, subtree: true});
  addEventListener("keydown", e => {
    const el = e.target;
    if (!el.dataset || !el.dataset.tangent || (e.key !== "Enter" && e.key !== " ")) return;
    e.preventDefault();
    el.dispatchEvent(new MouseEvent("click", {bubbles: true, cancelable: true}));
  });
  if (document.readyState === "loading") addEventListener("DOMContentLoaded", () => fixa(document.body));
  else fixa(document.body);
})();
