"""Märkesbörsen: mäter vilka märken som säljer på andrahandsmarknaden, för vad och hur snabbt.

Körs efter varje botrunda och hinner några mätningar per gång, så att varje mätning görs ungefär en gång
per dygn utan att Vinted, Tradera eller Plick får för många frågor på en gång.

Källorna:
- Tradera: alla sålda och osålda annonser i herrkategorierna (t.ex. Herrkläder > Skjortor), med slutpris,
  märke (som säljaren valt), när den lades upp och när den såldes. Det är riktiga affärer i Sverige och
  grunden för det mesta börsen visar: vad märket säljs för, hur många som säljs, hur snabbt och hur stor
  chansen är att det säljs.
- Vinted: de ~960 senast upplagda annonserna per kategori (vad som läggs ut och vad det kostar att köpa),
  och för märkena i dina alarm alla deras annonser i kategorin.
- Plick: de senaste annonserna per kategori, som jämförelse.

Märkesnamnen slås ihop (marken.py), så att t.ex. "Polo Ralph Lauren" och "RALPH Ralph Lauren" räknas som
Ralph Lauren. Allt sammanställs i bors.json under "marknad", som hemsidans börssida (hemsida/bors.html) visar.
"""
import argparse
import bisect
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
from collections import Counter

import marken as M
import vinted_bot as vb

MAPP = os.path.dirname(os.path.abspath(__file__))
BORS_FIL = os.path.join(MAPP, "bors.json")
AFFAR_FIL = os.path.join(MAPP, "tradera_affarer.json")  # alla sålda och osålda Tradera-annonser vi sett
EGNA_FIL = os.path.join(MAPP, "borskategorier.json")  # kategorier som lagts till från hemsidan
VERSION = 2

TIDSGRANS_SEK = 240       # så länge mätningarna får hålla på per runda
MATT_IGEN_TIMMAR = 20     # en mätning görs om när den är så här gammal
OSALDA_IGEN_TIMMAR = 44   # osålda Tradera-annonser behövs inte lika ofta
FORSTA_SALDA_TIMMAR = 3   # ett Vinted-märke som bara mätts en gång mäts om så här snart, så att sålda syns direkt
TOM_IGEN_DAGAR = 5        # märken som inte har något i en kategori mäts bara om så här ofta
SPARA_DAGAR = 400         # så lång historik sparas i bors.json
DAGLIGT_DAGAR = 60        # så länge sparas en punkt per dag, sedan en per vecka
ANDEL_TOPP = 30           # så många märken sparas per Vinted- och Plick-stickprov (plus alla alarm-märken)
VINTED_SIDOR = 10         # Vinted visar högst 10 sidor à 96 annonser
VINTED_PER_RUNDA = 40     # högst så många frågor till Vinted per runda, så att alarmen aldrig blir blockerade
VINTED_KOLLA = 3          # så många försvunna annonser per märke som kollas om de verkligen sålts
PLICK_SIDOR = 4           # 24 annonser per sida
PLICK_MARKE_SIDOR = 2     # per märke
FONSTER = 30              # börsen visar de senaste 30 dagarna och jämför med 30 dagar innan
TRADERA_STARTAD = 62      # varje dag hämtas alla sålda annonser som lagts upp de senaste 62 dagarna (köp nu ligger ute i 60)
OSALDA_STARTAD = 35       # osålda behövs bara för de senaste 30 dagarna
TRADERA_LANGST = 40       # så länge nästan alla sålda annonser legat ute (för att veta hur långt bak historiken är komplett)
TRADERA_BAKAT = 120       # första gången hämtas så här långt bak, några sidor per runda
TRADERA_BAKAT_SIDOR = 20  # så många sidor bakåt per runda
TRADERA_MAX_SIDOR = 125   # Tradera visar högst 125 sidor à 80 annonser
TRADERA_SIDTAK = 10000    # alltså högst så många annonser per sökning
TRADERA_UTE_SIDOR = 40    # så många sidor aktiva annonser per runda (alla gås igenom en gång per dygn)
GAMLA_TOPP = 60           # så många märken per kategori får egna diagram (de som sålt mest), plus de med flest ute
UTE_TOPP = 30
AFFAR_DAGAR = 200         # så länge Tradera-affärerna sparas
TITEL_DAGAR = 130         # så länge titlarna sparas (för att hitta märket igen om märkeslistan blir bättre)
TRADERA_HERR = {302074, 340304}  # Traderas Herrkläder och Herrskor

# Kategorierna som mäts. vinted = Vinteds kategorinamn under Herr (slås upp automatiskt), annars söks det på
# ordet. tradera_id = Traderas kategorier under Herrkläder. tradera = sökord, för att hitta kategorin för
# egna kategorier. ord = sökord på Plick.
BAS_KATEGORIER = [
    {"id": "koftor", "namn": "Koftor & cardigans", "vinted": ["Koftor", "Cardigans"], "ord": "cardigan",
     "tradera": ["cardigan"], "tradera_id": [343837]},
    {"id": "stickat", "namn": "Stickade tröjor", "vinted": ["Stickade tröjor", "Tröjor med rund hals"], "ord": "stickad tröja",
     "tradera": ["stickad tröja"], "tradera_id": [1000656]},
    {"id": "skjortor", "namn": "Skjortor", "vinted": ["Skjortor"], "ord": "skjorta", "tradera": ["skjorta"], "tradera_id": [1639]},
    {"id": "overshirts", "namn": "Overshirts", "vinted": [], "ord": "overshirt", "tradera": ["overshirt"], "tradera_id": [1000696]},
    {"id": "dun", "namn": "Dunjackor & västar", "vinted": ["Dunjackor"], "ord": "dunjacka", "tradera": ["dunjacka"],
     "tradera_id": [1000695, 344184]},
    {"id": "jeans", "namn": "Jeans", "vinted": ["Jeans"], "ord": "jeans", "tradera": ["jeans"], "tradera_id": [340327]},
]
KATEGORIER = list(BAS_KATEGORIER)  # plus de egna, när börsen körs
KALLOR = ["vinted", "tradera", "plick"]
VINTED_HERR = 5  # Herr på Vinted (kläder, skor, accessoarer)


def egna_kategorier():
    """Kategorier som lagts till från börsen. Bara namnet behövs: Vinted-kategorin letas upp på namnet
    under Herr, Tradera-kategorin på sökordet, och sökordet blir namnet om inget annat anges."""
    ut, sett = [], {k["id"] for k in BAS_KATEGORIER}
    for k in vb.las_json(EGNA_FIL, []):
        namn = (k.get("namn") or "").strip()
        kid = re.sub(r"[^a-z0-9]+", "-", normalisera(k.get("id") or namn)).strip("-")
        if not namn or not kid or kid in sett:
            continue
        sett.add(kid)
        ord_ = (k.get("ord") or namn).strip().lower()
        ut.append({"id": kid, "namn": namn, "egen": True, "ord": ord_,
                   "vinted": vb.lista(k.get("vinted")) or [namn],
                   "tradera": vb.lista(k.get("tradera")) or [ord_],
                   "tradera_id": [int(x) for x in vb.lista(k.get("tradera_id")) if str(x).isdigit()]})
    return ut


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
    """'J.Lindeberg grå Cardigan' -> ' j lindeberg grå cardigan '."""
    return " " + re.sub(r"[^0-9a-zåäöøæéèü]+", " ", text.lower()).strip() + " "


def dagstr(t):
    return time.strftime("%Y-%m-%d", time.gmtime(t))


def tid(dag):
    return calendar.timegm(time.strptime(dag, "%Y-%m-%d"))


# ---------- Vinted ----------

def vinted_status(v, id_):
    """'såld', 'borta' (borttagen eller dold) eller 'finns' för en Vinted-annons."""
    try:
        text = vb.sidans_data(v.hamta(vb.VINTED + "/items/%s" % id_))
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return "borta"
        raise
    if re.search(r'"item_id":"%s"[^{}]*"title":"Såld"' % id_, text) or '"is_closed":true' in text:
        return "såld"
    m = re.search(r'"can_buy":(true|false)[^{}]*?"is_hidden":(true|false)', text)
    if m and m.group(2) == "true":
        return "borta"
    return "finns"


class VintedKalla:
    def __init__(self, bors):
        self.v = vb.Vinted()
        self.bors = bors
        self.katalog = None

    def katalog_id(self, kat):
        """Vinteds kategorinummer under Herr, hittat på namnet (Herr > Kläder först, sedan resten av Herr)."""
        if not kat["vinted"]:
            return None
        sparade = self.bors.setdefault("vinted_kategorier", {})
        if kat["id"] in sparade:
            return sparade[kat["id"]]
        if self.katalog is None:
            text = vb.sidans_data(self.v.hamta(vb.VINTED + "/catalog?catalog_ids[]=2050"))
            i = text.find('"catalogTree":')
            trad, _ = json.JSONDecoder().raw_decode(text, i + len('"catalogTree":'))
            klader, herr = [], []

            def ga(noder, inne, kl):
                for n in noder:
                    inne2, kl2 = inne or n.get("id") == VINTED_HERR, kl or n.get("id") == 2050
                    if kl2:
                        klader.append(n)
                    elif inne2:
                        herr.append(n)
                    ga(n.get("catalogs") or [], inne2, kl2)
            ga(trad, False, False)
            self.katalog = klader + herr
        for namn in kat["vinted"]:
            for n in self.katalog:
                if n.get("title", "").lower() == namn.lower():
                    sparade[kat["id"]] = n["id"]
                    logg("Vinted-kategori %s = %s (%s)" % (kat["id"], n["id"], n["title"]))
                    return n["id"]
        sparade[kat["id"]] = None
        return None

    def url(self, kat, marke_ids=None, sida=1):
        par = [("order", "newest_first"), ("currency", "SEK")]
        kid = self.katalog_id(kat)
        if kid:
            par.append(("catalog_ids[]", kid))
        else:
            par += [("search_text", kat["ord"]), ("catalog_ids[]", VINTED_HERR if kat.get("egen") else 2050)]
        for mid in marke_ids or []:
            par.append(("brand_ids[]", mid))
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

    def marke_ids(self, namn):
        """Alla Vinted-märken som är samma märke, t.ex. Ralph Lauren = Ralph Lauren, Polo Ralph Lauren, RALPH Ralph Lauren."""
        ids = self.bors.setdefault("vinted_marke_ids", {})
        if namn not in ids:
            hittade = []
            for ord_ in [namn] + M.MARKEN.get(namn, [])[:2]:
                try:
                    svar = self.v.api("/api/v2/brands?" + urllib.parse.urlencode({"keyword": ord_})).get("brands") or []
                except Exception as e:
                    logg("kunde inte slå upp märket %s på Vinted: %s" % (ord_, e))
                    return []  # försök igen nästa gång
                for b in svar:
                    if M.kanon(b.get("title", "")) == namn and b.get("id") not in hittade:
                        hittade.append(b["id"])
                time.sleep(random.uniform(0.8, 1.5))
            ids[namn] = hittade[:12]
            logg("Vinted-märken för %s: %s" % (namn, hittade[:12]))
        return ids[namn]

    def andel(self, kat):
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
            m = M.kanon(a["marke"]) or M.UTAN
            if M.ar_dam(m):
                continue
            per.setdefault(m, []).append(a["pris"])
        return sum(len(p) for p in per.values()), per

    def marke(self, kat, namn):
        mids = self.marke_ids(namn)
        if not mids:
            return None
        # Alla sidor med märket i kategorin (högst 10 à 96), så att sålda räknas över hela Vinted och inte bara de nyaste.
        annonser, totalt = self.sida(self.url(kat, mids))
        for s in range(2, min(VINTED_SIDOR, -(-(totalt or 0) // 96)) + 1):
            time.sleep(random.uniform(1.2, 2.2))
            nya, _ = self.sida(self.url(kat, mids, sida=s))
            if not nya:
                break
            annonser += nya
        priser = [a["pris"] for a in annonser]
        gillas = [a["gillas"] for a in annonser[:96]]
        return {"antal": totalt or 0, "tak": (totalt or 0) >= 960, "median": median(priser), "p25": kvantil(priser, 0.25),
                "gillas": round(sum(gillas) / len(gillas), 1) if gillas else None,
                "dygn": self.salda(kat["id"], namn, annonser, totalt)}

    def salda(self, kat_id, namn, annonser, totalt):
        """Sålda per dygn på Vinted. Vinted visar inte sålda, så märkets annonser sparas, och de som fanns vid
        förra mätningen men saknas nu är kandidater. Många av dem finns kvar (Vinted visar inte alltid samma
        annonser) eller har tagits bort, så några av dem kollas, och bara andelen som verkligen är sålda räknas."""
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
        borta = [i for i in gamla if i >= grans and i not in finns]
        if not borta:
            return 0.0
        utfall = Counter()
        for i in random.sample(borta, min(VINTED_KOLLA, len(borta))):
            time.sleep(random.uniform(1.0, 1.8))
            try:
                utfall[vinted_status(self.v, i)] += 1
            except Exception:
                pass
        kollade = sum(utfall.values())
        if not kollade:
            return None
        return round(len(borta) * utfall["såld"] / kollade / dagar, 1)


# ---------- Tradera (sålda och osålda annonser) ----------

def belopp(v):
    if isinstance(v, dict):
        v = v.get("amount") or v.get("value")
    try:
        return round(float(v))
    except (TypeError, ValueError):
        return 0


class TraderaKalla:
    def __init__(self, bors, deadline=None):
        self.bors = bors
        self.deadline = deadline or time.time() + TIDSGRANS_SEK

    def sok(self, par):
        """par = sökparametrar, eller bara sökord (då söks sålda annonser)."""
        if isinstance(par, str):
            par = [("q", par), ("itemStatus", "Sold")]
        text = vb.sidans_data(hamta("https://www.tradera.com/search?" + urllib.parse.urlencode(par)))
        i = text.find('"discover/receiveSearchResults"')
        if i < 0:
            raise ValueError("hittade inga sökresultat i Traderas sida")
        j = text.find('"result":', i)
        res, _ = json.JSONDecoder().raw_decode(text, j + len('"result":'))
        return res

    def filter(self, kat):
        """Traderas kategorier för en av börsens kategorier. Egna kategorier letas upp på sökordet: de
        vanligaste kategorierna bland sålda annonser som ligger under Herrkläder eller Herrskor."""
        if kat.get("tradera_id"):
            return [("categoryId", c) for c in kat["tradera_id"]]
        sparade = self.bors.setdefault("tradera_kategorier", {})
        if kat["id"] not in sparade:
            res = self.sok([("q", kat["tradera"][0]), ("itemStatus", "Sold")])
            antal = Counter(it.get("categoryId") for it in res.get("items") or [] if it.get("categoryId"))
            ids = []
            for cid, n in antal.most_common(4):
                if n < 5:
                    break
                time.sleep(random.uniform(1, 2))
                vag = self.sok([("categoryId", cid), ("itemStatus", "Sold")]).get("categoryPath") or []
                if any(p.get("id") in TRADERA_HERR for p in vag):
                    ids.append(cid)
            sparade[kat["id"]] = ids
            logg("Tradera-kategorier för %s: %s" % (kat["id"], ids))
        return [("categoryId", c) for c in sparade[kat["id"]]] or [("q", q) for q in kat["tradera"]]

    def ute(self, kat):
        """Antal aktiva annonser i kategorin just nu."""
        n = 0
        for f in self.filter(kat):
            n += self.sok([f]).get("totalItemCount") or 0
            time.sleep(random.uniform(1, 2))
        return n

    def ute_delar(self, kat):
        """Sökningarna som tillsammans täcker alla aktiva annonser i kategorin, var och en under Traderas sidtak.
        Stora kategorier delas upp på privat/företag och auktion/köp nu (en annons som är både auktion och köp nu
        kommer med i båda och räknas en gång). Returnerar (sökningar, antal aktiva i hela kategorin)."""
        delar, tot = [], 0
        for f in self.filter(kat):
            n = self.sok([f]).get("totalItemCount") or 0
            tot += n
            time.sleep(random.uniform(0.8, 1.6))
            if n <= TRADERA_SIDTAK:
                delar.append([list(f)])
            else:
                delar += [[list(f), ["sellerType", s], ["itemType", t]] for s in ("Private", "Company") for t in ("Auction", "FixedPrice")]
        return delar, tot

    def svep(self, kat, till):
        """Går igenom alla aktiva annonser i kategorin, nyaste först, TRADERA_UTE_SIDOR sidor per runda. till är
        var den är (sparas mellan rundorna). Returnerar True när hela kategorin är genomgången."""
        if not till.get("delar"):
            delar, tot = self.ute_delar(kat)
            till.clear()
            till.update({"delar": delar, "tot": tot, "i": 0, "sida": 1, "ids": {}})
        elif till["sida"] > 1:
            # En sida tillbaka: annonser som avslutats sedan förra rundan har flyttat fram resten av listan.
            till["sida"] -= 1
        ids, n = till["ids"], 0
        while till["i"] < len(till["delar"]) and n < TRADERA_UTE_SIDOR and time.time() < self.deadline - 5:
            sida = till["sida"]
            res = self.sok([tuple(p) for p in till["delar"][till["i"]]] + ([("paging", sida)] if sida > 1 else []))
            items = res.get("items") or []
            for it in items:
                if it.get("itemId"):
                    p = self.post(it, False)
                    ids[str(it["itemId"])] = [p[0], p[6], p[7]]
            n += 1
            sidor = min((res.get("pagination") or {}).get("pageCount") or 1, TRADERA_MAX_SIDOR)
            if not items or sida >= sidor:
                till["i"], till["sida"] = till["i"] + 1, 1
            else:
                till["sida"] = sida + 1
            time.sleep(random.uniform(0.8, 1.6))
        return till["i"] >= len(till["delar"])

    @staticmethod
    def post(it, salt):
        """[slutdag, startdag, pris, säljare, företag, såld, märket säljaren valt, titel]"""
        attr = {a.get("name"): a.get("values") or [] for a in it.get("attributes") or [] if isinstance(a, dict)}
        pris = (belopp(it.get("soldPrice")) if salt else 0) or belopp(it.get("price"))
        return [(it.get("endDate") or "")[:10], (it.get("startDate") or "")[:10], pris,
                it.get("sellerMemberId"), 1 if it.get("sellerIsCompany") else 0, 1 if salt else 0,
                str((attr.get("brand") or [""])[0] or ""), (it.get("shortDescription") or "")[:90]]

    def affarer(self, kat, status, bara_bakat=False):
        """Alla annonser i kategorin som avslutats (status Sold eller Unsold) och lades upp de senaste 62 dagarna
        (osålda 35), nyaste först. Första gången fortsätter den bakåt (TRADERA_BAKAT dagar), några sidor per runda.
        bara_bakat: bara fortsätt bakåt där förra rundan slutade. Returnerar {annons-id: post}."""
        nu = time.time()
        grans = dagstr(nu - (TRADERA_STARTAD if status == "Sold" else OSALDA_STARTAD) * 86400)
        bak_grans = dagstr(nu - TRADERA_BAKAT * 86400)
        bakat = self.bors.setdefault("tradera_bakat", {})
        ut = {}
        for f in self.filter(kat):
            nyckel = "%s|%s|%s" % (kat["id"], status, f[1])
            # Osålda behövs bara för de senaste 30 dagarna, så de hämtas aldrig längre bak.
            bak = bakat.get(nyckel, 1 if status == "Sold" else 0)

            def sida(s):
                res = self.sok([f, ("itemStatus", status), ("sortBy", "AddedOn")] + ([("paging", s)] if s > 1 else []))
                items = res.get("items") or []
                for it in items:
                    if it.get("itemId") and it.get("endDate"):
                        ut[str(it["itemId"])] = self.post(it, status == "Sold")
                starter = [(it.get("startDate") or "")[:10] for it in items if it.get("startDate")]
                time.sleep(random.uniform(0.8, 1.6))
                return items, (res.get("pagination") or {}).get("pageCount") or 1, max(starter) if starter else ""

            s = 1
            while not bara_bakat and s <= TRADERA_MAX_SIDOR:
                items, sidor, nyast = sida(s)
                if not items or s >= sidor:
                    bak = 0  # hela kategorin hämtad
                    break
                if nyast < grans:
                    break
                s += 1
            if bak:
                s, n = max(bak, s + 1), 0
                while time.time() < self.deadline and n < TRADERA_BAKAT_SIDOR:
                    items, sidor, nyast = sida(s)
                    n += 1
                    if not items or s >= min(sidor, TRADERA_MAX_SIDOR) or nyast < bak_grans:
                        s = 0
                        break
                    s += 1
                bak = s
                if not bak:
                    logg("Tradera %s: hela historiken bakåt hämtad" % nyckel)
            bakat[nyckel] = bak
        return ut


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
    def __init__(self, extra):
        self.extra = extra  # fler märken att leta efter i texten

    def sok(self, q, sida=1):
        par = [("query", q)] + ([("page", sida)] if sida > 1 else [])
        b = hamta("https://plick.se/produkter?" + urllib.parse.urlencode(par))
        return plick_kort(b), 'rel="next"' in b

    def andel(self, kat):
        sett, per = set(), {}
        for s in range(1, PLICK_SIDOR + 1):
            kort, mer = self.sok(kat["ord"], s)
            for k in kort:
                nyckel = k["lank"] or k["text"]
                if nyckel in sett:
                    continue
                sett.add(nyckel)
                m = M.kanon(k["marke"])
                if not m or m == M.UTAN:
                    m = M.i_titel(k["text"], self.extra) or m or M.UTAN
                if M.ar_dam(m):
                    continue
                per.setdefault(m, []).append(k["pris"])
            time.sleep(random.uniform(1, 2))
            if not mer or not kort:
                break
        return sum(len(p) for p in per.values()), per

    def marke(self, kat, namn):
        """Märkets annonser när man söker på märket och kategorins ord (högst PLICK_MARKE_SIDOR sidor). Bara annonser
        där märket är just det här (samma gemensamma namn) räknas."""
        priser, sett, mer = [], set(), False
        for s in range(1, PLICK_MARKE_SIDOR + 1):
            kort, mer = self.sok("%s %s" % (namn, kat["ord"]), s)
            for k in kort:
                nyckel = k["lank"] or k["text"]
                if nyckel in sett:
                    continue
                sett.add(nyckel)
                m = M.kanon(k["marke"])
                if not m or m == M.UTAN:
                    m = M.i_titel(k["text"], [namn])
                if m == namn:
                    priser.append(k["pris"])
            time.sleep(random.uniform(1, 2))
            if not mer or not kort:
                break
        return {"antal": len(priser), "tak": mer, "median": median(priser), "p25": kvantil(priser, 0.25)}


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
    if bors.get("version", 1) < VERSION:
        migrera(bors)
    return bors


def sla_ihop_punkt(p):
    """En andelspunkt [dag, n, {märke: [antal, median, (p25)]}, övriga] med märkena ihopslagna."""
    d, n, marken, ovr = p[:4]
    ny = {}
    for m, v in marken.items():
        k = M.kanon(m) or M.UTAN
        if k == M.UTAN or M.ar_dam(k):
            ovr += v[0]
            continue
        if k in ny:
            a = ny[k]
            tot = a[0] + v[0]
            ny[k] = [tot, round(((a[1] or 0) * a[0] + (v[1] or 0) * v[0]) / tot) if tot else None]
        else:
            ny[k] = list(v[:2])
    return [d, n, ny, ovr]


def migrera(bors):
    """Från version 1: märkena slås ihop, och Traderas gamla mätningar (sökord i stället för herrkategorier,
    så att dam- och barnkläder kom med) tas bort. Tradera mäts om från grunden med rätt kategorier."""
    logg("Uppgraderar börsen: slår ihop märken och mäter om Tradera med herrkategorierna.")
    for kalla in ("vinted", "plick"):
        for kat, pts in (bors["andel"].get(kalla) or {}).items():
            bors["andel"][kalla][kat] = [sla_ihop_punkt(p) for p in pts]
    bors["andel"].pop("tradera", None)
    for kalla in ("tradera", "plick"):
        bors["marke"].pop(kalla, None)
    nya = {}
    for kat, mm in (bors["marke"].get("vinted") or {}).items():
        # Den serie som redan heter som det gemensamma namnet går först, annars den längsta.
        for m, pts in sorted(mm.items(), key=lambda x: (M.kanon(x[0]) != x[0], -len(x[1]))):
            k = M.kanon(m)
            if k and k != M.UTAN:
                nya.setdefault(kat, {}).setdefault(k, pts)
    bors["marke"]["vinted"] = nya
    for k in ("tradera_veckor", "tradera_ute", "vinted_marken", "vinted_sett"):
        bors.pop(k, None)
    bors["senast"] = {k: v for k, v in bors["senast"].items() if k.startswith("andel|vinted|") or k.startswith("andel|plick|")}
    bors["version"] = VERSION


def spara_kompakt(fil, data):
    """Utan mellanslag, så att hemsidan laddar snabbare."""
    tmp = fil + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, fil)


def alarm_marken(sokningar):
    """{märke: [alarm]} med märkena under sina gemensamma namn ("morris" och "Morris" blir samma)."""
    marken = {}
    for s in sokningar:
        for m in vb.lista(s.get("marke")):
            k = M.kanon(m)
            if not k or k == M.UTAN:
                continue
            marken.setdefault(k, [])
            if vb.alarm_namn(s) not in marken[k]:
                marken[k].append(vb.alarm_namn(s))
    return marken


def satt_punkt(lista_, punkt):
    """En punkt per dag: dagens mätning ersätter en tidigare från samma dag.
    Äldre än DAGLIGT_DAGAR sparas bara en punkt per vecka, så filen inte växer för mycket."""
    if lista_ and lista_[-1][0] == punkt[0]:
        lista_[-1] = punkt
    else:
        lista_.append(punkt)
    grans = dagstr(time.time() - SPARA_DAGAR * 86400)
    dagligt = dagstr(time.time() - DAGLIGT_DAGAR * 86400)
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


def spara_affarer(kat_id, nya):
    alla = vb.las_json(AFFAR_FIL, {})
    kat = alla.setdefault(kat_id, {})
    kat.update(nya)
    grans, titelgrans = dagstr(time.time() - AFFAR_DAGAR * 86400), dagstr(time.time() - TITEL_DAGAR * 86400)
    for id_ in [i for i, v in kat.items() if v[0] < grans]:
        del kat[id_]
    for v in kat.values():
        if v[0] < titelgrans:
            v[7] = ""
    spara_kompakt(AFFAR_FIL, alla)


def uppgifter(bors, marken):
    """Alla mätningar som behöver göras, äldst först och källorna omväxlande."""
    nu = time.time()
    per_kalla = {k: [] for k in KALLOR}
    for kat in KATEGORIER:
        for typ, kalla, timmar in (("andel", "vinted", MATT_IGEN_TIMMAR), ("andel", "plick", MATT_IGEN_TIMMAR),
                                   ("salda", "tradera", MATT_IGEN_TIMMAR), ("osalda", "tradera", OSALDA_IGEN_TIMMAR)):
            nyckel = "%s|%s|%s" % (typ, kalla, kat["id"])
            senast = bors["senast"].get(nyckel, 0)
            if nu - senast >= timmar * 3600:
                per_kalla[kalla].append((senast, nyckel, kalla, kat, typ, None))
            elif typ == "salda" and any(v for k, v in (bors.get("tradera_bakat") or {}).items() if k.startswith(kat["id"] + "|Sold|")):
                # Historiken bakåt hämtas klart så fort det går, inte bara en gång per dygn.
                nyckel = "bakat|tradera|" + kat["id"]
                per_kalla["tradera"].append((bors["senast"].get(nyckel, 0), nyckel, "tradera", kat, "bakat", None))
        # Alla aktiva annonser på Tradera gås igenom en gång per dygn, några sidor per runda.
        nyckel = "ute|tradera|" + kat["id"]
        senast = bors["senast"].get(nyckel, 0)
        if kat["id"] in (bors.get("tradera_svep") or {}) or nu - senast >= MATT_IGEN_TIMMAR * 3600:
            per_kalla["tradera"].append((senast, nyckel, "tradera", kat, "ute", None))
        for m in marken:
            for kalla in ("vinted", "plick"):
                nyckel = "marke|%s|%s|%s" % (kalla, kat["id"], m)
                senast = bors["senast"].get(nyckel, 0)
                pts = bors["marke"].get(kalla, {}).get(kat["id"], {}).get(m) or []
                tom = len(pts) >= 2 and not pts[-1][1] and not pts[-2][1]
                vanta = TOM_IGEN_DAGAR * 86400 if tom else MATT_IGEN_TIMMAR * 3600
                if kalla == "vinted" and not tom and pts and (len(pts[-1]) < 7 or pts[-1][6] is None) \
                        and m in bors.get("vinted_sett", {}).get(kat["id"], {}):
                    vanta = FORSTA_SALDA_TIMMAR * 3600
                if nu - senast >= vanta:
                    per_kalla[kalla].append((senast, nyckel, kalla, kat, "marke", m))
    for k in per_kalla:
        # Kategorimätningarna först (de behövs för att hitta märken i titlar), sedan äldst först.
        per_kalla[k].sort(key=lambda u: (u[5] is not None, u[0]))
    ut = []
    while any(per_kalla.values()):
        for k in KALLOR:
            if per_kalla[k]:
                ut.append(per_kalla[k].pop(0))
    return ut


def kanda_marken(bors, alarm):
    """Fler märken att leta efter i titlar: dina alarm-märken och de största märkena på Vinted."""
    namn = set(alarm)
    for kat in (bors["andel"].get("vinted") or {}).values():
        if kat:
            namn.update(kat[-1][2].keys())
    return sorted(namn)


def spara_andel(bors, kalla, kat, n, per, alarm, idag):
    topp = sorted((m for m in per if m != M.UTAN), key=lambda m: -len(per[m]))
    spara = topp[:ANDEL_TOPP] + [m for m in alarm if m in per]
    marken = {m: [len(per[m]), median(per[m]), kvantil(per[m], 0.25)] for m in dict.fromkeys(spara)}
    ovr = n - sum(v[0] for v in marken.values())
    satt_punkt(bors["andel"].setdefault(kalla, {}).setdefault(kat["id"], []), [idag, n, marken, ovr])
    return "%d annonser, störst %s" % (n, ", ".join(topp[:3]))


def mat(k, kalla, typ, kat, marke, bors, alarm, idag):
    if typ == "andel":
        n, per = k.andel(kat)
        if not n:
            raise ValueError("tomt stickprov")
        return spara_andel(bors, kalla, kat, n, per, alarm, idag)
    if typ == "bakat":
        nya = k.affarer(kat, "Sold", bara_bakat=True)
        spara_affarer(kat["id"], nya)
        return "%d sålda annonser längre bak" % len(nya)
    if typ in ("salda", "osalda"):
        nya = k.affarer(kat, "Sold" if typ == "salda" else "Unsold")
        if not nya:
            raise ValueError("inga annonser")
        spara_affarer(kat["id"], nya)
        if typ == "salda":
            satt_punkt(bors.setdefault("tradera_aktiva", {}).setdefault(kat["id"], []), [idag, k.ute(kat)])
        return "%d %s annonser" % (len(nya), "sålda" if typ == "salda" else "osålda")
    if typ == "ute":
        return mat_ute(k, kat, bors, alarm, idag)
    r = k.marke(kat, marke)
    if r is None:
        return "märket finns inte hos källan"
    punkt = [idag, r["antal"], r["median"], r["p25"], 1 if r.get("tak") else 0]
    if kalla == "vinted":
        punkt += [r.get("gillas"), r.get("dygn")]
    satt_punkt(bors["marke"].setdefault(kalla, {}).setdefault(kat["id"], {}).setdefault(marke, []), punkt)
    return "%s st, median %s kr%s" % (r["antal"], r["median"], ", sålda per dygn %s" % r.get("dygn") if kalla == "vinted" else "")


def mat_ute(k, kat, bors, alarm, idag):
    """Fortsätter genomgången av Traderas aktiva annonser. När hela kategorin är klar räknas annonserna per märke
    (samma märke som för de sålda: det säljaren valt, annars det som står i titeln) och sparas för dagen:
    [dag, aktiva i kategorin, annonser som gåtts igenom, {märke: antal}]."""
    alla = vb.las_json(AFFAR_FIL, {})
    till = alla.setdefault("_ute", {}).setdefault(kat["id"], {})
    bors.setdefault("tradera_svep", {})[kat["id"]] = 1
    klar = k.svep(kat, till)
    if not klar:
        spara_kompakt(AFFAR_FIL, alla)
        return "aktiva annonser: sökning %d av %d, %d annonser hittills" % (min(till["i"] + 1, len(till["delar"])), len(till["delar"]), len(till["ids"]))
    extra, minne, per = kanda_marken(bors, alarm), {}, Counter()
    for slut, attr, titel in till["ids"].values():
        if slut and slut < idag:
            continue
        m = marke_for([slut, "", 0, None, 0, 0, attr, titel], extra, minne)
        if not M.ar_dam(m):
            per[m] += 1
    sett = sum(per.values())
    satt_punkt(alla.setdefault("_ute_hist", {}).setdefault(kat["id"], []), [idag, till["tot"], sett, dict(per)])
    del alla["_ute"][kat["id"]]
    bors["tradera_svep"].pop(kat["id"], None)
    spara_kompakt(AFFAR_FIL, alla)
    return "aktiva annonser klara: %d i kategorin, %d genomgångna, %d märken" % (till["tot"], sett, len(per))


# ---------- Sammanställning till hemsidan ----------

def marke_for(post, extra, minne):
    """Märket för en Tradera-annons: det säljaren valt, annars det som står i titeln."""
    attr, titel = post[6], post[7]
    nyckel = (attr, titel)
    if nyckel not in minne:
        m = M.kanon(attr) if attr else None
        if not m or m == M.UTAN:
            m = M.i_titel(titel, extra) or m or M.UTAN
        minne[nyckel] = m
    return minne[nyckel]


def mandag(dag):
    d = time.strptime(dag, "%Y-%m-%d")
    return dagstr(calendar.timegm(d) - d.tm_wday * 86400)


def stat(poster):
    """Antal, median, nedre och övre kvartil, dagar till försäljning, antal säljare och största säljarens andel."""
    if not poster:
        return None
    priser = [p[2] for p in poster if p[2]]
    dagar = [max(0, (tid(p[0]) - tid(p[1])) // 86400) for p in poster if p[1]]
    saljare = Counter(p[3] for p in poster)
    return {"n": len(poster), "p": median(priser), "l": kvantil(priser, 0.25), "h": kvantil(priser, 0.75),
            "d": round(statistics.median(dagar)) if dagar else None, "sa": len(saljare),
            "ts": round(100 * saljare.most_common(1)[0][1] / len(poster))}


def tackning(bors, kat_id, status):
    """Från vilket datum Tradera-affärerna i kategorin är kompletta (None om inte mätt än)."""
    nyckel = "%s|%s" % (kat_id, status)
    t = (bors.get("tradera_forsta") or {}).get(nyckel)
    if t is None:
        return None
    bak = [v for k, v in (bors.get("tradera_bakat") or {}).items() if k.startswith(nyckel + "|")]
    if status == "Sold" and bak and not any(bak):
        return dagstr(t - (TRADERA_BAKAT - TRADERA_LANGST) * 86400)
    return dagstr(t - (FONSTER - 2) * 86400)


def sammanstall(bors, alarm):
    """bors["marknad"]: för varje kategori och märke vad som sålts på Tradera de senaste 30 dagarna (antal,
    pris, hur snabbt, chans att sälja) jämfört med 30 dagar innan, och vad det kostar att köpa på Vinted.
    bors["veckor"]: sålda och medianpris per vecka, för diagrammen."""
    alla = vb.las_json(AFFAR_FIL, {})
    extra = kanda_marken(bors, alarm)
    minne = {}
    nu = time.time()
    idag = dagstr(nu)
    f0, f1 = dagstr(nu - FONSTER * 86400), dagstr(nu - 2 * FONSTER * 86400)
    ut, veckor_ut = {}, {}
    for kat in KATEGORIER:
        poster = alla.get(kat["id"]) or {}
        fran_s, fran_o = tackning(bors, kat["id"], "Sold"), tackning(bors, kat["id"], "Unsold")
        if not poster or not fran_s:
            continue
        per = {}
        for p in poster.values():
            if not p[0] or p[0] > idag:
                continue
            m = marke_for(p, extra, minne)
            if M.ar_dam(m):
                continue
            fonster = "nu" if p[0] > f0 else "fore" if p[0] > f1 else None
            d = per.setdefault(m, {"nu": [], "fore": [], "osalda": [], "alla": []})
            if p[5]:
                d["alla"].append(p)
                if fonster:
                    d[fonster].append(p)
            elif fonster == "nu":
                d["osalda"].append(p)
        jamfor = fran_s <= f1
        vin_pts = (bors["andel"].get("vinted") or {}).get(kat["id"]) or []
        vin = vin_pts[-1] if vin_pts else None
        vin_m = (bors["marke"].get("vinted") or {}).get(kat["id"]) or {}
        rader = []
        for m, d in per.items():
            if m == M.UTAN:
                continue
            s = stat(d["nu"])
            nf = len(d["fore"]) if jamfor else None
            if (s["n"] if s else 0) + (nf or 0) < 3 and m not in alarm:
                continue
            r = {"m": m, "s": s["n"] if s else 0}
            if s:
                r.update({k: s[k] for k in ("p", "l", "h", "d", "sa", "ts")})
            if jamfor:
                r["sf"] = nf
                r["pf"] = median([p[2] for p in d["fore"]])
            if fran_o:
                r["o"] = len(d["osalda"])
            v = {}
            if vin and m in vin[2]:
                x = vin[2][m]
                v.update({"n": x[0], "a": round(100 * x[0] / vin[1], 2), "p": x[1]})
                if len(x) > 2 and x[0] >= 5:
                    v["l"] = x[2]
            mp = (vin_m.get(m) or [None])[-1]
            if mp and mp[1]:
                v.update({"t": mp[1], "tak": mp[4], "p": mp[2] or v.get("p"), "l": mp[3] or v.get("l")})
                if len(mp) > 6 and mp[6] is not None:
                    v["dy"] = mp[6]
            if v:
                r["v"] = v
            rader.append(r)
        rader.sort(key=lambda r: (-r["s"], -(r.get("sf") or 0)))
        alla_nu = [p for d in per.values() for p in d["nu"]]
        s_alla = stat(alla_nu)
        aktiva = (bors.get("tradera_aktiva") or {}).get(kat["id"]) or []
        ut[kat["id"]] = {
            "s": len(alla_nu), "u": len(per.get(M.UTAN, {"nu": []})["nu"]),
            "p": s_alla["p"] if s_alla else None, "d": s_alla["d"] if s_alla else None,
            "sf": sum(len(d["fore"]) for d in per.values()) if jamfor else None,
            "o": sum(len(d["osalda"]) for d in per.values()) if fran_o else None,
            "ute": aktiva[-1][1] if aktiva else None, "fran": fran_s, "fran_o": fran_o,
            "vn": vin[1] if vin else None, "vd": vin[0] if vin else None,
            "marken": rader[:200],
        }
        # Veckor: sålda och medianpris per vecka för de största märkena, för diagrammen. Bara hela veckor
        # som börsen har mätt, och den som pågår.
        start = mandag(max(fran_s, dagstr(nu - 26 * 7 * 86400)))
        if start < fran_s:
            start = dagstr(tid(start) + 7 * 86400)
        v_lista, t = [], tid(start)
        while dagstr(t) <= idag:
            v_lista.append(dagstr(t))
            t += 7 * 86400
        if v_lista:
            index = {v: i for i, v in enumerate(v_lista)}
            # Priset är medianen för fyra veckor bakåt, så att ett märke som säljer ett par i veckan inte hoppar
            # upp och ner på enstaka plagg.
            serie = {}
            for m in dict.fromkeys([r["m"] for r in rader[:40]] + [m for m in alarm if m in per] + ["*"]):
                priser = [[] for _ in v_lista]
                for p in (per[m]["alla"] if m != "*" else [p for d in per.values() for p in d["alla"]]):
                    i = index.get(mandag(p[0]))
                    if i is not None:
                        priser[i].append(p[2])
                serie[m] = [[len(x), median([q for y in priser[max(0, i - 3):i + 1] for q in y])] for i, x in enumerate(priser)]
            veckor_ut[kat["id"]] = {"v": v_lista, "m": serie}
    bors["marknad"] = {"uppdaterad": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "fonster": FONSTER,
                       "kategorier": ut}
    bors["veckor"] = veckor_ut


def gles(punkter):
    """Som satt_punkt: en punkt per dag de senaste DAGLIGT_DAGAR dagarna, äldre en per vecka."""
    grans, dagligt = dagstr(time.time() - SPARA_DAGAR * 86400), dagstr(time.time() - DAGLIGT_DAGAR * 86400)
    ut, veckor = [], set()
    for p in punkter:
        if p[0] < grans:
            continue
        if p[0] < dagligt:
            vecka = time.strftime("%G-%V", time.strptime(p[0], "%Y-%m-%d"))
            if vecka in veckor:
                continue
            veckor.add(vecka)
        ut.append(p)
    return ut


def gamla_vyer(bors, alarm):
    """Börsens diagram och tabeller, räknade på alla sålda Tradera-annonser i kategorin (inte stickprov):
    tradera_veckor[kat]: [måndag, sålda, {märke: [sålda, medianpris fyra veckor bakåt]}, övriga] per vecka.
    marke.tradera[kat][märke]: [dag, sålda 30 dagar, medianpris, billigaste fjärdedelen, 0, sålda 7 dagar,
    annonser ute] per dag. andel.tradera[kat]: de senaste 30 dagarna i en punkt. tradera_ute[kat]: [dag, aktiva, 0].
    Det som räknats tidigare än affärerna sparas (AFFAR_DAGAR) behålls, så historiken växer."""
    alla = vb.las_json(AFFAR_FIL, {})
    hist = alla.get("_ute_hist") or {}
    extra, minne = kanda_marken(bors, alarm), {}
    idag = dagstr(time.time())
    veckor = bors.setdefault("tradera_veckor", {})
    mt = bors["marke"].setdefault("tradera", {})
    bors["tradera_ute"] = {k: [[p[0], p[1], 0] for p in v] for k, v in (bors.get("tradera_aktiva") or {}).items()}
    for kat in KATEGORIER:
        fran = tackning(bors, kat["id"], "Sold")
        poster = alla.get(kat["id"]) or {}
        if not fran or not poster:
            continue
        salda = {}  # märke -> [(slutdag, pris)], äldst först
        for p in poster.values():
            if p[5] and p[0] and fran <= p[0] <= idag:
                m = marke_for(p, extra, minne)
                if not M.ar_dam(m):
                    salda.setdefault(m, []).append((p[0], p[2]))
        if not salda:
            continue
        for v in salda.values():
            v.sort()
        uh = hist.get(kat["id"]) or []
        ute = {p[0]: p for p in uh}
        ute_nu = Counter(uh[-1][3]) if uh else Counter()
        # Märkena med egna diagram: de som sålt mest, de som har flest annonser ute och alla alarm-märken.
        topp = [m for m in sorted(salda, key=lambda m: -len(salda[m])) if m != M.UTAN and len(salda[m]) >= 3][:GAMLA_TOPP]
        topp += [m for m, n in ute_nu.most_common(UTE_TOPP + 1) if m != M.UTAN and n >= 3]
        topp = list(dict.fromkeys(topp + [m for m in alarm if m in salda or m in ute_nu]))

        # Veckor: hela veckor från den första som är komplett (och inte rensats bort), och den som pågår.
        def forsta_mandag(d):
            m = mandag(d)
            return m if m >= d else dagstr(tid(m) + 7 * 86400)
        bas = max(fran, dagstr(time.time() - (AFFAR_DAGAR - 1) * 86400))
        v_lista, t = [], tid(forsta_mandag(bas))
        while dagstr(t) <= idag:
            v_lista.append(dagstr(t))
            t += 7 * 86400
        if v_lista:
            index = {v: i for i, v in enumerate(v_lista)}
            per_v = {m: [[] for _ in v_lista] for m in topp}
            totalt = [0] * len(v_lista)
            for m, v in salda.items():
                for d, pris in v:
                    i = index.get(mandag(d))
                    if i is None:
                        continue
                    totalt[i] += 1
                    if m in per_v:
                        per_v[m][i].append(pris)
            nya = []
            for i, v in enumerate(v_lista):
                # Priset är medianen för fyra veckor bakåt, så att ett märke som säljer ett par i veckan inte hoppar.
                marken = {m: [len(per_v[m][i]), median([q for x in per_v[m][max(0, i - 3):i + 1] for q in x])] for m in topp}
                nya.append([v, totalt[i], marken, totalt[i] - sum(x[0] for x in marken.values())])
            veckor[kat["id"]] = gles([p for p in veckor.get(kat["id"]) or [] if forsta_mandag(fran) <= p[0] < v_lista[0]] + nya)

        # Märkena dag för dag: de senaste 30 dagarna fram till dagen, från den första dag där hela fönstret är
        # komplett. Äldre dagar (räknade innan affärerna rensades) behålls som de var.
        forsta = dagstr(tid(fran) + (FONSTER - 1) * 86400)
        dagar, t = [], tid(dagstr(tid(bas) + (FONSTER - 1) * 86400))
        while dagstr(t) <= idag:
            dagar.append(dagstr(t))
            t += 86400
        if not dagar:
            # Inte 30 dagar komplett än: bara i dag, med det som finns.
            dagar = [idag]
        gamla = mt.get(kat["id"]) or {}
        nya_m = {}
        for m in topp:
            v = salda.get(m) or []
            slut = [d for d, _ in v]
            pts = []
            for d in dagar:
                a = bisect.bisect_left(slut, dagstr(tid(d) - (FONSTER - 1) * 86400))
                b = bisect.bisect_right(slut, d)
                vecka = b - bisect.bisect_left(slut, dagstr(tid(d) - 6 * 86400))
                priser = [p for _, p in v[a:b]]
                u = ute.get(d)
                n_ute = round(u[3].get(m, 0) * u[1] / u[2]) if u and u[2] else None
                pts.append([d, b - a, median(priser), kvantil(priser, 0.25), 0, vecka, n_ute])
            nya_m[m] = gles([p for p in gamla.get(m) or [] if forsta <= p[0] < dagar[0]] + pts)
        mt[kat["id"]] = nya_m

        # De senaste 30 dagarna i en punkt, med alla märken som sålt minst två (för nya märken att bevaka).
        f0 = dagstr(time.time() - (FONSTER - 1) * 86400)
        nu = {m: [p for d, p in v if d >= f0] for m, v in salda.items()}
        n = sum(len(v) for v in nu.values())
        marken = {m: [len(v), median(v), kvantil(v, 0.25)] for m, v in nu.items() if m != M.UTAN and len(v) >= 2}
        bors["andel"].setdefault("tradera", {})[kat["id"]] = [[idag, n, marken, n - sum(x[0] for x in marken.values())]]


def sammanfatta(bors):
    """Skriver de mest sålda märkena per kategori i loggen, så börsen går att läsa utan hemsidan."""
    for kat_id, k in (bors.get("marknad") or {}).get("kategorier", {}).items():
        logg("%s: %s sålda på Tradera senaste %d dagarna (median %s kr, %s utan märke, komplett från %s). Mest sålda: %s" % (
            kat_id, k["s"], FONSTER, k["p"], k["u"], k["fran"],
            ", ".join("%s %d st/%s kr" % (r["m"], r["s"], r.get("p")) for r in k["marken"][:12])))


def vinted_kostnad(bors, kat, typ, marke):
    """Hur många frågor en Vinted-mätning gör: tio sidor för ett kategoristickprov, för ett märke så många som
    behövs för alla dess annonser enligt förra mätningen, plus kollen av försvunna annonser."""
    if typ == "andel":
        return VINTED_SIDOR
    pts = bors["marke"].get("vinted", {}).get(kat["id"], {}).get(marke) or []
    antal = pts[-1][1] if pts else 96
    slaupp = 0 if marke in bors.get("vinted_marke_ids", {}) else 3
    return max(1, min(VINTED_SIDOR, -(-(antal or 0) // 96))) + VINTED_KOLLA + slaupp


def kor(tidsgrans=TIDSGRANS_SEK, max_antal=None, bara=None):
    global KATEGORIER
    start = time.time()
    KATEGORIER = BAS_KATEGORIER + egna_kategorier()
    sokningar = vb.las_json(vb.SOKNINGAR_FIL, [])
    alarm = alarm_marken(sokningar)
    bors = las_bors()
    kallor = {}
    lista_ = uppgifter(bors, alarm)
    if bara:
        lista_ = [u for u in lista_ if u[2] == bara]
    idag = dagstr(time.time())
    gjorda, fel, vinted_fragor = 0, {}, 0
    for senast, nyckel, kalla, kat, typ, marke in lista_:
        if time.time() - start > tidsgrans or (max_antal and gjorda >= max_antal):
            break
        if fel.get(kalla, 0) >= 2:  # källan krånglar just nu, försök igen nästa runda
            continue
        kostar = vinted_kostnad(bors, kat, typ, marke) if kalla == "vinted" else 0
        if kalla == "vinted" and vinted_fragor + kostar > VINTED_PER_RUNDA:
            continue
        if kalla not in kallor:
            kallor[kalla] = {"vinted": lambda: VintedKalla(bors),
                             "tradera": lambda: TraderaKalla(bors, start + tidsgrans),
                             "plick": lambda: PlickKalla(kanda_marken(bors, alarm))}[kalla]()
        try:
            if kalla == "vinted":
                vinted_fragor += kostar
            svar = mat(kallor[kalla], kalla, typ, kat, marke, bors, alarm, idag)
            bors["senast"][nyckel] = time.time()
            if typ in ("salda", "osalda"):
                bors.setdefault("tradera_forsta", {}).setdefault(
                    "%s|%s" % (kat["id"], "Sold" if typ == "salda" else "Unsold"), round(time.time()))
            gjorda += 1
            logg("%s: %s" % (nyckel, svar))
        except Exception as e:
            fel[kalla] = fel.get(kalla, 0) + 1
            logg("%s: fel, %s" % (nyckel, e))
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403, 429) and kalla == "vinted":
                fel[kalla] = 99
        time.sleep(random.uniform(0.5, 1.5))
    # Släng mätningar av märken som inte längre finns i något alarm.
    for kalla in ("vinted", "plick"):
        for kat in bors["marke"].get(kalla, {}).values():
            for m in list(kat):
                if m not in alarm:
                    del kat[m]
    for kat in bors.get("vinted_sett", {}).values():
        for m in list(kat):
            if m not in alarm:
                del kat[m]
    bors["senast"] = {k: v for k, v in bors["senast"].items() if not k.startswith("marke|") or k.split("|", 3)[3] in alarm}
    try:
        sammanstall(bors, alarm)
        sammanfatta(bors)
    except Exception as e:
        logg("kunde inte sammanställa marknaden: %r" % e)
    try:
        gamla_vyer(bors, alarm)
    except Exception as e:
        logg("kunde inte räkna börsens diagram: %r" % e)
    # tr: Traderas kategorier, så att hemsidan kan länka till det som sålts
    bors["kategorier"] = [{"id": k["id"], "namn": k["namn"],
                           "tr": k.get("tradera_id") or (bors.get("tradera_kategorier") or {}).get(k["id"]) or [],
                           **({"egen": True, "ord": k["ord"]} if k.get("egen") else {})} for k in KATEGORIER]
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
