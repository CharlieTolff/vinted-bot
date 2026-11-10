// Märkesbörsens lås: köp, inloggning och börsens siffror, som bara den som betalat får hämta.
// Själva låset ligger hos Cloudflare (mappen betalning i repot).
const LAS = "https://markesborsen.markesborsen.workers.dev";

const Las = {
  token(){ try { return localStorage.getItem("inloggning") || ""; } catch { return ""; } },
  sparaToken(t){ try { localStorage.setItem("inloggning", t); } catch {} },
  loggaUt(){ try { localStorage.removeItem("inloggning"); } catch {} },
  // Ägaren kommer in med GitHub-nyckeln som hans egna sidor redan sparat, kunderna med sin inloggning.
  huvud(){
    const t = Las.token();
    if (t) return {Authorization: "Bearer " + t};
    let gh = "";
    try { gh = JSON.parse(localStorage.getItem("nyckel") || "\"\""); } catch {}
    return gh ? {Authorization: "GitHub " + gh} : null;
  },
  async anrop(vag, data){
    const r = await fetch(LAS + vag, data === undefined
      ? {headers: Las.huvud() || {}, cache: "no-store"}
      : {method: "POST", headers: {"Content-Type": "application/json", ...(Las.huvud() || {})}, body: JSON.stringify(data)});
    const svar = await r.json().catch(() => ({}));
    if (!r.ok) throw Object.assign(new Error(svar.fel || "Något gick fel. Försök igen om en stund."), {status: r.status});
    return svar;
  },
  // Börsens siffror, eller null om man inte är inloggad (eller inte har betalat).
  async bors(){
    if (!Las.huvud()) return null;
    try { return await Las.anrop("/data"); }
    catch (e) { if (e.status === 401 && Las.token()) Las.loggaUt(); return null; }
  },
  async status(){
    if (!Las.huvud()) return {inne: false};
    try { return await Las.anrop("/status"); } catch { return {inne: false}; }
  },
  // Skickar vidare till Stripes kassa.
  async kop(plan){ location.href = (await Las.anrop("/kop", {plan})).url; },
  async loggaIn(mejl){ return Las.anrop("/logga-in", {mejl}); },
  async hantera(){ location.href = (await Las.anrop("/hantera", {})).url; },
  // Tillbaka från Stripe (?betalt=) eller från inloggningsmejlet (?inloggning=): spara inloggningen.
  // Ger true om man just loggade in, ett felmeddelande om något gick snett, annars null.
  async tillbaka(){
    const q = new URLSearchParams(location.search);
    const betalt = q.get("betalt"), lank = q.get("inloggning");
    if (!betalt && !lank) return null;
    history.replaceState(null, "", location.pathname + location.hash);
    try {
      const svar = betalt ? await Las.anrop("/klar", {session: betalt}) : await Las.anrop("/token", {inloggning: lank});
      Las.sparaToken(svar.token);
      return true;
    } catch (e) {
      return e.message;
    }
  },
};
