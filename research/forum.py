"""Hämtar diskussioner från Reddit (via arkiv-API:er) och Flashback om vad som lönar sig att köpa och sälja vidare."""
import json, re, sys, time, urllib.parse, urllib.request, html as H
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
def get(url, ua=UA):
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.read().decode("utf-8", "replace")
ut = {"reddit": [], "flashback": [], "ovrigt": {}}
SOK = [("Flipping", "vinted"), ("FlippingUK", "vinted"), ("vinted", "flip"), ("vinted", "resell"), ("vinted", "profit"),
       ("Flipping", "menswear"), ("Flipping", "arcteryx"), ("Flipping", "barbour"), ("Flipping", "ralph lauren"),
       ("FlippingUK", "brands"), ("Depop", "flip"), ("sweden", "vinted"), ("Flipping", "best brands"), ("FlippingUK", "best sellers"),
       ("malefashionadvice", "vinted"), ("goodyearwelt", "vinted"), ("Flipping", "cashmere"), ("Flipping", "patagonia")]
for sub, ord_ in SOK:
    for bas in ["https://arctic-shift.photon-reddit.com/api/posts/search?" + urllib.parse.urlencode({"subreddit": sub, "query": ord_, "limit": 50, "sort": "desc"}),
                "https://api.pullpush.io/reddit/search/submission/?" + urllib.parse.urlencode({"subreddit": sub, "q": ord_, "size": 50})]:
        try:
            d = json.loads(get(bas, "research-script/0.1"))
            poster = d.get("data") or []
            for p in poster:
                ut["reddit"].append({"sub": sub, "sok": ord_, "titel": p.get("title"), "text": (p.get("selftext") or "")[:1500],
                                     "poang": p.get("score"), "kommentarer": p.get("num_comments"), "id": p.get("id"),
                                     "datum": time.strftime("%Y-%m-%d", time.gmtime(p.get("created_utc") or 0))})
            print("reddit", sub, ord_, bas[:30], len(poster), flush=True)
            if poster:
                break
        except Exception as e:
            print("reddit fel", sub, ord_, bas[:30], e, flush=True)
        time.sleep(1)
# Toppkommentarer för de mest kommenterade trådarna
topp = sorted({p["id"]: p for p in ut["reddit"]}.values(), key=lambda p: -(p["kommentarer"] or 0))[:40]
ut["reddit_kommentarer"] = {}
for p in topp:
    try:
        d = json.loads(get("https://arctic-shift.photon-reddit.com/api/comments/search?" + urllib.parse.urlencode({"link_id": p["id"], "limit": 100}), "research-script/0.1"))
        ks = sorted(d.get("data") or [], key=lambda c: -(c.get("score") or 0))[:25]
        ut["reddit_kommentarer"][p["id"]] = {"titel": p["titel"], "sub": p["sub"], "kommentarer": [(c.get("score"), (c.get("body") or "")[:700]) for c in ks]}
    except Exception as e:
        print("kommentarer fel", e)
    time.sleep(1)
for ord_ in ["vinted", "tradera köpa sälja vinst", "sälja kläder second hand vinst", "resell kläder", "plick"]:
    try:
        b = get("https://www.flashback.org/sok/?" + urllib.parse.urlencode({"query": ord_}))
        tr = re.findall(r'href="(/t\d+)"[^>]*>\s*([^<]{5,200})<', b)
        ut["flashback"].append({"sok": ord_, "tradar": tr[:40]})
        print("flashback", ord_, len(tr), flush=True)
        if not tr:
            ut["flashback"][-1]["sida"] = re.sub(r"\s+", " ", re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", b, flags=re.S))[:3000]
    except Exception as e:
        print("flashback fel", e)
    time.sleep(2)
for namn, url in [("barelicloset_plick", "https://plick.se/profiler/barelicloset"), ("barelicloset_se", "https://barelicloset.se/"),
                  ("barelicloset_se_produkter", "https://barelicloset.se/collections/all"), ("barelicloset_json", "https://barelicloset.se/products.json?limit=250")]:
    try:
        b = get(url)
        if namn.endswith("json"):
            d = json.loads(b)
            ut["ovrigt"][namn] = [(p.get("title"), p.get("vendor"), p.get("product_type"), [v.get("price") for v in p.get("variants", [])][:1], p.get("created_at", "")[:10]) for p in d.get("products", [])]
        else:
            ut["ovrigt"][namn] = re.sub(r"\s+", " ", H.unescape(re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", b, flags=re.S)))[:12000]
        print("ovrigt", namn, "ok", flush=True)
    except Exception as e:
        print("ovrigt fel", namn, e)
with open("research/forum.json", "w", encoding="utf-8") as f:
    json.dump(ut, f, ensure_ascii=False, indent=1)
