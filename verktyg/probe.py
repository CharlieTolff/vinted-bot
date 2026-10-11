"""Tillfälligt: testar datakällor från GitHub Actions."""
import json, re, sys, urllib.parse, urllib.request, html as H
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
        print("FEL", repr(e)[:500], flush=True)

v = vb.Vinted()
def vinted_kat():
    for u in ["/api/v2/catalog/initializers", "/api/v2/catalogs"]:
        try:
            d = v.api(u)
            s = json.dumps(d, ensure_ascii=False)
            print(u, "len", len(s), s[:300])
            def walk(n, path, depth=0):
                if isinstance(n, dict):
                    if "id" in n and "title" in n and isinstance(n.get("catalogs"), list):
                        p = path + [n["title"]]
                        if p[0] in ("Herr", "Män", "Men") or (len(p) > 1 and p[1] in ("Herr",)):
                            if len(p) <= 4:
                                print("KAT", n["id"], " > ".join(p))
                        for c in n["catalogs"]:
                            walk(c, p, depth+1)
                        return
                    for k, val in n.items():
                        walk(val, path, depth)
                elif isinstance(n, list):
                    for x in n:
                        walk(x, path, depth)
            walk(d, [])
            return
        except Exception as e:
            print(u, "FEL", repr(e)[:200])
steg("vinted kategorier", vinted_kat)

def vinted_sok():
    bid = v.marke_id("J.Lindeberg"); print("brand", bid)
    for par in ([("catalog_ids[]", 2050)], [("catalog_ids[]", 2050), ("brand_ids[]", bid)], [("search_text", "cardigan"), ("catalog_ids[]", 2050), ("brand_ids[]", bid)]):
        u = vb.VINTED + "/catalog?" + urllib.parse.urlencode(par + [("order", "newest_first")])
        sida = v.hamta(u)
        t = vb.sidans_data(sida)
        m = re.search(r'"pagination":(\{[^{}]*\})', t)
        a = vb.annonser_fran_sida(sida)
        print(par, m.group(1) if m else None, len(a), [x["pris"] for x in a[:8]], [x["gillas"] for x in a[:8]])
    try:
        d = v.api("/api/v2/catalog/items?" + urllib.parse.urlencode({"catalog_ids": "2050", "brand_ids": bid, "per_page": 96, "order": "newest_first"}))
        print("api items", d.get("pagination"), len(d.get("items", [])))
    except Exception as e:
        print("api items FEL", repr(e)[:200])
steg("vinted sök", vinted_sok)

def tradera():
    for status in ("Sold", "Active", "Unsold"):
        u = "https://www.tradera.com/search?" + urllib.parse.urlencode({"q": "j.lindeberg cardigan", "itemStatus": status})
        st, b = get(u)
        t = vb.sidans_data(b)
        i = t.find('"discover/receiveSearchResults"')
        print(status, st, len(b), len(t), i)
        if i >= 0:
            j = t.find('"result":', i)
            res, _ = json.JSONDecoder().raw_decode(t, j + 9)
            it = res.get("items") or []
            print(" total", res.get("totalItemCount"), "items", len(it), "keys", list(res)[:20])
            if it: print(" item", json.dumps(it[0], ensure_ascii=False)[:700])
        else:
            print(" snippet", b[:500])
steg("tradera", tradera)

def plick():
    for u in ["https://plick.se/sok?query=j.lindeberg+cardigan", "https://plick.se/search?query=j.lindeberg+cardigan",
              "https://plick.se/s/j.lindeberg%20cardigan", "https://api.plick.se/api/v2/search?query=j.lindeberg%20cardigan",
              "https://plick.se/m%C3%A4rkeskl%C3%A4der"]:
        try:
            st, b = get(u)
            print(u, st, len(b))
            body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", b, flags=re.S)
            txt = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", body)))
            print(" text", txt[:1200])
            print(" links", list(dict.fromkeys(re.findall(r'href="(/[^"]+)"', b)))[:60])
            print(" scripts", re.findall(r'<script[^>]*src="([^"]+)"', b)[:10])
            for k in ("annonser", "resultat", "price", "pris", "data-", "turbo-frame", "json"):
                i = b.find(k)
                if i >= 0: print(" ", k, "=>", b[max(0,i-200):i+300].replace("\n"," "))
        except Exception as e:
            print(u, "FEL", repr(e)[:200])
steg("plick", plick)
