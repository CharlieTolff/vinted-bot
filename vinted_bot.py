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

VINTED = "https://www.vinted.se"
WEBBLASARE = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
SKICK = ["Ny med prislapp", "Ny utan prislapp", "Mycket bra", "Bra", "Tillfredsställande"]
MAX_SEDDA_PER_SOKNING = 3000
MAX_TRAFFAR_PER_SOKNING = 200
KAP_ANDEL = 0.5  # utan kap-pris: kap om priset är högst hälften av det vanliga priset


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

    def sok(self, sokning):
        if not self.har_kakor:
            self.hamta(VINTED + "/")  # ger oss kakorna Vinted kräver
            self.har_kakor = True
        try:
            sida = self.hamta(sok_url(sokning))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                self.kakor.clear()  # hämta nya kakor nästa gång
                self.har_kakor = False
            raise
        return annonser_fran_sida(sida)


def sok_url(s):
    if s.get("url"):
        # En sök-länk kopierad direkt från Vinted. Vi ser till att nyaste visas först.
        delar = urllib.parse.urlsplit(s["url"])
        par = [(k, v) for k, v in urllib.parse.parse_qsl(delar.query) if k != "order"]
        par.append(("order", "newest_first"))
        return VINTED + delar.path + "?" + urllib.parse.urlencode(par)
    par = {"search_text": s.get("sokord", ""), "order": "newest_first", "currency": "SEK"}
    if s.get("maxpris"):
        par["price_to"] = s["maxpris"]
    if s.get("minpris"):
        par["price_from"] = s["minpris"]
    return VINTED + "/catalog?" + urllib.parse.urlencode(par)


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


def matchar(annons, s):
    """Filtren som Vinted-sökningen själv inte klarar av."""
    if s.get("maxpris") and annons["pris"] > float(s["maxpris"]):
        return False
    if s.get("minpris") and annons["pris"] < float(s["minpris"]):
        return False
    if s.get("marke") and s["marke"].lower() not in annons["marke"].lower():
        return False
    if s.get("storlekar"):
        storlek = annons["storlek"].lower()
        if not any(v.lower() in storlek for v in s["storlekar"]):
            return False
    if s.get("skick") and annons["skick"] not in s["skick"]:
        return False
    titel = annons["titel"].lower()
    if any(ord_.lower() in titel for ord_ in s.get("uteslut", [])):
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
    info = " · ".join(x for x in [annons["marke"], annons["storlek"], annons["skick"]] if x)
    if info:
        rader.append(html.escape(info))
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


def ska_till_telegram(annons, s):
    lage = s.get("telegram", "kap")  # "kap", "alla" eller "av"
    return lage == "alla" or (lage == "kap" and annons["kap"])


def en_runda(vinted, inst, sokningar, sedda, traffar_lista, test=False):
    nu = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for s in sokningar:
        if s.get("aktiv") is False:
            continue
        namn = s.get("namn") or s.get("sokord") or "sökning"
        try:
            annonser = vinted.sok(s)
        except Exception as e:  # nätverksfel, Vinted blockerar en stund, osv.
            logg("Fel vid sökning '%s': %s" % (namn, e))
            continue
        traffar = [a for a in annonser if matchar(a, s)]
        # Vanligt pris = medianpriset bland träffarna (minst 5 st). Visas också på hemsidan.
        priser = [a["pris"] for a in traffar]
        vanligt = median(priser) if len(priser) >= 5 else None
        tidigare = sedda.get(namn)
        nya = [a for a in traffar if tidigare is not None and str(a["id"]) not in tidigare]
        if tidigare is None:  # första gången: visa nuvarande träffar på hemsidan, men ingen notis
            nya_pa_sidan = traffar
            logg("'%s': första körningen, %d nuvarande träffar sparas som redan sedda." % (namn, len(traffar)))
        else:
            nya_pa_sidan = nya
        for a in traffar:
            a["kap"] = ar_kap(a, s, vanligt)
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
        traffar_lista[namn] = {
            "vanligt_pris": vanligt,
            "uppdaterad": nu,
            "annonser": (nya_pa_sidan + [a for a in gamla if str(a["id"]) not in kanda])[:MAX_TRAFFAR_PER_SOKNING],
        }

        ids = [str(a["id"]) for a in annonser] + list(tidigare or [])
        sedda[namn] = list(dict.fromkeys(ids))[:MAX_SEDDA_PER_SOKNING]
        time.sleep(random.uniform(2, 5))  # lite paus mellan sökningar
    # Släng hemsidans listor för alarm som tagits bort.
    aktuella = {s.get("namn") or s.get("sokord") or "sökning" for s in sokningar}
    for namn in list(traffar_lista):
        if namn not in aktuella:
            del traffar_lista[namn]
    spara_json(SEDDA_FIL, sedda)
    spara_json(TRAFFAR_FIL, traffar_lista)


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
    while True:
        sokningar = las_json(SOKNINGAR_FIL, [])  # läses om varje runda, så ändringar slår igenom direkt
        en_runda(vinted, inst, sokningar, sedda, traffar_lista, test=arg.test)
        if arg.en_gang or arg.test:
            break
        vanta = inst["intervall_sekunder"] + random.uniform(-20, 20)
        time.sleep(max(60, vanta))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logg("Avslutad.")
