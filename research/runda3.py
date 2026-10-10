import json, re, sys, time, urllib.parse, urllib.request, html as H
sys.path.insert(0, ".")
from research.marknadskoll import get
ut = {}
# Plick-profilen: alla länkar och bilder
try:
    b = get("https://plick.se/profiler/barelicloset")
    ut["plick_hrefs"] = sorted(set(re.findall(r'href="(/[^"]+)"', b)))
    i = b.find("Barelicloset", b.find("Gilla") - 3000)
    ut["plick_mitten"] = re.sub(r"\s+", " ", b[b.find("Gilla") - 6000: b.find("Gilla") + 6000])
except Exception as e:
    ut["plick_fel"] = str(e)
# Följ annonslänkarna
for h in [h for h in ut.get("plick_hrefs", []) if re.search(r"/(annons|annonser|items|produkt|p)/", h)][:60]:
    try:
        b = get("https://plick.se" + h)
        t = re.search(r"<title>(.*?)</title>", b, re.S)
        pris = re.findall(r"(\d[\d ]*)\s*kr", b)[:3]
        desc = re.search(r'<meta name="description" content="([^"]*)"', b)
        ut.setdefault("plick_annonser", []).append((h, H.unescape(t.group(1).strip()) if t else "", pris, H.unescape(desc.group(1))[:300] if desc else ""))
        time.sleep(0.8)
    except Exception as e:
        ut.setdefault("plick_annons_fel", []).append(str(e))
# barelicloset.se (Lovable/Supabase): hitta API i JS
try:
    b = get("https://barelicloset.se/")
    js = re.findall(r'src="([^"]+\.js)"', b)
    ut["bc_js"] = js
    for j in js[:3]:
        src = get(j if j.startswith("http") else "https://barelicloset.se" + j)
        sup = set(re.findall(r'https://[a-z0-9]+\.supabase\.co', src))
        keys = set(re.findall(r'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}', src))
        tabeller = set(re.findall(r'\.from\("([a-z_]+)"\)', src))
        ut.setdefault("bc_supabase", []).append([list(sup), len(keys), list(tabeller)])
        # märken och texter som står direkt i koden
        ut.setdefault("bc_strangar", []).extend(sorted(set(s for s in re.findall(r'"([^"]{4,90})"', src) if re.search(r"(?i)(ralph|lauren|stone|moncler|acne|our legacy|gucci|louis|prada|cp company|arc|barbour|canada|kr\b|köper|vi köper|stäng|lägger ner|tack för)", s)))[:300])
        for s in sup:
            for k in list(keys)[:1]:
                for tab in list(tabeller)[:10]:
                    try:
                        req = urllib.request.Request(s + "/rest/v1/" + tab + "?select=*&limit=500", headers={"apikey": k, "Authorization": "Bearer " + k})
                        with urllib.request.urlopen(req, timeout=30) as r:
                            rows = json.load(r)
                        ut.setdefault("bc_tabeller", {})[tab] = rows[:500]
                    except Exception as e:
                        ut.setdefault("bc_tabeller", {})[tab] = str(e)
except Exception as e:
    ut["bc_fel"] = str(e)
# Reddit via redlib-speglar
for inst in ["https://safereddit.com", "https://redlib.catsarch.com", "https://l.opnxng.com", "https://redlib.perennialte.ch", "https://rl.bloat.cat", "https://lr.eu.psf.lt"]:
    try:
        b = get(inst + "/r/FlippingUK/search?q=vinted&restrict_sr=on&sort=top&t=all")
        tit = re.findall(r'<h2 class="post_title">.*?<a href="([^"]+)">([^<]+)</a>', b, re.S)
        ut.setdefault("redlib", {})[inst] = tit[:5] or b[:300]
        if tit:
            ut["redlib_ok"] = inst
            break
    except Exception as e:
        ut.setdefault("redlib", {})[inst] = str(e)
if ut.get("redlib_ok"):
    inst = ut["redlib_ok"]; poster = {}
    for sub, q in [("FlippingUK", "vinted"), ("Flipping", "vinted"), ("vinted", "flip"), ("vinted", "resell"), ("FlippingUK", "brands"), ("FlippingUK", "best"), ("Flipping", "menswear"), ("Flipping", "arcteryx"), ("Flipping", "barbour"), ("Flipping", "ralph lauren")]:
        try:
            b = get(inst + "/r/%s/search?%s" % (sub, urllib.parse.urlencode({"q": q, "restrict_sr": "on", "sort": "top", "t": "all"})))
            for href, t in re.findall(r'<h2 class="post_title">.*?<a href="([^"]+)">([^<]+)</a>', b, re.S)[:12]:
                poster[href] = (sub, q, H.unescape(t.strip()))
            time.sleep(1.5)
        except Exception as e:
            print("redlib fel", e)
    ut["reddit_poster"] = list(poster.items())
    tradar = {}
    for href, _ in list(poster.items())[:45]:
        try:
            b = get(inst + href + "?sort=top")
            kom = re.findall(r'<div class="comment_body[^"]*"[^>]*>(.*?)</div>', b, re.S)
            op = re.search(r'<div class="post_body[^"]*">(.*?)</div>', b, re.S)
            tradar[href] = {"op": re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", op.group(1))))[:1500] if op else "",
                            "kom": [re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", k)))[:600] for k in kom[:25]]}
            time.sleep(1.5)
        except Exception as e:
            tradar[href] = str(e)
    ut["reddit_tradar"] = tradar
with open("research/runda3.json", "w", encoding="utf-8") as f:
    json.dump(ut, f, ensure_ascii=False, indent=1)
