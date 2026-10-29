"""Märkessidor för Google: en sida per märke med vad det säljs för i andra hand, byggd ur bors.json.

Körs när hemsidan byggs (bevaka.yml): python3 markessidor.py _site
Skriver _site/marken/index.html (alla märken), _site/marken/<märke>/index.html, sitemap.xml och robots.txt.
Sidorna är vanlig HTML utan spärr, så att Google kan läsa dem, och leder vidare till väntelistan.
"""
import html
import json
import os
import sys
import time

import marken as M

DOMAN = "https://xn--mrkesbrsen-q5a5t.se"  # märkesbörsen.se
MINST_SALDA = 5     # ett märke får en egen sida när det sålt minst så här många på 30 dagar i någon kategori
MINST_RAD = 3       # och en kategori visas på sidan från så här många sålda
INTE = {"cardigan", "övriga", "okänt", "vintage", "handgjord", "no brand", "diverse", "army", "black", "white", "svart", "vit", "navy"}
MANAD = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober",
         "november", "december"]


def e(t):
    return html.escape(str(t), quote=True)


def kr(v):
    return "–" if v is None else f"{round(v):,} kr".replace(",", " ")


def slug(m):
    return M.nyckel(m).replace(" ", "-")


def datum(dag):
    t = time.strptime(dag, "%Y-%m-%d")
    return f"{t.tm_mday} {MANAD[t.tm_mon - 1]} {t.tm_year}"


def prisandring(pts):
    """Mittenpriset nu jämfört med 30 dagar innan, i procent (None om historiken inte räcker)."""
    if len(pts) < 2 or not pts[-1][2]:
        return None
    slut = time.mktime(time.strptime(pts[-1][0], "%Y-%m-%d"))
    fore = [p for p in pts if p[2] and time.mktime(time.strptime(p[0], "%Y-%m-%d")) <= slut - 28 * 86400]
    if not fore:
        return None
    a = fore[-1][2]
    return round(100 * (pts[-1][2] - a) / a) if a else None


def marken_ur(bors):
    """{märke: [rad per kategori]} med de senaste 30 dagarnas slutpriser på Tradera."""
    kats = {k["id"]: k["namn"] for k in bors.get("kategorier") or []}
    ut = {}
    for kat, per in ((bors.get("marke") or {}).get("tradera") or {}).items():
        if kat not in kats:
            continue
        for m, pts in per.items():
            if not pts or m == M.UTAN or m.lower() in INTE or M.ar_dam(m):
                continue
            p = pts[-1]
            if not p[1] or p[1] < MINST_RAD or not p[2]:
                continue
            ut.setdefault(m, []).append({"kat": kat, "namn": kats[kat], "salda": p[1], "pris": p[2], "lag": p[3],
                                         "andring": prisandring(pts), "dag": p[0]})
    return {m: sorted(r, key=lambda x: -x["salda"]) for m, r in ut.items() if max(x["salda"] for x in r) >= MINST_SALDA}


STIL = """
:root{color-scheme:dark;--bg:#121a11;--kort:#1b2419;--yta:#222d20;--text:#eef1e6;--svag:#a3af98;--linje:#34412f;--guld:#c9a24f;--guldljus:#e6c47c;--gron:#52d394;--rod:#f07a62}
*{box-sizing:border-box}
body{margin:0;color:var(--text);font:16px/1.65 Inter,system-ui,-apple-system,"Segoe UI",sans-serif;-webkit-font-smoothing:antialiased;
  background:radial-gradient(900px 480px at 10% -5%,color-mix(in srgb,#c9a24f 18%,transparent),transparent 70%),var(--bg);background-attachment:fixed}
a{color:var(--guldljus);text-underline-offset:3px}
.inre{max-width:820px;margin:0 auto;padding:0 20px}
.meny{border-bottom:1px solid var(--linje)}
.meny .inre{display:flex;align-items:center;justify-content:space-between;gap:16px;height:64px}
.logga{display:flex;align-items:center;gap:10px;text-decoration:none;font-family:Cinzel,Georgia,serif;font-weight:700;font-size:18px;letter-spacing:.08em;color:var(--guldljus)}
.logga i{width:26px;height:26px;border-radius:8px;background:var(--guld);display:inline-flex;align-items:flex-end;justify-content:center;gap:2px;padding:6px 5px}
.logga i b{display:block;width:3px;background:#141414;border-radius:1px}
.meny nav{display:flex;gap:18px;font-size:14px}.meny nav a{color:var(--svag)}
main.inre{padding-top:40px;padding-bottom:30px}
.over{font-size:12.5px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--guldljus);margin:0 0 8px}
h1{font-size:clamp(28px,6vw,42px);line-height:1.15;letter-spacing:-.03em;margin:0 0 14px}
h2{font-size:21px;letter-spacing:-.02em;margin:34px 0 10px}
.ingress{font-size:18px;color:var(--text);margin:0 0 6px}
.datum{color:var(--svag);font-size:14px;margin:0 0 26px}
.nyckel{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:24px 0 8px}
.nyckel div{background:var(--kort);border:1px solid var(--linje);border-radius:16px;padding:16px 18px}
.nyckel span{display:block;font-size:12.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--svag)}
.nyckel b{display:block;font-size:28px;letter-spacing:-.03em;margin-top:2px;font-variant-numeric:tabular-nums}
.tabell{overflow-x:auto;background:var(--kort);border:1px solid var(--linje);border-radius:16px}
table{width:100%;border-collapse:collapse;font-size:15px}
th,td{text-align:left;padding:12px 14px;border-bottom:1px solid var(--linje);white-space:nowrap}
tr:last-child td{border-bottom:0}
th{color:var(--svag);font-weight:600;font-size:12.5px;text-transform:uppercase;letter-spacing:.06em}
td.tal,th.tal{text-align:right;font-variant-numeric:tabular-nums}
.upp{color:var(--gron)}.ned{color:var(--rod)}
.cta{margin:34px 0 8px;padding:24px;border-radius:20px;background:color-mix(in srgb,var(--guld) 14%,var(--kort));border:1px solid color-mix(in srgb,var(--guld) 45%,transparent)}
.cta h2{margin:0 0 6px}.cta p{margin:0 0 16px;color:var(--text)}
.knapp{display:inline-block;background:linear-gradient(135deg,#f0d491,#c9a24f 55%,#a8823a);color:#1a1408;font-weight:700;text-decoration:none;padding:12px 22px;border-radius:999px}
.lankar{display:flex;flex-wrap:wrap;gap:8px;padding:0;list-style:none}
.lankar a{display:inline-block;padding:7px 13px;border-radius:999px;background:var(--kort);border:1px solid var(--linje);color:var(--text);text-decoration:none;font-size:14.5px}
.lankar small{color:var(--svag)}
.last{list-style:none;padding:0;margin:0;background:var(--kort);border:1px solid var(--linje);border-radius:16px}
.last li{display:flex;justify-content:space-between;gap:12px;padding:12px 16px;border-bottom:1px solid var(--linje)}
.last li:last-child{border-bottom:0}
.last b{font-weight:600;font-size:14px;color:var(--guldljus)}
.last b{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.bokstav{font-size:15px;color:var(--guldljus);margin:26px 0 8px}
.svag{color:var(--svag)}
footer{border-top:1px solid var(--linje);padding:24px 0 40px;font-size:13.5px;color:var(--svag)}
footer .inre{display:flex;flex-wrap:wrap;gap:6px 18px}footer a{color:inherit}
@media (max-width:560px){ .nyckel{grid-template-columns:minmax(0,1fr)} .meny nav{display:none} th,td{padding:10px} .dolj-mobil{display:none} }
"""


def sida(titel, beskrivning, vag, djup, kropp):
    upp = "../" * djup
    return f"""<!doctype html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titel)}</title>
<meta name="description" content="{e(beskrivning)}">
<link rel="canonical" href="{DOMAN}/{vag}">
<meta property="og:title" content="{e(titel)}">
<meta property="og:description" content="{e(beskrivning)}">
<meta name="theme-color" content="#121a11">
<link rel="icon" href="/ikon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="32x32 48x48">
<link rel="apple-touch-icon" href="/ikon-180.png">
<link href="{upp}typsnitt/typsnitt.css" rel="stylesheet">
<script src="{upp}tillganglig.js" defer></script>
<style>{STIL}</style>
</head>
<body>
<header class="meny"><div class="inre">
  <a class="logga" href="{upp}vantelista/"><i><b style="height:6px"></b><b style="height:11px"></b><b style="height:15px"></b></i>Märkesbörsen</a>
  <nav aria-label="Meny"><a href="{upp}marken/">Alla märken</a><a href="{upp}vantelista/">Väntelistan</a></nav>
</div></header>
<main class="inre">
{kropp}
</main>
<footer><div class="inre"><span>© Märkesbörsen</span><a href="{upp}marken/">Alla märken</a><a href="{upp}integritet/">Integritet och kakor</a><a href="{upp}villkor/">Villkor</a></div></footer>
</body>
</html>
"""


LAS = ('<svg width="13" height="14" viewBox="0 0 13 14" aria-hidden="true"><rect x="1" y="6" width="11" height="8" rx="2" fill="currentColor"/>'
       '<path d="M3.5 6V4.5a3 3 0 0 1 6 0V6" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>')

CTA = """<div class="cta">
  <h2>Se alla märken, trender och vad du tjänar</h2>
  <p>Märkesbörsen visar vad märkeskläder säljs för i andra hand, vilka märken som säljer dyrast och vad du kan tjäna på ett inköp, innan du köper.</p>
  <a class="knapp" href="{upp}vantelista/">Skriv upp dig på väntelistan</a>
</div>"""


def markessida(m, rader, alla, bors):
    forst = rader[0]
    total = sum(r["salda"] for r in rader)
    uppdaterad = max(r["dag"] for r in rader)
    dyrast = max(rader, key=lambda r: r["pris"])

    # Bara ett smakprov: ett pris och antal sålda. Resten (pris per kategori, trender, prisändring) finns i
    # Märkesbörsen, så de siffrorna skrivs inte ens in i sidan.
    lasta = "".join(f'<li><span>{e(r["namn"])}</span><b>{LAS}Visas i Märkesbörsen</b></li>' for r in rader[1:8])
    text = (f'{e(m)} har sålts <b>{total}</b> gånger de senaste 30 dagarna i de kategorier Märkesbörsen mäter. '
            f'Mest säljs {e(forst["namn"].lower())}, för ungefär <b>{kr(forst["pris"])}</b>.')
    # Fler märken i samma kategori och prisklass, så att Google och besökarna hittar vidare.
    pris = {x: next(y["pris"] for y in r if y["kat"] == forst["kat"]) for x, r in alla.items()
            if x != m and any(y["kat"] == forst["kat"] for y in r)}
    grannar = sorted(pris, key=lambda x: abs(pris[x] - forst["pris"]))[:12]
    lankar = "".join(f'<li><a href="../{slug(x)}/">{e(x)}</a></li>' for x in grannar)
    kropp = f"""  <p class="over">Andrahandspriser</p>
  <h1>Vad säljs {e(m)} för i andra hand?</h1>
  <p class="ingress">{text}</p>
  <p class="datum">Uppdaterad {datum(uppdaterad)}. Räknat på sålda annonser, inte på vad säljarna begär.</p>
  <div class="nyckel">
    <div><span>Mittenpris</span><b>{kr(forst["pris"])}</b><small class="svag">{e(forst["namn"])}</small></div>
    <div><span>Sålda 30 dagar</span><b>{total}</b><small class="svag">alla kategorier</small></div>
  </div>
  {f'<h2>{e(m)} i fler kategorier</h2><ul class="last">{lasta}</ul>' if lasta else ""}
  <p class="svag">Mittenpris betyder att hälften såldes dyrare och hälften billigare. Skick, storlek och modell påverkar priset, så se siffran som vägledning.</p>
  {CTA.format(upp="../../")}
  {f'<h2>Fler märken i {e(forst["namn"].lower())}</h2><ul class="lankar">{lankar}</ul>' if lankar else ""}"""
    beskrivning = (f"{m} säljs för {kr(forst['pris'])} i mittenpris i andra hand ({forst['namn'].lower()}). "
                   f"Se hur många som sålts de senaste 30 dagarna.")
    return sida(f"Vad säljs {m} för i andra hand? · Märkesbörsen", beskrivning, f"marken/{slug(m)}/", 2, kropp)


def indexsida(alla):
    per = {}
    for m in sorted(alla, key=lambda x: M.nyckel(x)):
        b = M.nyckel(m)[:1].upper()
        per.setdefault(b if b.isalpha() else "#", []).append(m)
    delar = "".join(f'<h2 class="bokstav">{b}</h2><ul class="lankar">' + "".join(
        f'<li><a href="{slug(m)}/">{e(m)}</a></li>' for m in ms) + "</ul>"
        for b, ms in per.items())
    kropp = f"""  <p class="over">Andrahandspriser</p>
  <h1>Vad säljs märkena för i andra hand?</h1>
  <p class="ingress">{len(alla)} märken med slutpriser från sålda annonser, uppdaterat varje dag. Tryck på ett märke för att se vad det säljs för.</p>
  {CTA.format(upp="../")}
  {delar}"""
    return sida("Vad säljs märkena för i andra hand? · Märkesbörsen",
                f"Slutpriser i andra hand för {len(alla)} märken, till exempel Stone Island, Ralph Lauren och Moncler. Uppdaterat varje dag.",
                "marken/", 1, kropp)


def skriv(fil, text):
    os.makedirs(os.path.dirname(fil), exist_ok=True)
    with open(fil, "w", encoding="utf-8") as f:
        f.write(text)


def main(ut):
    try:
        with open(os.path.join(ut, "bors.json"), encoding="utf-8") as f:
            bors = json.load(f)
    except (OSError, ValueError):
        bors = {}
    alla = marken_ur(bors)
    for m, rader in alla.items():
        skriv(os.path.join(ut, "marken", slug(m), "index.html"), markessida(m, rader, alla, bors))
    skriv(os.path.join(ut, "marken", "index.html"), indexsida(alla))
    sidor = ["vantelista/", "marken/", "integritet/", "villkor/"] + [f"marken/{slug(m)}/" for m in sorted(alla)]
    skriv(os.path.join(ut, "sitemap.xml"), '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
          "".join(f"  <url><loc>{DOMAN}/{s}</loc></url>\n" for s in sidor) + "</urlset>\n")
    # Den privata delen och appen har noindex i sidorna själva, så att Google kan läsa det och låter bli dem.
    skriv(os.path.join(ut, "robots.txt"), f"User-agent: *\nAllow: /\n\nSitemap: {DOMAN}/sitemap.xml\n")
    print(f"märkessidor: {len(alla)} märken")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "_site")
