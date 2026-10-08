# Tillfälligt testskript: körs i GitHub Actions för att se hur Vinted svarar.
import json, re, sys, urllib.parse, urllib.error
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
    return list(ut.values()), text

def hamta(v, url):
    try: return v.hamta(url)
    except urllib.error.HTTPError as e: return "HTTPFEL %s %s" % (e.code, e.read()[:300])
    except Exception as e: return "FEL %r" % e

def api(v, dom, vag):
    import urllib.request
    req = urllib.request.Request("https://www.vinted.%s%s" % (dom, vag), headers={"User-Agent": vb.WEBBLASARE, "Accept": "application/json"})
    try:
        with v.oppnare.open(req, timeout=30) as s: return s.read().decode()[:3000]
    except urllib.error.HTTPError as e: return "HTTPFEL %s %s" % (e.code, e.read()[:300])
    except Exception as e: return "FEL %r" % e

for dom in ["se", "dk", "fi", "de", "fr", "nl", "pl", "co.uk"]:
    v = vb.Vinted()
    hamta(v, "https://www.vinted.%s/" % dom)
    sida = hamta(v, "https://www.vinted.%s/catalog?search_text=nudie+jeans&order=newest_first" % dom)
    if sida.startswith(("HTTPFEL", "FEL")): rad(dom, sida); continue
    its, text = items_raw(sida)
    rad("=== DOMÄN", dom, "antal", len(its), "valutor", sorted({i["price"].get("currency_code") for i in its}))
    if its: rad("FÖRSTA:", json.dumps(its[0], ensure_ascii=False)[:2500])
    if dom == "se":
        for nyckel in ["country", "country_code", "user_id", "userId", "\"user\"", "location", "region"]:
            i = text.find(nyckel); rad("SÖK", nyckel, text[max(0,i-200):i+300].replace("\n"," ") if i >= 0 else "-")
        for q in ["catalog_ids[]=5", "catalog_ids[]=1904", "catalog_ids[]=2050", "catalog_ids[]=257", "catalog_ids[]=4", "status_ids[]=6", "brand_ids[]=34947"]:
            s2 = hamta(v, "https://www.vinted.se/catalog?search_text=jeans&order=newest_first&" + q)
            i2, _ = items_raw(s2) if not s2.startswith(("HTTPFEL","FEL")) else ([], "")
            rad("FILTER", q, len(i2), [ (x.get("title"), (x.get("itemBox") or {}).get("firstLine"), (x.get("itemBox") or {}).get("secondLine")) for x in i2[:6]])
        for vag in ["/api/v2/brands?keyword=nudie", "/api/v2/catalog/filters/search?filter_code=brand&filter_search_text=nudie", "/api/v2/catalog/items?search_text=nudie&per_page=2", "/api/v2/catalog/initializers"]:
            rad("API", vag, api(v, "se", vag)[:1500])
        if its:
            uid = its[0].get("user", {}).get("id") if isinstance(its[0].get("user"), dict) else its[0].get("userId") or its[0].get("user_id")
            rad("UID", uid)
            if uid: rad("USER", api(v, "se", "/api/v2/users/%s" % uid)[:2500])
            rad("ITEMAPI", api(v, "se", "/api/v2/items/%s/details" % its[0]["id"])[:1500])
            sida3 = hamta(v, vb.VINTED + its[0].get("url", ""))
            for nyckel in ["feedback_reputation", "feedback_count", "country_title", "country_iso", "reputation"]:
                i = sida3.find(nyckel); rad("ANNONSSIDA", nyckel, sida3[max(0,i-150):i+250].replace("\n"," ") if i >= 0 else "-")
