// Märkesbörsens lås och betalning (Cloudflare Worker).
//
// Börsens siffror (bors.json) ligger här i stället för öppet på hemsidan. Den som betalat via Stripe får en
// inloggning (en signerad nyckel i webbläsaren) och kan hämta siffrorna. På en ny enhet loggar man in med sin
// mejl: en inloggningslänk skickas via Brevo.
//
// Hemligheter (läggs in från GitHub när låset läggs upp): STRIPE_KEY, BREVO_KEY.
// Inställningar i wrangler.toml: HEMSIDA, FRIA (mejladresser som alltid kommer in, t.ex. ägaren).

const PLANER = {
  manad: {namn: "Märkesbörsen, 1 månad", ore: 14900, man: 1, prenumeration: true},
  halvar: {namn: "Märkesbörsen, 6 månader", ore: 69900, man: 6},
  ar: {namn: "Märkesbörsen, 1 år", ore: 129900, man: 12},
};
const LANK_GILTIG = 30 * 60e3;          // inloggningslänken i mejlet
const INNE_GILTIG = 365 * 864e5;         // inloggningen i webbläsaren (prenumerationen kollas ändå)
const KOLLA_IGEN = 6 * 3600e3;           // hur ofta en prenumeration kollas mot Stripe
const URSPRUNG = [/^https:\/\/xn--mrkesbrsen-q5a5t\.se$/, /^https:\/\/charlietolff\.github\.io$/, /^http:\/\/localhost(:\d+)?$/];

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const ursprung = req.headers.get("Origin") || "";
    const cors = URSPRUNG.some(r => r.test(ursprung)) ? {
      "Access-Control-Allow-Origin": ursprung, "Vary": "Origin",
      "Access-Control-Allow-Headers": "Authorization, Content-Type", "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    } : {};
    if (req.method === "OPTIONS") return new Response(null, {status: 204, headers: cors});
    const svar = (data, status = 200, extra = {}) => new Response(typeof data === "string" ? data : JSON.stringify(data),
      {status, headers: {"Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...cors, ...extra}});
    try {
      const vag = url.pathname.replace(/\/+$/, "");
      const kropp = req.method === "POST" ? await req.json().catch(() => ({})) : {};
      const hemsida = hemsidaFor(ursprung, env);
      if (vag === "/kop" && req.method === "POST") return svar(await kop(kropp, hemsida, env));
      if (vag === "/klar" && req.method === "POST") return svar(await klar(kropp, env));
      if (vag === "/logga-in" && req.method === "POST") return svar(await loggaIn(kropp, hemsida, env));
      if (vag === "/token" && req.method === "POST") return svar(await bytLank(kropp, env));
      const vem = await inloggad(req, env);
      if (vag === "/status") return svar(vem ? {inne: true, mejl: vem.mejl, plan: vem.plan || null, till: vem.till || null, prenumeration: !!vem.prenumeration} : {inne: false});
      if (vag === "/data") {
        if (!vem) return svar({fel: "inte inloggad"}, 401);
        const data = await env.DATA.get("bors");
        return data ? svar(data) : svar({fel: "ingen data än"}, 503);
      }
      if (vag === "/hantera" && req.method === "POST") {
        if (!vem || !vem.kund) return svar({fel: "inte inloggad"}, 401);
        const s = await stripe(env, "POST", "billing_portal/sessions", {customer: vem.kund, return_url: hemsida + "/borsen/app.html"});
        return svar({url: s.url});
      }
      return svar({fel: "finns inte"}, 404);
    } catch (e) {
      return svar({fel: e.visas || "Något gick fel. Försök igen om en stund.", ...(e.orsak ? {orsak: e.orsak} : {})}, e.status || 500);
    }
  },
};

function hemsidaFor(ursprung, env) {
  return URSPRUNG.some(r => r.test(ursprung)) ? ursprung : env.HEMSIDA;
}

function fel(text, status = 400) {
  const e = new Error(text);
  e.visas = text; e.status = status;
  return e;
}

function rensaMejl(m) {
  m = String(m || "").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(m) || m.length > 200) throw fel("Skriv en riktig mejladress.");
  return m;
}

// ---- Stripe ----

function formular(obj, pre = "", ut = new URLSearchParams()) {
  for (const [k, v] of Object.entries(obj)) {
    if (v === undefined || v === null) continue;
    const nyckel = pre ? `${pre}[${k}]` : k;
    if (typeof v === "object") formular(v, nyckel, ut);
    else ut.append(nyckel, String(v));
  }
  return ut;
}

async function stripe(env, metod, vag, data) {
  const r = await fetch(`https://api.stripe.com/v1/${vag}` + (metod === "GET" && data ? "?" + formular(data) : ""), {
    method: metod,
    headers: {Authorization: `Bearer ${env.STRIPE_KEY}`, ...(metod === "POST" ? {"Content-Type": "application/x-www-form-urlencoded"} : {})},
    body: metod === "POST" ? formular(data || {}) : undefined,
  });
  const svar = await r.json();
  if (!r.ok) {
    // Orsaken (utan Stripes text, som kan visa delar av nyckeln) så att felet går att hitta.
    const e = fel("Betalningen krånglade. Försök igen om en stund.", 502);
    const f = svar.error || {};
    e.orsak = [r.status, f.type, f.code, f.param].filter(Boolean).join(" ");
    throw e;
  }
  return svar;
}

async function kop(k, hemsida, env) {
  const plan = PLANER[k.plan];
  if (!plan) throw fel("Välj ett av alternativen.");
  const mejl = k.mejl ? rensaMejl(k.mejl) : undefined;
  const pris = {currency: "sek", unit_amount: plan.ore, product_data: {name: plan.namn}};
  if (plan.prenumeration) pris.recurring = {interval: "month"};
  const s = await stripe(env, "POST", "checkout/sessions", {
    mode: plan.prenumeration ? "subscription" : "payment",
    line_items: {0: {quantity: 1, price_data: pris}},
    customer_email: mejl,
    customer_creation: plan.prenumeration ? undefined : "always",
    allow_promotion_codes: "true",
    locale: "sv",
    metadata: {plan: k.plan},
    success_url: `${hemsida}/borsen/?betalt={CHECKOUT_SESSION_ID}`,
    cancel_url: `${hemsida}/borsen/#pris`,
  });
  return {url: s.url};
}

// Efter betalningen: kolla med Stripe att det är betalt, spara kunden och logga in.
async function klar(k, env) {
  const id = String(k.session || "");
  if (!/^cs_[A-Za-z0-9_]+$/.test(id)) throw fel("Länken stämmer inte.");
  const s = await stripe(env, "GET", `checkout/sessions/${id}`);
  if (s.status !== "complete" || !["paid", "no_payment_required"].includes(s.payment_status)) throw fel("Betalningen är inte klar än.", 402);
  const mejl = rensaMejl(s.customer_details && s.customer_details.email);
  const plan = (s.metadata && s.metadata.plan) || "manad";
  const gammal = await hamtaKund(env, mejl);
  const kund = {mejl, plan, kund: s.customer || (gammal && gammal.kund) || null, kollad: Date.now()};
  if (s.subscription) {
    kund.prenumeration = s.subscription;
    Object.assign(kund, await prenumerationsLage(env, s.subscription));
  } else {
    // Förskottsbetalt: tiden läggs på eventuell tid som redan finns kvar.
    const fran = Math.max(Date.now(), (gammal && gammal.till) || 0);
    const d = new Date(fran);
    d.setMonth(d.getMonth() + PLANER[plan].man);
    kund.till = d.getTime();
    if (gammal && gammal.prenumeration) kund.prenumeration = gammal.prenumeration;
    // Samma betalning ska inte kunna förlänga två gånger.
    const sedd = await env.DATA.get(`session:${id}`);
    if (sedd) kund.till = (gammal && gammal.till) || kund.till;
    else await env.DATA.put(`session:${id}`, "1", {expirationTtl: 400 * 86400});
  }
  await env.DATA.put(`kund:${mejl}`, JSON.stringify(kund));
  return {token: await signera(env, {m: mejl, t: "inne", u: Date.now() + INNE_GILTIG}), mejl};
}

async function prenumerationsLage(env, id) {
  const p = await stripe(env, "GET", `subscriptions/${id}`);
  const slut = (p.current_period_end || (p.items && p.items.data[0] && p.items.data[0].current_period_end) || 0) * 1000;
  return {aktiv: ["active", "trialing", "past_due"].includes(p.status), till: slut};
}

async function hamtaKund(env, mejl) {
  const k = await env.DATA.get(`kund:${mejl}`);
  return k ? JSON.parse(k) : null;
}

// Har mejladressen tillgång just nu? Prenumerationer kollas mot Stripe med jämna mellanrum.
async function harTillgang(env, mejl) {
  const k = await hamtaKund(env, mejl);
  // Fria adresser (ägaren) kommer alltid in, men har de köpt något visas köpet (så att det går att testa).
  if (String(env.FRIA || "").toLowerCase().split(",").map(s => s.trim()).includes(mejl)) return k && k.kund ? k : {mejl, plan: "fri"};
  if (!k) return null;
  if (k.prenumeration && Date.now() - (k.kollad || 0) > KOLLA_IGEN) {
    try {
      const lage = await prenumerationsLage(env, k.prenumeration);
      const forskott = k.plan !== "manad" ? k.till : 0;
      k.aktiv = lage.aktiv;
      k.till = Math.max(forskott || 0, lage.till);
      k.kollad = Date.now();
      await env.DATA.put(`kund:${mejl}`, JSON.stringify(k));
    } catch { /* Stripe svarar inte: lita på det vi har en stund till */ }
  }
  const ok = (k.prenumeration && k.aktiv) || (k.till && k.till > Date.now());
  return ok ? k : null;
}

async function inloggad(req, env) {
  const h = req.headers.get("Authorization") || "";
  if (h.startsWith("GitHub ")) return agare(env, h.slice(7));
  const t = h.startsWith("Bearer ") ? await las(env, h.slice(7)) : null;
  if (!t || t.t !== "inne" || t.u < Date.now()) return null;
  return harTillgang(env, t.m);
}

// Ägaren kommer in med samma GitHub-nyckel som hans egna sidor redan använder (sparad i hans webbläsare):
// den som får skriva i repot får se allt. Svaret sparas en timme så att GitHub inte frågas varje gång.
async function agare(env, gh) {
  if (!/^[A-Za-z0-9_]{20,255}$/.test(gh)) return null;
  const hash = b64(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(gh)));
  const sparad = await env.DATA.get(`agare:${hash}`);
  if (sparad) return sparad === "1" ? {mejl: "agare", plan: "fri"} : null;
  const r = await fetch(`https://api.github.com/repos/${env.REPO}`, {headers: {Authorization: `Bearer ${gh}`, "User-Agent": "markesborsen"}});
  const ok = r.ok && !!((await r.json()).permissions || {}).push;
  await env.DATA.put(`agare:${hash}`, ok ? "1" : "0", {expirationTtl: 3600});
  return ok ? {mejl: "agare", plan: "fri"} : null;
}

// ---- Inloggning med mejl ----

async function loggaIn(k, hemsida, env) {
  const mejl = rensaMejl(k.mejl);
  // Högst ett mejl per minut till samma adress.
  if (await env.DATA.get(`skickat:${mejl}`)) return {ok: true};
  await env.DATA.put(`skickat:${mejl}`, "1", {expirationTtl: 60});
  if (!(await harTillgang(env, mejl))) {
    await skickaMejl(env, mejl, "Ingen aktiv prenumeration",
      `<p>Hej!</p><p>Någon (förhoppningsvis du) försökte logga in på Märkesbörsen med den här mejladressen, men vi hittar ingen aktiv prenumeration.</p>
       <p><a href="${hemsida}/borsen/#pris">Se priserna och kom igång här</a>.</p><p>Har du betalat med en annan mejladress? Logga in med den i stället.</p>`);
    return {ok: true};
  }
  const lank = await signera(env, {m: mejl, t: "lank", u: Date.now() + LANK_GILTIG});
  await skickaMejl(env, mejl, "Din inloggning till Märkesbörsen",
    `<p>Hej!</p><p>Tryck på knappen för att logga in på Märkesbörsen. Länken gäller i 30 minuter.</p>
     <p><a href="${hemsida}/borsen/?inloggning=${lank}" style="display:inline-block;background:#a8823a;color:#141414;font-weight:700;padding:12px 22px;border-radius:999px;text-decoration:none">Logga in</a></p>
     <p>Bad du inte om att logga in kan du strunta i det här mejlet.</p>`);
  return {ok: true};
}

async function bytLank(k, env) {
  const t = await las(env, String(k.inloggning || ""));
  if (!t || t.t !== "lank" || t.u < Date.now()) throw fel("Länken har gått ut. Be om en ny.", 401);
  if (!(await harTillgang(env, t.m))) throw fel("Vi hittar ingen aktiv prenumeration.", 402);
  return {token: await signera(env, {m: t.m, t: "inne", u: Date.now() + INNE_GILTIG}), mejl: t.m};
}

async function skickaMejl(env, till, amne, html) {
  const r = await fetch("https://api.brevo.com/v3/smtp/email", {
    method: "POST",
    headers: {"api-key": env.BREVO_KEY, "Content-Type": "application/json", Accept: "application/json"},
    body: JSON.stringify({sender: {name: "Märkesbörsen", email: env.AVSANDARE}, to: [{email: till}], subject: amne,
      htmlContent: `<div style="font-family:Arial,sans-serif;font-size:16px;line-height:1.5;color:#1b2219">${html}<p>Hälsningar<br>Märkesbörsen</p></div>`}),
  });
  if (!r.ok) throw fel("Mejlet kunde inte skickas. Försök igen om en stund.", 502);
}

// ---- Signerade nycklar ----

const b64 = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const fran64 = s => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));

async function nyckel(env) {
  // Signeringsnyckeln härleds ur Stripe-nyckeln, så att det inte behövs en hemlighet till.
  const bas = await crypto.subtle.importKey("raw", new TextEncoder().encode(env.STRIPE_KEY), {name: "HMAC", hash: "SHA-256"}, false, ["sign"]);
  const rå = await crypto.subtle.sign("HMAC", bas, new TextEncoder().encode("markesborsen-inloggning"));
  return crypto.subtle.importKey("raw", rå, {name: "HMAC", hash: "SHA-256"}, false, ["sign", "verify"]);
}

async function signera(env, data) {
  const del = b64(new TextEncoder().encode(JSON.stringify(data)));
  return del + "." + b64(await crypto.subtle.sign("HMAC", await nyckel(env), new TextEncoder().encode(del)));
}

async function las(env, token) {
  const [del, sig] = String(token).split(".");
  if (!del || !sig) return null;
  try {
    const ok = await crypto.subtle.verify("HMAC", await nyckel(env), fran64(sig), new TextEncoder().encode(del));
    return ok ? JSON.parse(new TextDecoder().decode(fran64(del))) : null;
  } catch {
    return null;
  }
}
