"""Märkesbörsen: mäter hur märkena i dina alarm går på andrahandsmarknaden.

Körs efter varje botrunda (var 5:e minut) och hinner några mätningar per gång, så att varje mätning
görs ungefär en gång per dygn utan att Vinted, Tradera eller Plick får för många frågor på en gång.

Två sorters mätningar per källa och kategori:
- andel: ett stickprov av hela kategorin (t.ex. de 960 nyaste koftorna på Vinted, eller de 400 senast
  sålda på Tradera) och hur stor del av dem som är av varje märke. Det är "procent av marknaden".
- märke: en sökning på bara ett märke i kategorin, med antal annonser och pris (medianpris och billigaste
  fjärdedelen). På Tradera är det sålda annonser och slutpriser, alltså riktig efterfrågan.

Allt sparas i bors.json, som hemsidans börssida (hemsida/bors.html) visar.
"""
import argparse
import calendar
import html as H
import json
import os
import random
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request

import vinted_bot as vb

MAPP = os.path.dirname(os.path.abspath(__file__))
BORS_FIL = os.path.join(MAPP, "bors.json")
SALDA_FIL = os.path.join(MAPP, "tradera_salda.json")  # sålda Tradera-annonser vi sett (för veckohistorik)

TIDSGRANS_SEK = 240       # så länge mätningarna får hålla på per runda (GitHub kör bara ungefär var halvtimme)
MATT_IGEN_TIMMAR = 20     # en mätning görs om när den är så här gammal
FORSTA_SALDA_TIMMAR = 3   # ett Vinted-märke som bara mätts en gång mäts om så här snart, så att sålda 24 h syns direkt
TOM_IGEN_DAGAR = 5        # märken som inte har något i en kategori mäts bara om så här ofta
SPARA_DAGAR = 400         # så lång historik sparas
DAGLIGT_DAGAR = 60        # så länge sparas en punkt per dag, sedan en per vecka
ANDEL_TOPP = 30           # så många märken sparas per stickprov (plus alla alarm-märken)
VINTED_SIDOR = 10         # Vinted visar högst 10 sidor à 96 annonser
VINTED_PER_RUNDA = 40     # högst så många frågor till Vinted per runda, så att alarmen aldrig blir blockerade
TRADERA_SIDOR = 5         # 80 sålda annonser per sida
PLICK_SIDOR = 4           # 24 annonser per sida

# Kategorierna som mäts. vinted = Vinteds kategorinamn under Herr > Kläder (slås upp automatiskt),
# annars söks det på ordet. tradera/plick = sökord.
KATEGORIER = [
    {"id": "koftor", "namn": "Koftor & cardigans", "vinted": ["Koftor", "Cardigans"], "ord": "cardigan", "tradera": ["cardigan", "kofta"]},
    {"id": "stickat", "namn": "Stickade tröjor", "vinted": ["Stickade tröjor", "Tröjor med rund hals"], "ord": "stickad tröja", "tradera": ["stickad tröja"]},
    {"id": "skjortor", "namn": "Skjortor", "vinted": ["Skjortor"], "ord": "skjorta", "tradera": ["skjorta"]},
    {"id": "overshirts", "namn": "Overshirts", "vinted": [], "ord": "overshirt", "tradera": ["overshirt", "skjortjacka"]},
    {"id": "jackor", "namn": "Jackor", "vinted": ["Jackor"], "ord": "jacka", "tradera": ["jacka"]},
    {"id": "dun", "namn": "Dunjackor & västar", "vinted": ["Dunjackor"], "ord": "dunjacka", "tradera": ["dunjacka", "dunväst"]},
    {"id": "kavajer", "namn": "Kavajer", "vinted": ["Kavajer"], "ord": "kavaj", "tradera": ["kavaj"]},
    {"id": "jeans", "namn": "Jeans", "vinted": ["Jeans"], "ord": "jeans", "tradera": ["jeans"]},
]
KALLOR = ["vinted", "tradera", "plick"]


def logg(text):
    vb.logg("[börsen] " + text)


def hamta(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": vb.WEBBLASARE, "Accept": "text/html,application/xhtml+xml", "Accept-Language": "sv-SE,sv;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as svar:
        return svar.read().decode("utf-8", "replace")


def kvantil(tal, andel):
    tal = sorted(t for t in tal if t)
    if not tal:
        return None
    return round(tal[min(len(tal) - 1, int(len(tal) * andel))])


def median(tal):
    tal = [t for t in tal if t]
    return round(statistics.median(tal)) if tal else None


def normalisera(text):
    """'J.Lindeberg grå Cardigan' -> ' j lindeberg grå cardigan ' (för att hitta märken i titlar)."""
    return " " + re.sub(r"[^0-9a-zåäöøæéèü]+", " ", text.lower()).strip() + " "


def hitta_marke(titel, marken_norm):
    t = normalisera(titel)
    for norm, namn in marken_norm:  # längsta först, så "Polo Ralph Lauren" går före "Ralph Lauren"
        if norm in t:
            return namn
    return None


def marken_norm(namn):
    par = {(normalisera(m), m) for m in namn if m and len(normalisera(m).strip()) >= 2}
    return sorted(par, key=lambda p: -len(p[0]))


# ---------- Vinted ----------

class VintedKalla:
    def __init__(self, bors):
        self.v = vb.Vinted()
        self.bors = bors
        self.katalog = None

    def katalog_id(self, kat):
        """Vinteds kategorinummer under Herr > Kläder, hittat på namnet."""
        if not kat["vinted"]:
            return None
        sparade = self.bors.setdefault("vinted_kategorier", {})
        if kat["id"] in sparade:
            return sparade[kat["id"]]
        if self.katalog is None:
            text = vb.sidans_data(self.v.hamta(vb.VINTED + "/catalog?catalog_ids[]=2050"))
            i = text.find('"catalogTree":')
            trad, _ = json.JSONDecoder().raw_decode(text, i + len('"catalogTree":'))
            herr = []

            def ga(noder, inne):
                for n in noder:
                    inne2 = inne or n.get("id") == 2050
                    if inne2:
                        herr.append(n)
                    ga(n.get("catalogs") or [], inne2)
            ga(trad, False)
            self.katalog = herr
        for namn in kat["vinted"]:
            for n in self.katalog:
                if n.get("title", "").lower() == namn.lower():
                    sparade[kat["id"]] = n["id"]
                    logg("Vinted-kategori %s = %s (%s)" % (kat["id"], n["id"], n["title"]))
                    return n["id"]
        sparade[kat["id"]] = None
        return None

    def url(self, kat, marke_id=None, sida=1):
        par = [("order", "newest_first"), ("currency", "SEK")]
        kid = self.katalog_id(kat)
        if kid:
            par.append(("catalog_ids[]", kid))
        else:
            par += [("search_text", kat["ord"]), ("catalog_ids[]", 2050)]
        if marke_id:
            par.append(("brand_ids[]", marke_id))
        if sida > 1:
            par.append(("page", sida))
        return vb.VINTED + "/catalog?" + urllib.parse.urlencode(par)

    def sida(self, url):
        if not self.v.har_kakor:
            self.v.hamta(vb.VINTED + "/")
            self.v.har_kakor = True
        sida = self.v.hamta(url)
        m = re.search(r'"pagination":(\{[^{}]*\})', vb.sidans_data(sida))
        pag = json.loads(m.group(1)) if m else {}
        return vb.annonser_fran_sida(sida), pag.get("total_entries")

    def marke_id(self, namn):
        ids = self.bors.setdefault("vinted_marken", {})
        if namn not in ids:
            ids[namn] = self.v.marke_id(namn)
        return ids[namn]

    def andel(self, kat, alarm_marken):
        annonser = {}
        for s in range(1, VINTED_SIDOR + 1):
            nya, _ = self.sida(self.url(kat, sida=s))
            if not nya:
                break
            for a in nya:
                annonser[a["id"]] = a
            time.sleep(random.uniform(1.2, 2.2))
        per = {}
        for a in annonser.values():
            if a["marke"]:
                per.setdefault(a["marke"], []).append(a["pris"])
        return len(annonser), per

    def marke(self, kat, namn):
        mid = self.marke_id(namn)
        if not mid:
            return None
        # Alla sidor med märket i kategorin (högst 10 à 96), så att sålda räknas över hela Vinted och inte bara de nyaste.
        annonser, totalt = self.sida(self.url(kat, mid))
        for s in range(2, min(VINTED_SIDOR, -(-(totalt or 0) // 96)) + 1):
            time.sleep(random.uniform(1.2, 2.2))
            nya, _ = self.sida(self.url(kat, mid, sida=s))
            if not nya:
                break
            annonser += nya
        forsta = annonser[:96]
        priser = [a["pris"] for a in forsta]
        gillas = [a["gillas"] for a in forsta]
        return {"antal": totalt or 0, "tak": (totalt or 0) >= 960, "median": median(priser), "p25": kvantil(priser, 0.25),
                "gillas": round(sum(gillas) / len(gillas), 1) if gillas else None,
                "dygn": self.forsvunna(kat["id"], namn, annonser, totalt)}

    def forsvunna(self, kat_id, namn, annonser, totalt):
        """Sålda senaste dygnet på hela Vinted: Vinted visar inte sålda, så alla märkets annonser i kategorin sparas,
        och de som fanns vid förra mätningen (ungefär ett dygn sedan) men saknas nu har sålts (eller tagits bort).
        Antalet räknas om till ett dygn. Har märket fler än 960 annonser syns bara de nyaste, och då räknas bara
        de som är nyare än den äldsta som syns nu."""
        ids = sorted({int(a["id"]) for a in annonser if str(a.get("id", "")).isdigit()})
        sett = self.bors.setdefault("vinted_sett", {}).setdefault(kat_id, {})
        forra = sett.get(namn)
        nu = time.time()
        sett[namn] = [round(nu), ids]
        if not forra or not ids:
            return None
        t, gamla = forra
        dagar = (nu - t) / 86400
        if dagar < FORSTA_SALDA_TIMMAR / 24 * 0.8:  # för tätt: behåll förra mätningen som jämförelse
            sett[namn] = forra
            return None
        grans = 0 if (totalt or 0) <= len(ids) else ids[0]
        finns = set(ids)
        borta = sum(1 for i in gamla if i >= grans and i not in finns)
        return round(borta / dagar, 1)


# ---------- Tradera (sålda annonser och slutpriser) ----------

class TraderaKalla:
    def __init__(self):
        self.salda = []

    def sok(self, q, sida=1, salda=True):
        par = [("q", q)] + ([("itemStatus", "Sold")] if salda else [])
        if sida > 1:
            par.append(("paging", sida))
        text = vb.sidans_data(hamta("https://www.tradera.com/search?" + urllib.parse.urlencode(par)))
        i = text.find('"discover/receiveSearchResults"')
        if i < 0:
            raise ValueError("hittade inga sökresultat i Traderas sida")
        j = text.find('"result":', i)
        res, _ = json.JSONDecoder().raw_decode(text, j + len('"result":'))
        return res

    def ute(self, q):
        """Antal aktiva annonser (allt som ligger ute nu) för en sökning, och om Tradera slutat räkna (tak)."""
        res = self.sok(q, salda=False)
        tak = "AboveCap" in str((res.get("itemsMatched") or {}).get("translationKey", ""))
        time.sleep(random.uniform(1, 2))
        return res.get("totalItemCount") or 0, tak

    def andel(self, kat, marken):
        # Hela kategorins aktiva annonser, så att märkenas andel av allt som ligger ute kan räknas.
        self.ute_kat = [0, False]
        for q in kat["tradera"]:
            n, tak = self.ute(q)
            self.ute_kat = [self.ute_kat[0] + n, self.ute_kat[1] or tak]
        sett, per = set(), {}
        mn = marken_norm(marken)
        for q in kat["tradera"]:
            for s in range(1, TRADERA_SIDOR + 1):
                res = self.sok(q, s)
                items = res.get("items") or []
                for it in items:
                    if it.get("itemId") in sett:
                        continue
                    sett.add(it.get("itemId"))
                    m = hitta_marke(it.get("shortDescription", ""), mn) or "Övriga"
                    per.setdefault(m, []).append(it.get("price"))
                    if it.get("endDate") and it.get("price"):
                        self.salda.append((str(it.get("itemId")), it["endDate"][:10], m, it["price"]))
                pc = (res.get("pagination") or {}).get("pageCount") or 1
                time.sleep(random.uniform(1, 2))
                if s >= pc or not items:
                    break
        return len(sett), per

    def marke(self, kat, namn):
        antal, priser, tak, fart = 0, [], False, 0.0
        nn = normalisera(namn)
        idag = time.time()
        for q in kat["tradera"]:
            res = self.sok('"%s" %s' % (namn, q))
            n = res.get("totalItemCount") or 0
            info = res.get("itemsMatched") or {}
            if "AboveCap" in str(info.get("translationKey", "")):
                tak = True
            antal += n
            items = res.get("items") or []
            priser += [it.get("price") for it in items if nn in normalisera(it.get("shortDescription", ""))]
            # Sålda per vecka: Tradera visar bara det som sålts den senaste tiden, så antalet delas med hur
            # långt bak det äldsta slutdatumet i svaret ligger (minst en vecka, så att få affärer inte blåses upp).
            datum = [calendar.timegm(time.strptime(it["endDate"][:10], "%Y-%m-%d")) for it in items if it.get("endDate")]
            if n and datum:
                dagar = max(7.0, (idag - min(datum)) / 86400 + 1)
                fart += n / dagar * 7
            time.sleep(random.uniform(1, 2))
        ute = sum(self.ute('"%s" %s' % (namn, q))[0] for q in kat["tradera"])
        return {"antal": antal, "tak": tak, "median": median(priser), "p25": kvantil(priser, 0.25), "fart": round(fart, 1), "ute": ute}


# ---------- Plick ----------

def plick_kort(sida):
    """Annonserna på en av Plicks söksidor: märke, pris och länk."""
    ut = []
    for bit in sida.split('class="listing-card-component"')[1:]:
        fot = bit.split("listing-card-component__footer", 1)[-1]
        rutor = [H.unescape(t).strip() for t in re.findall(r'<(?:span|strong) class="text-truncate">\s*([^<]*?)\s*</(?:span|strong)>', fot)]
        pris = next((re.match(r"(\d[\d\s]*)\s*SEK", r) for r in rutor if re.match(r"\d[\d\s]*\s*SEK", r)), None)
        if not pris:
            continue
        # Första raden i foten är märket (kan saknas), sedan storlek och pris.
        marke = rutor[0] if rutor and not re.match(r"\d[\d\s]*\s*SEK", rutor[0]) else ""
        lank = next((l for l in re.findall(r'<a href="(/[^"]+)"', bit) if not l.startswith("/profiler/")), "")
        alt = re.search(r'alt="([^"]*)"[^>]*class="listing-card-component__card-image"|class="listing-card-component__card-image" alt="([^"]*)"', bit)
        text = re.sub(r"\s+", " ", H.unescape((alt.group(1) or alt.group(2)) if alt else ""))[:200]
        ut.append({"marke": marke, "pris": float(re.sub(r"\s", "", pris.group(1))), "text": text, "lank": lank})
    return ut


class PlickKalla:
    def sok(self, q, sida=1):
        par = [("query", q)] + ([("page", sida)] if sida > 1 else [])
        b = hamta("https://plick.se/produkter?" + urllib.parse.urlencode(par))
        return plick_kort(b), 'rel="next"' in b

    def andel(self, kat, marken):
        sett, per = set(), {}
        mn = marken_norm(marken)
        for s in range(1, PLICK_SIDOR + 1):
            kort, mer = self.sok(kat["ord"], s)
            for k in kort:
                nyckel = k["lank"] or k["text"]
                if nyckel in sett:
                    continue
                sett.add(nyckel)
                # Plick skriver märket på olika sätt (J.LINDEBERG, j.lindeberg), så samma namn som på Vinted om det går.
                m = hitta_marke(k["marke"], mn) or k["marke"] or hitta_marke(k["text"], mn) or "Övriga"
                per.setdefault(m, []).append(k["pris"])
            time.sleep(random.uniform(1, 2))
            if not mer or not kort:
                break
        return len(sett), per

    def marke(self, kat, namn):
        kort, mer = self.sok("%s %s" % (namn, kat["ord"]))
        nn = normalisera(namn)
        egna = [k for k in kort if nn in normalisera(k["marke"] or k["text"])]
        priser = [k["pris"] for k in egna]
        return {"antal": len(egna), "tak": mer and len(egna) == len(kort), "median": median(priser), "p25": kvantil(priser, 0.25)}


# ---------- Sparat ----------

def las_bors():
    bors = vb.las_json(BORS_FIL, None)
    if bors is None:
        # Ingen sparad kopia (t.ex. tömd cache på GitHub): hämta den som ligger på hemsidan.
        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if "/" in repo:
            agare, namn = repo.split("/", 1)
            try:
                bors = json.loads(hamta("https://%s.github.io/%s/bors.json" % (agare.lower(), namn)))
                logg("Hämtade historiken från hemsidan.")
            except Exception as e:
                logg("Ingen historik på hemsidan än (%s)." % e)
    bors = bors or {}
    for k in ("andel", "marke", "senast"):
        bors.setdefault(k, {})
    return bors


def spara_kompakt(fil, data):
    """Utan mellanslag, så att hemsidan laddar snabbare."""
    tmp = fil + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, fil)


def alarm_marken(sokningar):
    marken = {}
    for s in sokningar:
        for m in vb.lista(s.get("marke")):
            marken.setdefault(m, [])
            if vb.alarm_namn(s) not in marken[m]:
                marken[m].append(vb.alarm_namn(s))
    return marken


def satt_punkt(lista_, punkt):
    """En punkt per dag: dagens mätning ersätter en tidigare från samma dag.
    Äldre än DAGLIGT_DAGAR sparas bara en punkt per vecka, så filen inte växer för mycket."""
    if lista_ and lista_[-1][0] == punkt[0]:
        lista_[-1] = punkt
    else:
        lista_.append(punkt)
    grans = time.strftime("%Y-%m-%d", time.gmtime(time.time() - SPARA_DAGAR * 86400))
    dagligt = time.strftime("%Y-%m-%d", time.gmtime(time.time() - DAGLIGT_DAGAR * 86400))
    behall, veckor = [], set()
    for p in lista_:
        if p[0] < grans:
            continue
        if p[0] < dagligt:
            vecka = time.strftime("%G-%V", time.strptime(p[0], "%Y-%m-%d"))
            if vecka in veckor:
                continue
            veckor.add(vecka)
        behall.append(p)
    lista_[:] = behall


def spara_salda(bors, kat_id, nya, alarm):
    """Lägger till sålda Tradera-annonser i en egen fil och räknar andel och pris per vecka (måndag)."""
    alla = vb.las_json(SALDA_FIL, {})
    kat = alla.setdefault(kat_id, {})
    for id_, datum, marke, pris in nya:
        kat[id_] = [datum, marke, pris]
    grans = time.strftime("%Y-%m-%d", time.gmtime(time.time() - SPARA_DAGAR * 86400))
    for id_ in [i for i, v in kat.items() if v[0] < grans]:
        del kat[id_]
    spara_kompakt(SALDA_FIL, alla)
    veckor = {}
    for datum, marke, pris in kat.values():
        d = time.strptime(datum, "%Y-%m-%d")
        mandag = time.strftime("%Y-%m-%d", time.gmtime(calendar.timegm(d) - d.tm_wday * 86400))
        veckor.setdefault(mandag, {}).setdefault(marke, []).append(pris)
    ut = []
    for v in sorted(veckor):
        per = veckor[v]
        n = sum(len(p) for p in per.values())
        topp = [m for m in sorted(per, key=lambda m: -len(per[m])) if m != "Övriga"][:ANDEL_TOPP]
        marken = {m: [len(per[m]), median(per[m])] for m in dict.fromkeys(topp + [m for m in alarm if m in per])}
        ut.append([v, n, marken, n - sum(x[0] for x in marken.values())])
    bors.setdefault("tradera_veckor", {})[kat_id] = ut


def uppgifter(bors, marken):
    """Alla mätningar som behöver göras, äldst först och källorna omväxlande."""
    nu = time.time()
    per_kalla = {k: [] for k in KALLOR}
    for kalla in KALLOR:
        for kat in KATEGORIER:
            nyckel = "andel|%s|%s" % (kalla, kat["id"])
            senast = bors["senast"].get(nyckel, 0)
            saknar_ute = kalla == "tradera" and kat["id"] not in bors.get("tradera_ute", {})
            if nu - senast >= MATT_IGEN_TIMMAR * 3600 or saknar_ute:
                per_kalla[kalla].append((senast, nyckel, kalla, kat, None))
            for m in marken:
                nyckel = "marke|%s|%s|%s" % (kalla, kat["id"], m)
                senast = bors["senast"].get(nyckel, 0)
                pts = bors["marke"].get(kalla, {}).get(kat["id"], {}).get(m) or []
                tom = len(pts) >= 2 and not pts[-1][1] and not pts[-2][1]
                vanta = TOM_IGEN_DAGAR * 86400 if tom else MATT_IGEN_TIMMAR * 3600
                if kalla == "vinted" and not tom and pts and (len(pts[-1]) < 7 or pts[-1][6] is None) \
                        and m in bors.get("vinted_sett", {}).get(kat["id"], {}):
                    vanta = FORSTA_SALDA_TIMMAR * 3600
                if kalla == "tradera" and not tom and pts and len(pts[-1]) < 7:
                    vanta = 0  # mättes innan antalet annonser ute fanns med
                if nu - senast >= vanta:
                    per_kalla[kalla].append((senast, nyckel, kalla, kat, m))
    for k in per_kalla:
        # Kategoristickproven först (de behövs för att hitta märken i titlar), sedan äldst först.
        per_kalla[k].sort(key=lambda u: (u[4] is not None, u[0]))
    ut = []
    while any(per_kalla.values()):
        for k in KALLOR:
            if per_kalla[k]:
                ut.append(per_kalla[k].pop(0))
    return ut


def kanda_marken(bors, kat_id, alarm):
    """Märken att leta efter i titlar: dina alarm-märken och de vanligaste märkena på Vinted i kategorin."""
    namn = list(alarm)
    pts = bors["andel"].get("vinted", {}).get(kat_id) or []
    if pts:
        namn += list(pts[-1][2].keys())
    return namn


def mat(kalla_obj, kalla, kat, marke, bors, alarm, idag):
    if marke is None:
        n, per = kalla_obj.andel(kat, kanda_marken(bors, kat["id"], alarm))
        if not n:
            raise ValueError("tomt stickprov")
        topp = sorted(per, key=lambda m: -len(per[m]))
        spara = [m for m in topp if m != "Övriga"][:ANDEL_TOPP] + [m for m in alarm if m in per]
        marken = {m: [len(per[m]), median(per[m])] for m in dict.fromkeys(spara)}
        ovr = n - sum(v[0] for v in marken.values())
        satt_punkt(bors["andel"].setdefault(kalla, {}).setdefault(kat["id"], []), [idag, n, marken, ovr])
        if kalla == "tradera":
            n_ute, tak_ute = kalla_obj.ute_kat
            bors.setdefault("tradera_ute", {})[kat["id"]] = [idag, n_ute, 1 if tak_ute else 0]  # alla aktiva i kategorin
            spara_salda(bors, kat["id"], kalla_obj.salda, alarm)
            kalla_obj.salda = []
        return "%d annonser, störst %s" % (n, ", ".join(topp[:3]))
    r = kalla_obj.marke(kat, marke)
    if r is None:
        return "märket finns inte hos källan"
    punkt = [idag, r["antal"], r["median"], r["p25"], 1 if r.get("tak") else 0]
    if kalla == "vinted":
        punkt += [r.get("gillas"), r.get("dygn")]  # gillas i snitt, sålda senaste dygnet
    elif kalla == "tradera":
        punkt += [r.get("fart"), r.get("ute")]  # sålda per vecka, aktiva annonser ute nu
    satt_punkt(bors["marke"].setdefault(kalla, {}).setdefault(kat["id"], {}).setdefault(marke, []), punkt)
    return "%s st, median %s kr" % (r["antal"], r["median"])


def sammanfatta(bors):
    """Skriver de största märkena per kategori i loggen (antal och medianpris), så börsen går att läsa utan hemsidan."""
    for kat in KATEGORIER:
        for kalla in ("tradera", "vinted"):
            pts = bors["andel"].get(kalla, {}).get(kat["id"]) or []
            if not pts:
                continue
            _, n, marken, _ = pts[-1]
            topp = sorted(marken.items(), key=lambda x: -x[1][0])[:15]
            logg("topp %s %s (%d st): %s" % (kalla, kat["id"], n, ", ".join("%s %d/%s" % (m, v[0], v[1]) for m, v in topp)))


def vinted_sidor(bors, kat, marke):
    """Hur många sidor en Vinted-mätning hämtar: tio för ett kategoristickprov, för ett märke så många som behövs
    för alla dess annonser enligt förra mätningen."""
    if marke is None:
        return VINTED_SIDOR
    pts = bors["marke"].get("vinted", {}).get(kat["id"], {}).get(marke) or []
    antal = pts[-1][1] if pts else 96
    return max(1, min(VINTED_SIDOR, -(-(antal or 0) // 96)))


def kor(tidsgrans=TIDSGRANS_SEK, max_antal=None, bara=None):
    start = time.time()
    sokningar = vb.las_json(vb.SOKNINGAR_FIL, [])
    alarm = alarm_marken(sokningar)
    bors = las_bors()
    kallor = {}
    lista_ = uppgifter(bors, alarm)
    if bara:
        lista_ = [u for u in lista_ if u[2] == bara]
    idag = time.strftime("%Y-%m-%d", time.gmtime())
    gjorda, fel, vinted_fragor = 0, {}, 0
    for senast, nyckel, kalla, kat, marke in lista_:
        if time.time() - start > tidsgrans or (max_antal and gjorda >= max_antal):
            break
        if fel.get(kalla, 0) >= 2:  # källan krånglar just nu, försök igen nästa runda
            continue
        kostar = vinted_sidor(bors, kat, marke) if kalla == "vinted" else 0
        if kalla == "vinted" and vinted_fragor + kostar > VINTED_PER_RUNDA:
            continue
        if kalla not in kallor:
            kallor[kalla] = {"vinted": lambda: VintedKalla(bors), "tradera": TraderaKalla, "plick": PlickKalla}[kalla]()
        try:
            if kalla == "vinted":
                vinted_fragor += kostar
            svar = mat(kallor[kalla], kalla, kat, marke, bors, alarm, idag)
            bors["senast"][nyckel] = time.time()
            gjorda += 1
            logg("%s: %s" % (nyckel, svar))
        except Exception as e:
            fel[kalla] = fel.get(kalla, 0) + 1
            logg("%s: fel, %s" % (nyckel, e))
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 429) and kalla == "vinted":
                fel[kalla] = 99
        time.sleep(random.uniform(0.5, 1.5))
    sammanfatta(bors)
    # Släng mätningar av märken som inte längre finns i något alarm.
    for kalla in bors["marke"].values():
        for kat in kalla.values():
            for m in list(kat):
                if m not in alarm:
                    del kat[m]
    for kat in bors.get("vinted_sett", {}).values():
        for m in list(kat):
            if m not in alarm:
                del kat[m]
    bors["senast"] = {k: v for k, v in bors["senast"].items() if not k.startswith("marke|") or k.split("|", 3)[3] in alarm}
    bors["kategorier"] = [{"id": k["id"], "namn": k["namn"]} for k in KATEGORIER]
    bors["alarm"] = alarm
    bors["uppdaterad"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    kvar = len(lista_) - gjorda
    bors["ko"] = kvar
    spara_kompakt(BORS_FIL, bors)
    logg("%d mätningar gjorda, %d väntar på nästa runda." % (gjorda, kvar))


def main():
    p = argparse.ArgumentParser(description="Märkesbörsen")
    p.add_argument("--sekunder", type=int, default=TIDSGRANS_SEK, help="hur länge den får mäta")
    p.add_argument("--antal", type=int, help="högst så många mätningar")
    p.add_argument("--kalla", choices=KALLOR, help="bara en källa")
    a = p.parse_args()
    kor(a.sekunder, a.antal, a.kalla)


if __name__ == "__main__":
    main()
