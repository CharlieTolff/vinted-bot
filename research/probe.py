import json, re, sys, urllib.request, urllib.parse, time
sys.path.insert(0, ".")
import vinted_bot as vb

UA = vb.WEBBLASARE
def get(url, extra=None):
    h = {"User-Agent": UA, "Accept": "text/html,application/json", "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8"}
    h.update(extra or {})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", "ERR"), str(e)

v = vb.Vinted()
sida = v.hamta(vb.VINTED + "/catalog?search_text=barbour&catalog_ids[]=2050")
text = vb.sidans_data(sida)
m = re.search(r'"productItem":', text)
a, _ = json.JSONDecoder().raw_decode(text, m.end())
print("VINTED HTML ITEM:", json.dumps(a)[:3000])
print("N items html:", len(vb.annonser_fran_sida(sida)))
try:
    r = v.api("/api/v2/catalog/items?" + urllib.parse.urlencode({"search_text": "barbour", "per_page": 96, "catalog_ids": 2050}))
    its = r.get("items") or []
    print("API items:", len(its), "keys:", list(its[0].keys()) if its else None)
    print("API ITEM:", json.dumps(its[0])[:2500] if its else r)
    print("API pagination:", r.get("pagination"))
except Exception as e:
    print("API fail", e)

for u in ["https://www.tradera.com/search?q=barbour%20bedale",
          "https://www.tradera.com/search?q=barbour%20bedale&itemStatus=Ended",
          "https://www.tradera.com/search?q=barbour%20bedale&itemStatus=Sold",
          "https://www.tradera.com/search?q=barbour+bedale&sold=true"]:
    st, b = get(u)
    nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', b, re.S)
    print("TRADERA", u, st, len(b), "nextdata" if nd else "no-nextdata")
    if nd:
        d = json.loads(nd.group(1))
        s = json.dumps(d)
        i = s.find("itemStatus")
        print("  snippet:", s[:300])
        print("  around items:", s[max(0, s.find('"items"')):s.find('"items"') + 2500])
    else:
        print("  body:", b[:500].replace("\n", " "))
        for k in ["Såld", "Sold", "Avslutad", "price", "kr"]:
            print("  ", k, b.count(k))
    time.sleep(2)

st, b = get("https://www.ebay.co.uk/sch/i.html?_nkw=barbour+bedale&LH_Sold=1&LH_Complete=1&_ipg=60")
print("EBAY", st, len(b), "prices:", re.findall(r's-item__price[^>]*>(?:<[^>]+>)*([^<]+)', b)[:20], "s-card", b.count("s-card"))
print(b[:300])
for u in ["https://www.reddit.com/r/Flipping/search.json?q=vinted&restrict_sr=1&sort=top&t=all&limit=5",
          "https://old.reddit.com/r/Flipping/search.json?q=vinted&restrict_sr=1&limit=5"]:
    st, b = get(u, {"User-Agent": "research-script/0.1 by valtoresell"})
    print("REDDIT", u, st, b[:400])
for u in ["https://www.flashback.org/sok/?query=vinted+resell", "https://plick.se/profiler/barelicloset",
          "https://www.tiktok.com/discover/best-brands-to-resell-on-vinted"]:
    st, b = get(u)
    print("OTHER", u, st, len(b))
