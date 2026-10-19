"""Egna börsanalyser: du gör ett filter (sökord, märken och gärna inspirationsbilder) på börssidan,
och här mäts vad som säljer bäst inom det.

Varje runda söker den på Vinted (allt som ligger ute, nyast först) och på Tradera (sålda annonser).
Har analysen bilder jämförs varje annonsbild med dem (den gratis bildmodellen CLIP), och bara de som
liknar räknas. Annonser på Vinted som fanns vid förra rundan men inte nu har sålts (eller tagits bort).

Filtren ligger i spaningar.json (hemsidan sparar dem dit). Det som hemsidan visar sparas i spaning.json,
och vad som redan är granskat i spaning_minne.json.
"""
import calendar
import hashlib
import json
import os
import random
import time
import urllib.parse

import marknad as mk
import vinted_bot as vb

MAPP = os.path.dirname(os.path.abspath(__file__))
SPANINGAR_FIL = os.path.join(MAPP, "spaningar.json")
VISNING_FIL = os.path.join(MAPP, "spaning.json")
MINNE_FIL = os.path.join(MAPP, "spaning_minne.json")

TIDSGRANS_SEK = 150
VINTED_SIDOR = 3          # högst så många sidor (96 annonser) per sökord och runda
VINTED_PER_RUNDA = 15     # högst så många frågor till Vinted per runda, så att alarmen aldrig blir blockerade
BILDER_PER_RUNDA = 150
LIKHET = 0.80             # så lik en inspirationsbild måste annonsen vara för att räknas
SPARA_DAGAR = 60          # träffar sparas så här länge
KOLLADE_DAGAR = 14        # granskade bilder minns så här länge


def logg(text):
    vb.logg("[analys] " + text)


def nyckel(sp):
    """Ändras sökord, märken eller bilder börjar analysen om."""
    delar = [vb.lista(sp.get("sokord")), vb.lista(sp.get("marke")), sp.get("bilder") or [],
             [w.lower() for w in vb.lista(sp.get("uteslut"))], sp.get("maxpris")]
    return hashlib.sha1(json.dumps(delar, ensure_ascii=False).encode()).hexdigest()[:10]


def utesluten(titel, sp):
    t = " " + mk.normalisera(titel) + " "
    return any(mk.normalisera(w) in t for w in vb.lista(sp.get("uteslut")) if w.strip())


def tradera_bild(it):
    """Första bildlänken i en Tradera-annons (fältens namn varierar)."""
    for k in ("imageUrl", "mainImageUrl", "thumbnailUrl", "imageLink", "image"):
        v = it.get(k)
        if isinstance(v, str) and v.startswith("http"):
            return v
        if isinstance(v, dict):
            for u in v.values():
                if isinstance(u, str) and u.startswith("http"):
                    return u
    for k in ("images", "imageLinks", "imageUrls"):
        for v in it.get(k) or []:
            if isinstance(v, str) and v.startswith("http"):
                return v
            if isinstance(v, dict):
                for u in v.values():
                    if isinstance(u, str) and u.startswith("http"):
                        return u
    return ""


def tradera_lank(it):
    u = it.get("itemUrl") or it.get("url") or "/item/%s" % it.get("itemId")
    return u if u.startswith("http") else "https://www.tradera.com" + u


class Analys:
    def __init__(self, minne, bors):
        self.minne = minne
        self.bors = bors
        self.vinted = None
        self.tradera = None
        self.clip = None
        self.clip_fel = False
        self.vinted_fragor = 0
        self.bilder_kvar = BILDER_PER_RUNDA
        self.start = time.time()

    def tid_kvar(self):
        return time.time() - self.start < TIDSGRANS_SEK

    def bildmodell(self):
        if self.clip is None and not self.clip_fel:
            try:
                from bildkoll import Clip
                self.clip = Clip()
            except Exception as e:
                logg("bildmodellen gick inte att starta (%s), bilderna jämförs inte den här rundan." % e)
                self.clip_fel = True
        return self.clip

    def likhet(self, sp, mm, id_, bild_url):
        """Hur lik annonsen är inspirationsbilderna: 1.0 om analysen inte har bilder, None om den inte hunnit granskas."""
        bilder = sp.get("bilder") or []
        if not bilder:
            return 1.0
        k = mm["kollade"].get(id_)
        if k:
            return k[0]
        if not bild_url or self.bilder_kvar <= 0 or not self.tid_kvar() or not self.bildmodell():
            return None
        self.bilder_kvar -= 1
        try:
            from bildkoll import hamta_bild
            lik = self.clip.likhet(self.clip.bildvektor(hamta_bild(bild_url)[0]), bilder)
        except Exception as e:
            logg("kunde inte granska bilden i %s: %s" % (id_, e))
            return None
        if lik is None:
            return None
        mm["kollade"][id_] = [round(lik, 3), round(time.time())]
        return lik

    def vinted_url(self, q, marke_ids, sp, sida):
        par = [("order", "newest_first"), ("currency", "SEK"), ("search_text", q), ("catalog_ids[]", 2050)]
        par += [("brand_ids[]", m) for m in marke_ids]
        if sp.get("maxpris"):
            par.append(("price_to", sp["maxpris"]))
        if sida > 1:
            par.append(("page", sida))
        return vb.VINTED + "/catalog?" + urllib.parse.urlencode(par)

    def mat_vinted(self, sp, mm):
        if self.vinted is None:
            self.vinted = mk.VintedKalla(self.bors)
        marke_ids = [i for i in (self.vinted.marke_id(m) for m in vb.lista(sp.get("marke"))) if i]
        if vb.lista(sp.get("marke")) and not marke_ids:
            return "hittade inga av märkena på Vinted"
        nu = time.time()
        nya = 0
        for q in vb.lista(sp.get("sokord")) or [""]:
            annonser, totalt = [], None
            for s in range(1, VINTED_SIDOR + 1):
                if self.vinted_fragor >= VINTED_PER_RUNDA:
                    break
                self.vinted_fragor += 1
                sida, tot = self.vinted.sida(self.vinted_url(q, marke_ids, sp, s))
                totalt = tot if totalt is None else totalt
                annonser += sida
                if not sida or len(annonser) >= (totalt or 0):
                    break
                time.sleep(random.uniform(1.2, 2.2))
            if not annonser:
                continue
            ids = sorted({int(a["id"]) for a in annonser if str(a.get("id", "")).isdigit()})
            # Syns inte allt räknas bara det som är nyare än den äldsta annonsen som syns nu.
            grans = 0 if (totalt or 0) <= len(ids) else ids[0]
            for a in annonser:
                if utesluten(a.get("titel", ""), sp):
                    continue
                id_ = str(a["id"])
                lik = self.likhet(sp, mm, id_, a.get("bild"))
                if lik is None or lik < LIKHET:
                    continue
                t = mm["traffar"].get(id_)
                if not t:
                    nya += 1
                    t = mm["traffar"][id_] = {"k": "vinted", "q": q, "f": round(nu)}
                t.update({"m": a.get("marke") or "", "p": a.get("pris"), "g": a.get("gillas") or 0, "b": a.get("bild") or "",
                          "l": a.get("lank") or "", "ti": a.get("titel", "")[:80], "lik": round(lik, 2), "s": None, "u": 0})
            finns = set(ids)
            for id_, t in mm["traffar"].items():
                if t["k"] != "vinted" or t.get("q") != q or t.get("s") or int(id_) in finns:
                    continue
                if int(id_) >= grans:
                    t["s"] = round(nu)  # fanns förra rundan men inte nu: såld
                else:
                    t["u"] = 1  # för gammal för att synas i sökningen längre, vet inte om den sålts
        return "%d nya liknande på Vinted" % nya

    def mat_tradera(self, sp, mm, marken):
        if self.tradera is None:
            self.tradera = mk.TraderaKalla()
        mn = mk.marken_norm(marken)
        nya, utan_bild = 0, 0
        for q in vb.lista(sp.get("sokord")) or vb.lista(sp.get("marke")):
            for m in (vb.lista(sp.get("marke")) or [None]):
                if not self.tid_kvar():
                    break
                res = self.tradera.sok(('"%s" %s' % (m, q)) if m else q)
                time.sleep(random.uniform(1, 2))
                for it in res.get("items") or []:
                    titel = it.get("shortDescription", "")
                    id_ = "t" + str(it.get("itemId"))
                    if id_ in mm["traffar"] or utesluten(titel, sp) or not it.get("price"):
                        continue
                    if sp.get("maxpris") and it["price"] > sp["maxpris"]:
                        continue
                    bild = tradera_bild(it)
                    if not bild and sp.get("bilder"):
                        utan_bild += 1
                        continue
                    lik = self.likhet(sp, mm, id_, bild)
                    if lik is None or lik < LIKHET:
                        continue
                    try:
                        s = calendar.timegm(time.strptime(it["endDate"][:10], "%Y-%m-%d"))
                    except Exception:
                        s = round(time.time())
                    mm["traffar"][id_] = {"k": "tradera", "m": m or mk.hitta_marke(titel, mn) or "", "p": it["price"], "g": 0,
                                          "b": bild, "l": tradera_lank(it),
                                          "ti": titel[:80], "lik": round(lik, 2), "f": s, "s": s, "u": 0}
                    nya += 1
        if utan_bild and not mm.get("tradera_varnat"):
            mm["tradera_varnat"] = True
            exempel = (res.get("items") or [{}])[0]
            logg("hittade ingen bild i Traderas annonser, fälten är: %s" % ", ".join(sorted(exempel)))
        return "%d nya sålda på Tradera" % nya


def kanda_marken(bors, sokningar):
    namn = set(mk.alarm_marken(sokningar))
    for kat in (bors.get("andel", {}).get("vinted") or {}).values():
        if kat:
            namn.update(kat[-1][2].keys())
    return list(namn)


def kor():
    spaningar = vb.las_json(SPANINGAR_FIL, [])
    minne = vb.las_json(MINNE_FIL, {})
    bors = mk.las_bors()
    bors.setdefault("vinted_marken", {}).update(minne.get("_marken") or {})
    sokningar = vb.las_json(vb.SOKNINGAR_FIL, [])
    an = Analys(minne, bors)
    marken = kanda_marken(bors, sokningar)
    nu = time.time()
    visning = {"analyser": [], "uppdaterad": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    aktiva = set()
    # Den som mättes längst sedan först, så att alla hinns med.
    for sp in sorted(spaningar, key=lambda s: minne.get(s.get("namn", ""), {}).get("senast", 0)):
        namn = sp.get("namn") or ", ".join(vb.lista(sp.get("sokord")))
        if not namn or namn == "_marken":
            continue
        aktiva.add(namn)
        mm = minne.get(namn)
        if not mm or mm.get("nyckel") != nyckel(sp):
            mm = minne[namn] = {"nyckel": nyckel(sp), "traffar": {}, "kollade": {}, "start": round(nu)}
        if an.tid_kvar():
            for kalla, fn in (("vinted", lambda: an.mat_vinted(sp, mm)), ("tradera", lambda: an.mat_tradera(sp, mm, marken))):
                try:
                    logg("%s, %s: %s" % (namn, kalla, fn()))
                except Exception as e:
                    logg("%s, %s: fel, %s" % (namn, kalla, e))
            mm["senast"] = round(time.time())
        grans = nu - SPARA_DAGAR * 86400
        mm["traffar"] = {k: v for k, v in mm["traffar"].items() if (v.get("s") or v["f"]) >= grans}
        grans = nu - KOLLADE_DAGAR * 86400
        mm["kollade"] = {k: v for k, v in mm["kollade"].items() if v[1] >= grans}
        visning["analyser"].append({"namn": namn, "start": mm["start"], "senast": mm.get("senast"),
                                    "traffar": [dict(v, id=k) for k, v in mm["traffar"].items() if not v.get("u")]})
    for namn in [n for n in minne if n not in aktiva and n != "_marken"]:
        del minne[namn]
    minne["_marken"] = bors.get("vinted_marken", {})  # Vinteds nummer för märkena
    mk.spara_kompakt(MINNE_FIL, minne)
    mk.spara_kompakt(VISNING_FIL, visning)
    logg("%d analyser, %d bilder granskade." % (len(visning["analyser"]), BILDER_PER_RUNDA - an.bilder_kvar))


if __name__ == "__main__":
    kor()
