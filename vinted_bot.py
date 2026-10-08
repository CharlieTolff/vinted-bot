#!/usr/bin/env python3
"""
Vinted-bevakare för Valto Resell.

Söker på Vinted med dina sparade sökningar (sokningar.json) med några minuters
mellanrum och skickar nya annonser som notis i Telegram, med bild, pris och länk.

Kör:
    python3 vinted_bot.py               # bevaka för alltid
    python3 vinted_bot.py --en-gang     # en enda runda (för schemalagd hosting)
    python3 vinted_bot.py --test        # skicka de 3 senaste träffarna, för att testa notiserna
    python3 vinted_bot.py --hitta-chat-id   # visar ditt Telegram chat-id

Bara Pythons standardbibliotek används, så inget behöver installeras.
"""

import argparse
import html
import http.cookiejar
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

MAPP = os.path.dirname(os.path.abspath(__file__))
SOKNINGAR_FIL = os.path.join(MAPP, "sokningar.json")
INSTALLNINGAR_FIL = os.path.join(MAPP, "installningar.json")
SEDDA_FIL = os.path.join(MAPP, "sedda.json")
TRAFFAR_FIL = os.path.join(MAPP, "traffar.json")  # det hemsidan visar
MINNE_FIL = os.path.join(MAPP, "minne.json")  # priser, säljare och märken som boten minns

VINTED = "https://www.vinted.se"
WEBBLASARE = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
SKICK = ["Ny med prislapp", "Ny utan prislapp", "Mycket bra", "Bra", "Tillfredsställande"]
MAX_SEDDA_PER_SOKNING = 3000
MAX_TRAFFAR_PER_SOKNING = 200
KAP_ANDEL = 0.5  # utan kap-pris: kap om priset är högst hälften av det vanliga priset

# Vinteds egna nummer för skick, kategorier och länder (samma på alla Vinted-sidor).
SKICK_ID = {"Ny med prislapp": 6, "Ny utan prislapp": 1, "Mycket bra": 2, "Bra": 3, "Tillfredsställande": 4}
KATEGORI_ID = {
    "herr": {"": 5, "klader": 2050, "skor": 1231, "accessoarer": 82},
    "dam": {"": 1904, "klader": 4, "skor": 16, "vaskor": 19, "accessoarer": 1187},
}
# Länderna som säljer på svenska Vinted, alltså de du kan köpa från.
LANDER = {"SE": "🇸🇪 Sverige", "DK": "🇩🇰 Danmark", "FI": "🇫🇮 Finland", "PL": "🇵🇱 Polen"}
FLAGGA = {"SE": "🇸🇪", "DK": "🇩🇰", "FI": "🇫🇮", "PL": "🇵🇱"}

PRIS_DAGAR = 30           # vanligt pris räknas på priser från de senaste 30 dagarna
MIN_PRISER = 8            # så många priser behövs innan vi säger vad det vanliga priset är
SALJARE_DAGAR = 7         # så länge vi litar på en säljares omdömen innan vi kollar igen
MAX_SALJARKOLLAR = 20     # säljare vi högst slår upp per alarm och runda
STANDARD_BETYG = 4.5      # säljare med lägre snittbetyg hoppas över (0 = av)
STANDARD_FRAKT = 60       # vad frakten brukar kosta när du köper (kr)
MARKNAD_TIMMAR = 6        # så ofta vi kollar om vad liknande saker säljs för
MARKNAD_MIN = 8           # så många liknande annonser behövs för att uppskatta ett säljpris
MARKNAD_ANDEL = 0.4       # säljpris = 40 % av liknande annonser är billigare (dyra annonser blir ofta inte sålda)
# Skicket påverkar vad du kan sälja för, jämfört med en vanlig "Mycket bra"-annons.
SKICK_FAKTOR = {"Ny med prislapp": 1.2, "Ny utan prislapp": 1.1, "Mycket bra": 1.0, "Bra": 0.85, "Tillfredsställande": 0.65}


def logg(text):
    print(time.strftime("%H:%M:%S"), text, flush=True)


# ---------- Filer ----------

def las_json(fil, standard):
    if not os.path.exists(fil):
        return standard
    with open(fil, encoding="utf-8") as f:
        return json.load(f)


def spara_json(fil, data):
    tmp = fil + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, fil)


def installningar():
    inst = las_json(INSTALLNINGAR_FIL, {})
    # Miljövariabler går före filen (smidigt när boten körs på en server).
    inst["telegram_token"] = os.environ.get("TELEGRAM_TOKEN") or inst.get("telegram_token", "")
    inst["telegram_chat_id"] = os.environ.get("TELEGRAM_CHAT_ID") or inst.get("telegram_chat_id", "")
    inst.setdefault("intervall_sekunder", 180)
    return inst


# ---------- Vinted ----------

class Vinted:
    def __init__(self):
        self.kakor = http.cookiejar.CookieJar()
        self.oppnare = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.kakor))
        self.har_kakor = False

    def hamta(self, url):
        req = urllib.request.Request(url, headers={
            "User-Agent": WEBBLASARE,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "sv-SE,sv;q=0.9",
        })
        with self.oppnare.open(req, timeout=30) as svar:
            return svar.read().decode("utf-8", errors="replace")

    def api(self, vag):
        if not self.har_kakor:
            self.hamta(VINTED + "/")
            self.har_kakor = True
        req = urllib.request.Request(VINTED + vag, headers={"User-Agent": WEBBLASARE, "Accept": "application/json"})
        with self.oppnare.open(req, timeout=30) as svar:
            return json.load(svar)

    def marke_id(self, namn):
        """Vinteds nummer för ett märke, t.ex. "Nudie" -> 95256 (Nudie Jeans)."""
        marken = self.api("/api/v2/brands?" + urllib.parse.urlencode({"keyword": namn})).get("brands") or []
        namn = namn.lower().strip()
        for m in marken:
            if m.get("title", "").lower() == namn:
                return m["id"]
        for m in marken:  # annars det största märket som innehåller ordet
            if namn in m.get("title", "").lower():
                return m["id"]
        return None

    def saljare(self, uid):
        u = self.api("/api/v2/users/%s" % uid).get("user") or {}
        return {
            "land": u.get("country_code") or "",
            "betyg": round(float(u.get("feedback_reputation") or 0) * 5, 1),
            "omdomen": int(u.get("feedback_count") or 0),
            "kollad": time.time(),
        }

    def sok(self, url):
        if not self.har_kakor:
            self.hamta(VINTED + "/")  # ger oss kakorna Vinted kräver
            self.har_kakor = True
        try:
            sida = self.hamta(url)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                self.kakor.clear()  # hämta nya kakor nästa gång
                self.har_kakor = False
            raise
        return annonser_fran_sida(sida)


def lista(varde):
    """Alarmfält kan vara en text eller en lista (t.ex. flera sökord eller märken)."""
    if not varde:
        return []
    if isinstance(varde, str):
        return [varde.strip()] if varde.strip() else []
    return [str(v).strip() for v in varde if str(v).strip()]


def alarm_namn(s):
    return s.get("namn") or ", ".join(lista(s.get("sokord"))) or "sökning"


def sok_url(s, marke_ids=(), sokord=None):
    if s.get("url"):
        # En sök-länk kopierad direkt från Vinted. Vi ser till att nyaste visas först.
        delar = urllib.parse.urlsplit(s["url"])
        par = [(k, v) for k, v in urllib.parse.parse_qsl(delar.query) if k != "order"]
        par.append(("order", "newest_first"))
        return VINTED + delar.path + "?" + urllib.parse.urlencode(par)
    if sokord is None:
        sokord = (lista(s.get("sokord")) or [""])[0]
    par = [("search_text", sokord), ("order", "newest_first"), ("currency", "SEK")]
    if s.get("maxpris"):
        par.append(("price_to", s["maxpris"]))
    if s.get("minpris"):
        par.append(("price_from", s["minpris"]))
    # Vinteds egna filter, så att sökningen bara ger rätt sorts saker från början.
    for k in kategori_ids(s):
        par.append(("catalog_ids[]", k))
    for marke_id in marke_ids:
        par.append(("brand_ids[]", marke_id))
    for skick in s.get("skick") or []:
        if skick in SKICK_ID:
            par.append(("status_ids[]", SKICK_ID[skick]))
    return VINTED + "/catalog?" + urllib.parse.urlencode(par)


def kategori_ids(s):
    kon = KATEGORI_ID.get(s.get("kon") or "")
    if not kon:
        return []
    valda = [kon[k] for k in s.get("kategorier") or [] if k in kon and k]
    return valda or [kon[""]]


def annonser_fran_sida(sida):
    """Plockar ut annonserna ur sökresultatets HTML (Vinted bäddar in dem som JSON)."""
    bitar = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', sida)
    text = "".join(json.loads(b) for b in bitar)
    avkodare = json.JSONDecoder()
    annonser = {}
    for m in re.finditer(r'"productItem":', text):
        try:
            a, _ = avkodare.raw_decode(text, m.end())
        except ValueError:
            continue
        if isinstance(a, dict) and "id" in a and "price" in a:
            annonser[a["id"]] = forenkla(a)
    return list(annonser.values())


def forenkla(a):
    box = a.get("itemBox") or {}
    andra = [d.strip() for d in (box.get("secondLine") or "").split("·")]
    skick = andra[-1] if andra and andra[-1] in SKICK else ""
    storlek = " · ".join(d for d in andra if d and d != skick)
    bild = ""
    if a.get("photos"):
        bild = a["photos"][0].get("url", "")
    bild = bild or a.get("thumbnailUrl") or ""
    total = (a.get("totalItemPrice") or {}).get("amount")
    return {
        "saljare_id": (a.get("user") or {}).get("id"),
        "gillas": a.get("favouriteCount") or 0,
        "id": a["id"],
        "titel": a.get("title", ""),
        "marke": box.get("firstLine") or "",
        "storlek": storlek,
        "skick": skick,
        "pris": float(a["price"]["amount"]),
        "pris_totalt": float(total) if total else None,
        "bild": bild,
        "lank": VINTED + a.get("url", "/items/%s" % a["id"]),
    }


def storlek_delar(text):
    """'46 | W30' -> {'46', 'w30'}, 'W30/L32' -> {'w30', 'l32'}, 'EU 36' -> {'eu 36', 'eu', '36'}."""
    delar = {d.strip().lower() for d in re.split(r"[|·/,]", text) if d.strip()}
    return delar | {o for d in delar for o in d.split()}


def matchar(annons, s):
    """Filtren som Vinted-sökningen själv inte klarar av."""
    if s.get("maxpris") and annons["pris"] > float(s["maxpris"]):
        return False
    if s.get("minpris") and annons["pris"] < float(s["minpris"]):
        return False
    marken = lista(s.get("marke"))
    if marken and not any(m.lower() in annons["marke"].lower() for m in marken):
        return False
    if s.get("storlekar"):
        # Exakt storlek, så att "S" inte råkar matcha "XS" och "L" inte "XL".
        if not any(storlek_delar(v) <= storlek_delar(annons["storlek"]) for v in s["storlekar"]):
            return False
    if s.get("skick") and annons["skick"] not in s["skick"]:
        return False
    titel = annons["titel"].lower()
    if any(ord_.lower() in titel for ord_ in s.get("uteslut", [])):
        return False
    # "Måste stå i titeln": minst en av fraserna, med alla dess ord (t.ex. "regular alf").
    maste = lista(s.get("maste"))
    if maste and not any(all(o in titel for o in fras.lower().split()) for fras in maste):
        return False
    return True


# ---------- Telegram ----------

def telegram(inst, metod, data):
    url = "https://api.telegram.org/bot%s/%s" % (inst["telegram_token"], metod)
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as svar:
        return json.load(svar)


def skicka_notis(inst, annons, sokning_namn):
    rader = [
        "<b>%s</b>" % html.escape(annons["titel"]),
        "💰 <b>%.0f kr</b>" % annons["pris"]
        + (" (%.0f kr med avgift)" % annons["pris_totalt"] if annons["pris_totalt"] else ""),
    ]
    if annons.get("kap"):
        rader.insert(0, "🔥 <b>KAP!</b>")
    if annons.get("vinst") is not None:
        rader.append("📈 Vinst ca <b>%+.0f kr</b> (liknande säljs för ca %.0f kr)" % (annons["vinst"], annons["saljpris"]))
    info = " · ".join(x for x in [annons["marke"], annons["storlek"], annons["skick"]] if x)
    if info:
        rader.append(html.escape(info))
    saljare = annons.get("saljare")
    if saljare:
        om = "⭐ %.1f (%d omdömen)" % (saljare["betyg"], saljare["omdomen"]) if saljare["omdomen"] else "Inga omdömen än"
        rader.append(" ".join(x for x in [FLAGGA.get(saljare["land"], ""), om] if x))
    rader.append('🔗 <a href="%s">Öppna på Vinted</a>' % annons["lank"])
    rader.append("<i>Sökning: %s</i>" % html.escape(sokning_namn))
    text = "\n".join(rader)

    if not inst["telegram_token"] or not inst["telegram_chat_id"]:
        logg("NY: %s | %.0f kr | %s" % (annons["titel"], annons["pris"], annons["lank"]))
        return
    try:
        if annons["bild"]:
            telegram(inst, "sendPhoto", {"chat_id": inst["telegram_chat_id"], "photo": annons["bild"],
                                         "caption": text, "parse_mode": "HTML"})
            return
    except urllib.error.HTTPError as e:
        logg("Bilden gick inte att skicka (%s), skickar bara text." % e.code)
    telegram(inst, "sendMessage", {"chat_id": inst["telegram_chat_id"], "text": text, "parse_mode": "HTML"})


def hitta_chat_id(inst):
    if not inst["telegram_token"]:
        sys.exit("Lägg först in telegram_token i installningar.json.")
    svar = telegram(inst, "getUpdates", {})
    hittade = {}
    for u in svar.get("result", []):
        chat = (u.get("message") or {}).get("chat")
        if chat:
            hittade[chat["id"]] = chat.get("first_name") or chat.get("title") or ""
    if not hittade:
        print("Hittade inget. Skicka ett meddelande (t.ex. 'hej') till din bot i Telegram och kör igen.")
    for cid, namn in hittade.items():
        print("Chat-id: %s  (%s)" % (cid, namn))


# ---------- Huvudloop ----------

def median(tal):
    tal = sorted(tal)
    if not tal:
        return None
    mitt = len(tal) // 2
    return tal[mitt] if len(tal) % 2 else (tal[mitt - 1] + tal[mitt]) / 2


def ar_kap(annons, s, vanligt_pris):
    """Kap = under alarmets kap-pris, eller (utan kap-pris) högst hälften av det vanliga priset."""
    if s.get("kappris"):
        return annons["pris"] <= float(s["kappris"])
    return bool(vanligt_pris) and annons["pris"] <= vanligt_pris * KAP_ANDEL


def percentil(tal, andel):
    tal = sorted(tal)
    return tal[min(len(tal) - 1, int(len(tal) * andel))] if tal else None


def marknad_urls(s, marke_ids):
    """Samma sökning som alarmet men utan prisgränser, sorterad som Vinted själv tycker är relevant."""
    utan_pris = {k: v for k, v in s.items() if k not in ("maxpris", "minpris")}
    urls = []
    for ord_ in lista(s.get("sokord")) or [""]:
        delar = urllib.parse.urlsplit(sok_url(utan_pris, marke_ids, ord_))
        par = [(k, v) for k, v in urllib.parse.parse_qsl(delar.query)
               if k not in ("order", "price_to", "price_from")]
        urls.append(VINTED + delar.path + "?" + urllib.parse.urlencode(par))
    return urls


def kolla_marknad(vinted, s, marke_ids, minne, namn):
    """Vad liknande saker brukar säljas för och hur eftertraktade de är (sparas några timmar)."""
    urls = marknad_urls(s, marke_ids)
    gammal = minne["marknad"].get(namn)
    if gammal and gammal["url"] == "\n".join(urls) and time.time() - gammal["tid"] < MARKNAD_TIMMAR * 3600:
        return gammal
    utan_pris = {k: v for k, v in s.items() if k not in ("maxpris", "minpris")}
    hittade = {}
    for u in urls:
        try:
            for a in vinted.sok(u):
                if matchar(a, utan_pris):
                    hittade.setdefault(a["id"], a)
        except Exception as e:
            logg("Kunde inte kolla marknadspriset för '%s': %s" % (namn, e))
            return gammal
        time.sleep(random.uniform(1, 3))
    annonser = list(hittade.values())
    # Räkna om till "Mycket bra"-skick så att olika skick blir jämförbara.
    priser = [a["pris"] / SKICK_FAKTOR.get(a["skick"], 1.0) for a in annonser]
    gillas = sorted(a["gillas"] for a in annonser)
    marknad = {
        "url": "\n".join(urls),
        "tid": time.time(),
        "antal": len(annonser),
        "pris": round(percentil(priser, MARKNAD_ANDEL)) if len(priser) >= MARKNAD_MIN else None,
        "gillas": median(gillas) if gillas else 0,
    }
    minne["marknad"][namn] = marknad
    return marknad


def efterfragan(gillas):
    """Hur många som brukar gilla liknande annonser säger hur eftertraktat det är."""
    if gillas >= 15:
        return "hög"
    if gillas >= 5:
        return "medel"
    return "låg"


def uppskattat_saljpris(annons, marknad):
    if not marknad or not marknad.get("pris"):
        return None
    pris = marknad["pris"] * SKICK_FAKTOR.get(annons["skick"], 1.0)
    return round(pris / 10) * 10


def vinst(annons, saljpris, s):
    """Ungefärlig vinst om du köper (pris + avgift + frakt) och säljer för det uppskattade priset."""
    if not saljpris:
        return None
    frakt = s.get("frakt", STANDARD_FRAKT) or 0
    kostnad = (annons["pris_totalt"] or annons["pris"]) + float(frakt)
    return saljpris - kostnad


def vanligt_pris(prislista, nu):
    """Medianpriset för alarmets träffar de senaste 30 dagarna (minst 8 olika annonser)."""
    grans = nu - PRIS_DAGAR * 86400
    priser = [p for p, t in prislista.values() if t >= grans]
    return median(priser) if len(priser) >= MIN_PRISER else None


def minns_priser(prislista, traffar, nu):
    for a in traffar:
        prislista.setdefault(str(a["id"]), [a["pris"], nu])
    grans = nu - PRIS_DAGAR * 86400
    for k in [k for k, (_, t) in prislista.items() if t < grans]:
        del prislista[k]


def saljare_ok(info, s):
    """Godkänd säljare: rätt land och inte dåliga omdömen. Säljare utan omdömen är okej."""
    lander = s.get("lander") or []
    if lander and info["land"] not in lander:
        return False
    lagst = s.get("min_betyg", STANDARD_BETYG)
    if lagst and info["omdomen"] > 0 and info["betyg"] < float(lagst):
        return False
    return True


def kolla_saljare(vinted, annonser, s, saljarminne):
    """Slår upp säljarna (land och omdömen). Ger tillbaka (godkända, ej_kollade)."""
    godkanda, ej_kollade, uppslag = [], [], 0
    for a in annonser:
        uid = str(a.get("saljare_id") or "")
        info = saljarminne.get(uid)
        if not uid:
            godkanda.append(a)
            continue
        if not info or time.time() - info["kollad"] > SALJARE_DAGAR * 86400:
            if uppslag >= MAX_SALJARKOLLAR:
                ej_kollade.append(a)
                continue
            try:
                uppslag += 1
                info = vinted.saljare(uid)
                saljarminne[uid] = info
                time.sleep(random.uniform(0.6, 1.2))
            except Exception as e:
                logg("Kunde inte kolla säljare %s: %s" % (uid, e))
                ej_kollade.append(a)
                uppslag = MAX_SALJARKOLLAR  # Vinted bromsar, försök igen nästa runda
                continue
        a["saljare"] = {k: info[k] for k in ("land", "betyg", "omdomen")}
        if saljare_ok(info, s):
            godkanda.append(a)
    return godkanda, ej_kollade


def ska_till_telegram(annons, s):
    lage = s.get("telegram", "kap")  # "kap", "alla" eller "av"
    return lage == "alla" or (lage == "kap" and annons["kap"])


def hitta_marke_ids(vinted, s, minne):
    """Märkena i alarmet som Vinteds märkesnummer (sparas så vi bara frågar en gång)."""
    if s.get("url"):
        return []
    ids = []
    for marke in lista(s.get("marke")):
        nyckel = marke.lower()
        if nyckel not in minne["marken"]:
            try:
                minne["marken"][nyckel] = vinted.marke_id(marke)
            except Exception as e:
                logg("Kunde inte slå upp märket '%s': %s" % (marke, e))
                continue
        if minne["marken"][nyckel]:
            ids.append(minne["marken"][nyckel])
    return ids


def en_runda(vinted, inst, sokningar, sedda, traffar_lista, minne, test=False):
    nu = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    nu_sek = time.time()
    for s in sokningar:
        if s.get("aktiv") is False:
            continue
        namn = alarm_namn(s)
        # Ett sökord per sökning hos Vinted; träffarna slås ihop.
        marke_ids = hitta_marke_ids(vinted, s, minne)
        urls = [sok_url(s, marke_ids, ord_) for ord_ in (lista(s.get("sokord")) or [""])]
        url = "\n".join(urls)
        try:
            hittade = {}
            for i, u in enumerate(urls):
                if i:
                    time.sleep(random.uniform(1, 3))
                for a in vinted.sok(u):
                    hittade.setdefault(a["id"], a)
            annonser = list(hittade.values())
            if len(urls) > 1:  # nyaste först (högre nummer = nyare annons)
                annonser.sort(key=lambda a: a["id"], reverse=True)
        except Exception as e:  # nätverksfel, Vinted blockerar en stund, osv.
            logg("Fel vid sökning '%s': %s" % (namn, e))
            continue
        traffar = [a for a in annonser if matchar(a, s)]
        tidigare = sedda.get(namn)
        # Ändrat alarm (t.ex. annan kategori) räknas som nytt, så du inte får en massa notiser.
        andrat = minne["sokningar"].get(namn) not in (None, url)
        forsta = tidigare is None or andrat
        minne["sokningar"][namn] = url
        # Vanligt pris = medianpriset av alla träffar de senaste 30 dagarna. Visas också på hemsidan.
        if andrat:
            minne["priser"][namn] = {}
        prislista = minne["priser"].setdefault(namn, {})
        minns_priser(prislista, traffar, nu_sek)
        vanligt = vanligt_pris(prislista, nu_sek)
        okanda = [a for a in traffar if forsta or str(a["id"]) not in tidigare]
        # Kolla säljarnas land och omdömen. De vi inte hann kolla försöker vi med nästa runda.
        godkanda, ej_kollade = kolla_saljare(vinted, okanda, s, minne["saljare"])
        if forsta:  # första gången: visa nuvarande träffar på hemsidan, men ingen notis
            nya, nya_pa_sidan, ej_kollade = [], godkanda, []
            logg("'%s': första körningen, %d nuvarande träffar sparas som redan sedda." % (namn, len(traffar)))
        else:
            nya = nya_pa_sidan = godkanda
        marknad = kolla_marknad(vinted, s, marke_ids, minne, namn)
        for a in traffar:
            a["kap"] = ar_kap(a, s, vanligt)
            a["saljpris"] = uppskattat_saljpris(a, marknad)
            a["vinst"] = vinst(a, a["saljpris"], s)
            a["hittad"] = nu

        if test:
            skicka = traffar[:3]
        else:
            skicka = [a for a in nya if ska_till_telegram(a, s)]
        for a in reversed(skicka):  # äldst först, så den nyaste hamnar längst ner i Telegram
            try:
                skicka_notis(inst, a, namn)
                time.sleep(1)
            except Exception as e:
                logg("Kunde inte skicka notis: %s" % e)
        logg("'%s': %d nya träffar, %d skickade till Telegram." % (namn, len(nya), len(skicka)))

        gamla = traffar_lista.get(namn, {}).get("annonser", [])
        kanda = {str(a["id"]) for a in nya_pa_sidan}
        # Räkna om säljpris och vinst även för annonser som redan ligger på hemsidan.
        for a in gamla:
            a["saljpris"] = uppskattat_saljpris(a, marknad)
            a["vinst"] = vinst(a, a["saljpris"], s)
        traffar_lista[namn] = {
            "vanligt_pris": vanligt,
            "saljpris": (marknad or {}).get("pris"),
            "efterfragan": efterfragan(marknad["gillas"]) if marknad else None,
            "uppdaterad": nu,
            "annonser": (nya_pa_sidan + [a for a in gamla if str(a["id"]) not in kanda])[:MAX_TRAFFAR_PER_SOKNING],
        }

        vanta = {str(a["id"]) for a in ej_kollade}
        ids = [str(a["id"]) for a in annonser if str(a["id"]) not in vanta] + list(tidigare or [])
        sedda[namn] = list(dict.fromkeys(ids))[:MAX_SEDDA_PER_SOKNING]
        time.sleep(random.uniform(2, 5))  # lite paus mellan sökningar
    # Släng hemsidans listor för alarm som tagits bort.
    aktuella = {alarm_namn(s) for s in sokningar}
    for namn in list(traffar_lista):
        if namn not in aktuella:
            del traffar_lista[namn]
    for falt in ("priser", "sokningar", "marknad"):
        for namn in list(minne[falt]):
            if namn not in aktuella:
                del minne[falt][namn]
    grans = nu_sek - SALJARE_DAGAR * 86400
    minne["saljare"] = {k: v for k, v in minne["saljare"].items() if v["kollad"] >= grans}
    spara_json(SEDDA_FIL, sedda)
    spara_json(TRAFFAR_FIL, traffar_lista)
    spara_json(MINNE_FIL, minne)


def main():
    p = argparse.ArgumentParser(description="Vinted-bevakare")
    p.add_argument("--en-gang", action="store_true", help="kör bara en runda")
    p.add_argument("--test", action="store_true", help="skicka de 3 senaste träffarna per sökning")
    p.add_argument("--hitta-chat-id", action="store_true", help="visa ditt Telegram chat-id")
    arg = p.parse_args()

    inst = installningar()
    if arg.hitta_chat_id:
        return hitta_chat_id(inst)
    if not inst["telegram_token"]:
        logg("Ingen Telegram-token än, så nya träffar skrivs bara ut här.")

    vinted = Vinted()
    sedda = las_json(SEDDA_FIL, {})
    traffar_lista = las_json(TRAFFAR_FIL, {})
    minne = las_json(MINNE_FIL, {})
    for k in ("priser", "saljare", "marken", "sokningar", "marknad"):
        minne.setdefault(k, {})
    while True:
        sokningar = las_json(SOKNINGAR_FIL, [])  # läses om varje runda, så ändringar slår igenom direkt
        en_runda(vinted, inst, sokningar, sedda, traffar_lista, minne, test=arg.test)
        if arg.en_gang or arg.test:
            break
        vanta = inst["intervall_sekunder"] + random.uniform(-20, 20)
        time.sleep(max(60, vanta))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logg("Avslutad.")
