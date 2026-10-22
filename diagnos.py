"""Felsökning av Märkesbörsen: skriver ut hur mätningarna ser ut i loggen, så att de går att granska.

Körs för hand från Actions (Diagnos). Ändrar inget i den sparade historiken.
"""
import json
import random
import re
import sys
import time
import urllib.error

import marknad as mk
import vinted_bot as vb


def rubrik(t):
    print("\n===== %s =====" % t, flush=True)


def sparat():
    bors = vb.las_json(mk.BORS_FIL, {})
    salda = vb.las_json(mk.SALDA_FIL, {})
    rubrik("SPARAT")
    print("uppdaterad", bors.get("uppdaterad"), "kö", bors.get("ko"))
    print("kategorier", [k["id"] for k in bors.get("kategorier", [])])
    print("alarm-märken", sorted(bors.get("alarm", {})))
    for kalla, kats in bors.get("andel", {}).items():
        for kat, pts in kats.items():
            if not pts:
                continue
            d, n, marken, ovr = pts[-1]
            topp = sorted(marken.items(), key=lambda x: -x[1][0])
            print("andel %s %s %s: n=%d, övriga=%d (%.0f%%), punkter=%d" % (kalla, kat, d, n, ovr, 100 * ovr / max(n, 1), len(pts)))
            print("   ", "; ".join("%s %d/%s" % (m, v[0], v[1]) for m, v in topp[:25]))
    for kat, rader in salda.items():
        alla = list(rader.values())
        ovr = sum(1 for r in alla if r[1] == "Övriga")
        datum = sorted(r[0] for r in alla)
        print("tradera_salda %s: %d sålda, övriga %.0f%%, %s..%s" % (kat, len(alla), 100 * ovr / max(len(alla), 1), datum[0] if datum else "", datum[-1] if datum else ""))
    for kalla, kats in bors.get("marke", {}).items():
        for kat, mm in kats.items():
            rad = []
            for m, pts in sorted(mm.items()):
                if pts:
                    rad.append("%s %s" % (m, pts[-1][1:]))
            print("märke %s %s: %s" % (kalla, kat, " | ".join(rad)))
    return bors


def vinted_varianter(v, namn):
    rubrik("VINTED MÄRKESVARIANTER")
    for n in namn:
        try:
            marken = v.api("/api/v2/brands?" + __import__("urllib.parse").parse.urlencode({"keyword": n})).get("brands") or []
            print(n, "->", "; ".join("%s(%s, %s st)" % (m.get("title"), m.get("id"), m.get("item_count") or m.get("favourite_count")) for m in marken[:12]))
        except Exception as e:
            print(n, "fel", e)
        time.sleep(random.uniform(1, 2))


def vinted_stickprov(bors):
    rubrik("VINTED STICKPROV (första sidan per kategori)")
    kalla = mk.VintedKalla(bors)
    for kat in mk.BAS_KATEGORIER + mk.egna_kategorier():
        try:
            url = kalla.url(kat)
            nya, totalt = kalla.sida(url)
            marken = {}
            for a in nya:
                marken[a["marke"] or "(inget)"] = marken.get(a["marke"] or "(inget)", 0) + 1
            print("%s kat=%s totalt=%s n=%d url=%s" % (kat["id"], kalla.katalog_id(kat), totalt, len(nya), url))
            print("   märken:", sorted(marken.items(), key=lambda x: -x[1])[:20])
            print("   titlar:", " | ".join("%s: %s (%s kr)" % (a["marke"], a["titel"][:40], a["pris"]) for a in nya[:12]))
        except Exception as e:
            print(kat["id"], "fel", e)
        time.sleep(random.uniform(1.5, 2.5))
    return kalla


def vinted_salda(kalla, bors):
    """Kollar om annonser som försvunnit sedan förra mätningen är sålda eller borttagna."""
    rubrik("VINTED FÖRSVUNNA: SÅLDA ELLER BORTTAGNA?")
    sett = bors.get("vinted_sett", {})
    kollade = 0
    for kat_id, mm in sett.items():
        kat = next((k for k in mk.BAS_KATEGORIER + mk.egna_kategorier() if k["id"] == kat_id), None)
        if not kat:
            continue
        for namn, (t, gamla) in list(mm.items())[:2]:
            mid = kalla.marke_id(namn)
            if not mid:
                continue
            try:
                nu, totalt = kalla.sida(kalla.url(kat, mid))
            except Exception as e:
                print(kat_id, namn, "fel", e)
                continue
            ids = {int(a["id"]) for a in nu}
            grans = min(ids) if ids else 0
            borta = [i for i in gamla if i >= grans and i not in ids]
            utfall = {}
            for i in borta[:8]:
                time.sleep(random.uniform(1.2, 2.0))
                try:
                    text = vb.sidans_data(kalla.v.hamta(vb.VINTED + "/items/%s" % i))
                    if re.search(r'"item_id":"%s"[^{}]*"title":"Såld"' % i, text) or '"is_closed":true' in text:
                        u = "såld"
                    elif '"is_hidden":true' in text:
                        u = "dold"
                    else:
                        u = "finns"
                except urllib.error.HTTPError as e:
                    u = "borta %s" % e.code
                except Exception as e:
                    u = "fel"
                utfall[u] = utfall.get(u, 0) + 1
            print("%s %s: sedan %.1f h, %d försvunna av %d, kollade %d: %s" % (
                kat_id, namn, (time.time() - t) / 3600, len(borta), len(gamla), min(8, len(borta)), utfall))
            kollade += 1
            if kollade >= 6:
                return


def tradera_stickprov(bors):
    rubrik("TRADERA STICKPROV (sålda, första sidan)")
    tk = mk.TraderaKalla()
    for kat in mk.BAS_KATEGORIER + mk.egna_kategorier():
        q = kat["tradera"][0]
        try:
            res = tk.sok(q)
            items = res.get("items") or []
            if kat is mk.BAS_KATEGORIER[0]:
                print("svarets nycklar:", sorted(res.keys()))
                print("annonsens nycklar:", sorted(items[0].keys()) if items else None)
                for k in res:
                    if "categor" in k.lower() or "filter" in k.lower() or "facet" in k.lower():
                        print("  %s: %s" % (k, json.dumps(res[k], ensure_ascii=False)[:1500]))
            mn = mk.marken_norm(mk.kanda_marken(bors, kat["id"], bors.get("alarm", {})))
            traff = sum(1 for it in items if mk.hitta_marke(it.get("shortDescription", ""), mn))
            kats = {}
            for it in items:
                c = it.get("categoryId") or it.get("category") or it.get("categoryName")
                kats[str(c)] = kats.get(str(c), 0) + 1
            print("%s q=%s totalt=%s n=%d, märke hittat %d, kategorier %s" % (kat["id"], q, res.get("totalItemCount"), len(items), traff, sorted(kats.items(), key=lambda x: -x[1])[:8]))
            print("   ", " | ".join("%s -> %s (%s kr)" % (it.get("shortDescription", "")[:45], mk.hitta_marke(it.get("shortDescription", ""), mn), it.get("price")) for it in items[:20]))
        except Exception as e:
            print(kat["id"], "fel", e)
        time.sleep(random.uniform(1.5, 2.5))


def vinted_falt(kalla):
    """Vilka fält Vinted skickar med för varje annons i sökningen (finns säljarens land?)."""
    rubrik("VINTED FÄLT")
    text = vb.sidans_data(kalla.v.hamta(kalla.url(mk.BAS_KATEGORIER[2])))
    m = re.search(r'"productItem":', text)
    a, _ = json.JSONDecoder().raw_decode(text, m.end())
    print(json.dumps(a, ensure_ascii=False)[:3000])
    for nyckel in ("country", "Country", "locale", "iso_code", "countryCode"):
        print(nyckel, text.count(nyckel))


def tradera_djup():
    """Traderas kategorier (namn och föräldrar), märkesfältet i annonserna och om sökningen kan begränsas till en kategori."""
    rubrik("TRADERA KATEGORIER OCH MÄRKEN")
    tk = mk.TraderaKalla()
    res = tk.sok("cardigan")
    f = res.get("filters") or {}
    for typ, lista_ in f.items():
        if not isinstance(lista_, list):
            print("filter %s = %s" % (typ, json.dumps(lista_, ensure_ascii=False)[:1500]))
            continue
        for x in lista_:
            if not isinstance(x, dict):
                print("filter %s: %s" % (typ, json.dumps(x, ensure_ascii=False)[:600]))
                continue
            print("filter %s %s: %s" % (typ, x.get("parameter"), json.dumps(x.get("options") or x, ensure_ascii=False)[:1200]))
    for it in (res.get("items") or [])[:8]:
        print("attr:", it.get("shortDescription"), json.dumps(it.get("attributes"), ensure_ascii=False)[:600], it.get("sellerCountryCodeIso2"), it.get("sellerIsCompany"))
    for cid in ["343837", "1000656", "1000678", "1000675", "1000696", "1000695", "1000733", "1000734", "1000398", "1000397", "340326", "340327", "340304", "1000392"]:
        for url in ["https://www.tradera.com/category/%s?itemStatus=Sold" % cid]:
            try:
                text = vb.sidans_data(mk.hamta(url))
                i = text.find('"discover/receiveSearchResults"')
                r = {}
                if i >= 0:
                    j = text.find('"result":', i)
                    r, _ = json.JSONDecoder().raw_decode(text, j + len('"result":'))
                titel = re.search(r"<title>([^<]*)</title>", text)
                print("kategori %s: titel=%s, väg=%s, sålda=%s, först: %s" % (
                    cid, titel.group(1) if titel else None, json.dumps(r.get("categoryPath"), ensure_ascii=False)[:500],
                    r.get("totalItemCount"), " | ".join(x.get("shortDescription", "")[:30] for x in (r.get("items") or [])[:6])))
            except Exception as e:
                print("kategori", cid, "fel", e)
            time.sleep(random.uniform(1, 2))
    for q, cid in [("cardigan", "343837"), ("jeans", "340326"), ("jeans", "340327"), ("skjorta", "1000678")]:
        for par in ("categoryId", "category"):
            try:
                url = "https://www.tradera.com/search?" + __import__("urllib.parse").parse.urlencode([("q", q), (par, cid), ("itemStatus", "Sold")])
                text = vb.sidans_data(mk.hamta(url))
                i = text.find('"discover/receiveSearchResults"')
                j = text.find('"result":', i)
                r, _ = json.JSONDecoder().raw_decode(text, j + len('"result":'))
                kats = {}
                for it in r.get("items") or []:
                    kats[str(it.get("categoryId"))] = kats.get(str(it.get("categoryId")), 0) + 1
                print("sök %s %s=%s: totalt=%s väg=%s kategorier=%s" % (q, par, cid, r.get("totalItemCount"), json.dumps(r.get("categoryPath"), ensure_ascii=False)[:300], kats))
            except Exception as e:
                print("sök", q, par, cid, "fel", e)
            time.sleep(random.uniform(1, 2))


def tradera_sortering():
    """Vilken sortering som ger de senast sålda först, hur långt bak Tradera visar sålda och hur ofta märket finns i annonsen."""
    rubrik("TRADERA SORTERING")
    import urllib.parse as up

    def hamta_res(par):
        text = vb.sidans_data(mk.hamta("https://www.tradera.com/search?" + up.urlencode(par)))
        i = text.find('"discover/receiveSearchResults"')
        j = text.find('"result":', i)
        r, _ = json.JSONDecoder().raw_decode(text, j + len('"result":'))
        return r
    for cid in ["343837", "1639", "340327", "1000695"]:
        for sort in [None, "AddedOn", "TimeLeft"]:
            for status in ["Sold", "Unsold"]:
                par = [("categoryId", cid), ("itemStatus", status)] + ([("sortBy", sort)] if sort else [])
                try:
                    r = hamta_res(par)
                    items = r.get("items") or []
                    slut = sorted(it.get("endDate", "")[:10] for it in items if it.get("endDate"))
                    marke = sum(1 for it in items if any(a.get("name") == "brand" for a in it.get("attributes") or []))
                    print("%s sort=%s %s: totalt=%s sidor=%s, slut %s..%s, märke i %d/%d, företag %d" % (
                        cid, sort, status, r.get("totalItemCount"), (r.get("pagination") or {}).get("pageCount"),
                        slut[0] if slut else "", slut[-1] if slut else "", marke, len(items), sum(1 for it in items if it.get("sellerIsCompany"))))
                except Exception as e:
                    print(cid, sort, status, "fel", e)
                time.sleep(random.uniform(1, 2))
        # Hur långt bak: sida 10 och 25 med senast sålda först
        for sida in (10, 25, 60):
            try:
                r = hamta_res([("categoryId", cid), ("itemStatus", "Sold"), ("sortBy", "AddedOn"), ("paging", sida)])
                slut = sorted(it.get("endDate", "")[:10] for it in r.get("items") or [] if it.get("endDate"))
                print("   sida %d: %d annonser, slut %s..%s" % (sida, len(r.get("items") or []), slut[0] if slut else "", slut[-1] if slut else ""))
            except Exception as e:
                print("   sida", sida, "fel", e)
            time.sleep(random.uniform(1, 2))
    # Fler herrkategorier som kan behövas
    for cid in ["302074", "1622", "340274", "1000738"]:
        try:
            r = hamta_res([("categoryId", cid), ("itemStatus", "Sold")])
            f = (r.get("filters") or {}).get("categoryFilter") or {}
            def ga(n, d=0):
                for c in n.get("children") or []:
                    print("   " * d, c.get("id"), c.get("name"), c.get("count"))
                    ga(c, d + 1)
            print("underkategorier till", cid, "totalt", r.get("totalItemCount"))
            ga(f.get("categoryTree") or {})
        except Exception as e:
            print(cid, "fel", e)
        time.sleep(random.uniform(1, 2))


def main():
    bors = sparat()
    if "--bara-sparat" in sys.argv:
        return
    tradera_sortering()
    if "--allt" not in sys.argv:
        return
    tradera_djup()
    vinted_falt(mk.VintedKalla(bors))
    if "--allt" not in sys.argv:
        return
    kalla = vinted_stickprov(bors)
    vinted_varianter(kalla.v, ["Ralph Lauren", "Hugo Boss", "Levi", "Tommy Hilfiger", "Stone Island", "Moncler", "Lacoste", "C.P. Company", "Arc'teryx", "Nudie", "Morris", "Peak Performance"])
    vinted_salda(kalla, bors)
    tradera_stickprov(bors)


if __name__ == "__main__":
    main()
