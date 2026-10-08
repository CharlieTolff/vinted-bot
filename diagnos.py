# Tillfälligt testskript: körs i GitHub Actions för att se hur Vinted svarar.
import json, re, sys, time, collections, urllib.error, urllib.request
sys.path.insert(0, ".")
import vinted_bot as vb

def rad(*a): print(*a, flush=True)

def items_raw(sida):
    bitar = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', sida)
    text = "".join(json.loads(b) for b in bitar)
    dec = json.JSONDecoder(); ut = {}
    for m in re.finditer(r'"productItem":', text):
        try: a, _ = dec.raw_decode(text, m.end())
        except ValueError: continue
        if isinstance(a, dict) and "id" in a and "price" in a: ut[a["id"]] = a
    return list(ut.values())

def api(v, vag):
    req = urllib.request.Request("https://www.vinted.se" + vag, headers={"User-Agent": vb.WEBBLASARE, "Accept": "application/json"})
    try:
        with v.oppnare.open(req, timeout=30) as s: return json.loads(s.read().decode())
    except urllib.error.HTTPError as e: return {"fel": e.code}

v = vb.Vinted()
v.hamta("https://www.vinted.se/")
def kat(q):
    s = v.hamta("https://www.vinted.se/catalog?order=newest_first&" + q)
    return items_raw(s)

# Vilka länder säljarna kommer från i svenska katalogen
land = collections.Counter(); landid = {}
uids = []
for q in ["search_text=jeans", "search_text=nike", "search_text=ralph+lauren", "catalog_ids[]=5"]:
    for i in kat(q)[:20]: uids.append(i["user"]["id"])
for uid in list(dict.fromkeys(uids))[:70]:
    u = api(v, "/api/v2/users/%s" % uid).get("user") or {}
    land[u.get("country_code")] += 1; landid[u.get("country_code")] = u.get("country_id")
    time.sleep(0.2)
rad("LÄNDER", land.most_common(), landid)

for q in ["search_text=jeans&country_ids[]=%s" % landid.get("SE"), "search_text=jeans&brand_ids[]=95256", "search_text=&brand_ids[]=95256&catalog_ids[]=5",
          "search_text=jeans&status_ids[]=1", "search_text=jeans&status_ids[]=2", "search_text=jeans&status_ids[]=3", "search_text=jeans&status_ids[]=4",
          "search_text=jeans&page=2", "search_text=jeans&catalog_ids[]=1231", "search_text=jeans&catalog_ids[]=16", "search_text=jeans&catalog_ids[]=82", "search_text=jeans&catalog_ids[]=1187", "search_text=jeans&catalog_ids[]=19"]:
    its = kat(q)
    rad("FILTER", q, len(its), [(x["title"][:40], (x.get("itemBox") or {}).get("firstLine"), (x.get("itemBox") or {}).get("secondLine")) for x in its[:5]])
    if q.startswith("search_text=jeans&country_ids"):
        c = collections.Counter()
        for x in its[:15]:
            c[(api(v, "/api/v2/users/%s" % x["user"]["id"]).get("user") or {}).get("country_code")] += 1
        rad("LÄNDER MED country_ids", c)
