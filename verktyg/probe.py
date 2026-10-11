"""Tillfälligt: testar datakällor från GitHub Actions (runda 2)."""
import json, re, sys, time, urllib.parse, urllib.request, html as H
sys.path.insert(0, ".")
import vinted_bot as vb

def get(url, accept="text/html"):
    req = urllib.request.Request(url, headers={"User-Agent": vb.WEBBLASARE, "Accept": accept, "Accept-Language": "sv-SE,sv;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, r.read().decode("utf-8", "replace")

def steg(namn, f):
    print("=====", namn, flush=True)
    try:
        f()
    except Exception as e:
        import traceback; traceback.print_exc(); sys.stdout.flush()

v = vb.Vinted()
def vinted_kat():
    sida = v.hamta(vb.VINTED + "/catalog?catalog_ids[]=2050")
    t = vb.sidans_data(sida)
    print("len", len(t))
    for ord_ in ["Cardigans", "Koftor", "Stickat", "Skjortor", "Jeans", "Jackor", "Kavajer", "Tröjor", "Ytterkläder", "Västar", "Dunjackor", "Rockar", "Hoodies"]:
        for m in re.finditer(r'"title":"%s"' % ord_, t):
            print(ord_, "=>", t[max(0, m.start()-250):m.end()+120].replace("\n", " "))
            break
    # leta efter katalogträd i början av sidan
    for k in ['"catalogTree"', '"catalogs":[', '"code":"MEN_', '"url":"/catalog/2050']:
        i = t.find(k); print(k, i, t[max(0,i-100):i+500] if i >= 0 else "")
    # en annons-nyckel
    m = re.search(r'"productItem":', t)
    sida = v.hamta(vb.VINTED + "/catalog?catalog_ids[]=2050&order=newest_first")
    t2 = vb.sidans_data(sida)
    m = re.search(r'"productItem":', t2)
    a, _ = json.JSONDecoder().raw_decode(t2, m.end())
    print("ITEM", json.dumps(a, ensure_ascii=False)[:2500])
steg("vinted kategorier", vinted_kat)

def vinted_sidor():
    # Hur långt bak räcker 10 sidor av nyaste i herr-kläder? och sida 11?
    for p in (1, 10, 11):
        u = vb.VINTED + "/catalog?" + urllib.parse.urlencode([("catalog_ids[]", 2050), ("order", "newest_first"), ("page", p), ("search_text", "cardigan")])
        sida = v.hamta(u); a = vb.annonser_fran_sida(sida)
        t = vb.sidans_data(sida); m = re.search(r'"pagination":(\{[^{}]*\})', t)
        print(p, m.group(1) if m else None, len(a), a[0]["id"] if a else None, a[-1]["id"] if a else None, [x["marke"] for x in a[:15]])
        time.sleep(1.5)
steg("vinted sidor", vinted_sidor)

def tradera(q, status, extra=()):
    u = "https://www.tradera.com/search?" + urllib.parse.urlencode([("q", q), ("itemStatus", status)] + list(extra))
    st, b = get(u)
    t = vb.sidans_data(b)
    i = t.find('"discover/receiveSearchResults"')
    j = t.find('"result":', i)
    res, _ = json.JSONDecoder().raw_decode(t, j + 9)
    return u, res

def trad():
    for q, extra in [("j.lindeberg cardigan", ()), ("j.lindeberg", ()), ("cardigan", ()), ('"j.lindeberg" cardigan', ()),
                     ("j.lindeberg cardigan", (("sortBy", "EndDateDescending"),)), ("j.lindeberg cardigan", (("paging", "MjpBdWN0aW9ufDM5fDE5NjE6QXVjdGlvbg"),)),
                     ("j.lindeberg cardigan", (("spage", "2"),)), ("cardigan", (("categoryId", "343837"),))]:
        try:
            u, res = tradera(q, "Sold", extra)
            it = res.get("items") or []
            match = sum(1 for x in it if "lindeberg" in x.get("shortDescription", "").lower())
            print(q, extra, "total", res.get("totalItemCount"), res.get("itemsMatched"), "n", len(it), "lindeberg i titel", match,
                  "slut", [x.get("endDate", "")[:10] for x in it[:5]], "pag", json.dumps(res.get("pagination"))[:300])
            print("  titlar", [x.get("shortDescription", "")[:40] for x in it[:8]])
        except Exception as e:
            print(q, extra, "FEL", repr(e)[:200])
        time.sleep(1.2)
    u, res = tradera("cardigan", "Sold")
    print("categoryPath", json.dumps(res.get("categoryPath"), ensure_ascii=False)[:500])
    print("filters", json.dumps(res.get("filters"), ensure_ascii=False)[:3000])
steg("tradera", trad)

def plick():
    for u in ["https://plick.se/produkter?query=j.lindeberg+cardigan", "https://plick.se/kategorier/stickat?query=j.lindeberg"]:
        st, b = get(u)
        print(u, st, len(b))
        body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", b, flags=re.S)
        txt = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", body)))
        i = txt.find("Vad letar du")
        print(" text", txt[-3000:])
        for k in ("träffar", "resultat", "annonser", 'href="/produkter/', 'class="listing', "kr<", "data-price", "next", "sida="):
            i = b.find(k)
            if i >= 0: print(" ", k, "=>", b[max(0,i-300):i+400].replace("\n"," "))
        print(" prodlinks", len(re.findall(r'href="/produkter/[^"]+"', b)), re.findall(r'href="(/produkter/[^"?]+)"', b)[:5])
        time.sleep(1)
steg("plick", plick)
