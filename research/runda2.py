"""Runda 2: renare Tradera-slutpriser (titel måste innehålla rätt ord), hur ofta det kommer nya annonser på Vinted,
Flashback-trådar och BareliCloset."""
import json, random, re, sys, time, urllib.parse, urllib.request, html as H
sys.path.insert(0, ".")
import vinted_bot as vb
from research.marknadskoll import q, get, tradera

# namn: (tradera-sökord, ord som MÅSTE finnas i titeln (alla grupper, något ord per grupp), vinted-alarm (sokord, märken, kategori))
R = {
 "Barbour vaxjacka": (["barbour vaxjacka", "barbour bedale", "barbour beaufort", "barbour border", "barbour ashby", "barbour transport"], [["barbour"], ["vax", "wax", "bedale", "beaufort", "border", "ashby", "transport", "northumbria", "spey"]], ("", ["Barbour"], "klader")),
 "Barbour quilt": (["barbour quiltad", "barbour liddesdale", "barbour powell"], [["barbour"], ["quilt", "liddesdale", "powell", "heritage liddesdale"]], ("quilt", ["Barbour"], "klader")),
 "Arc'teryx jacka": (["arcteryx jacka", "arc'teryx jacka", "arcteryx beta", "arcteryx atom", "arcteryx alpha", "arcteryx gamma"], [["arc"], ["jack", "beta", "atom", "alpha", "gamma", "squamish", "zeta", "cerium", "shell", "hoody", "hoodie"]], ("jacka", ["Arc'teryx"], "klader")),
 "Fjällräven Greenland jacka": (["fjällräven greenland jacka", "fjällräven greenland"], [["fjällräven", "fjallraven"], ["jack", "parka"]], ("greenland", ["Fjällräven"], "klader")),
 "Fjällräven Keb/Vidda byxor": (["fjällräven keb byxor", "fjällräven vidda pro", "fjällräven barents"], [["fjällräven", "fjallraven"], ["byx", "trouser", "pant"]], ("byxor", ["Fjällräven"], "klader")),
 "Fjällräven Kånken": (["kånken"], [["kånken", "kanken"]], ("kånken", ["Fjällräven"], "")),
 "Woolpower": (["woolpower"], [["woolpower"], ["tröja", "zip", "jacka", "väst", "400", "600", "200", "underst", "fleece"]], ("", ["Woolpower"], "klader")),
 "Hermès slips": (["hermes slips", "hermès slips"], [["herm"], ["slips", "tie"]], ("slips", ["Hermès"], "accessoarer")),
 "Paraboot": (["paraboot"], [["paraboot"]], ("", ["Paraboot"], "skor")),
 "Church's": (["church's skor", "churchs skor", "church's loafers"], [["church"], ["sko", "loafer", "oxford", "brogue", "derby", "boot", "chetwynd", "consul", "shannon", "pembrey"]], ("", ["Church's"], "skor")),
 "Loro Piana": (["loro piana"], [["loro piana"]], ("", ["Loro Piana"], "klader")),
 "Brunello Cucinelli": (["brunello cucinelli"], [["cucinelli"]], ("", ["Brunello Cucinelli"], "klader")),
 "Moncler jacka": (["moncler jacka", "moncler dunjacka", "moncler väst"], [["moncler"], ["jack", "dun", "väst", "vest", "parka"]], ("", ["Moncler"], "klader")),
 "Canada Goose": (["canada goose jacka", "canada goose parka"], [["canada goose"], ["jack", "parka", "dun", "väst", "vest", "bomber"]], ("", ["Canada Goose"], "klader")),
 "RL kabelstickat": (["ralph lauren kabelstickad", "ralph lauren cable knit"], [["ralph", "polo"], ["kabel", "cable"]], ("kabelstickad", ["Ralph Lauren", "Polo Ralph Lauren"], "klader")),
 "RL half zip": (["ralph lauren half zip", "ralph lauren quarter zip"], [["ralph", "polo"], ["half", "quarter", "kvarts", "halv"]], ("half zip", ["Ralph Lauren", "Polo Ralph Lauren"], "klader")),
 "RL Harrington/jacka": (["ralph lauren harrington", "polo ralph lauren jacka herr"], [["ralph", "polo"], ["harrington", "jacka", "jacket"]], ("jacka", ["Ralph Lauren", "Polo Ralph Lauren"], "klader")),
 "RL skjorta": (["ralph lauren skjorta herr"], [["ralph", "polo"], ["skjorta", "shirt", "oxford"]], ("skjorta", ["Ralph Lauren", "Polo Ralph Lauren"], "klader")),
 "Stone Island": (["stone island"], [["stone island"]], ("", ["Stone Island"], "klader")),
 "Stone Island ytterplagg": (["stone island jacka", "stone island overshirt"], [["stone island"], ["jack", "overshirt", "skjortjacka", "dun", "parka"]], ("jacka", ["Stone Island"], "klader")),
 "CP Company": (["cp company", "c.p. company"], [["cp company", "c.p. company", "c.p company"]], ("", ["C.P. Company"], "klader")),
 "Carhartt Detroit": (["carhartt detroit"], [["carhartt"], ["detroit"]], ("detroit", ["Carhartt", "Carhartt WIP"], "klader")),
 "Carhartt Active/Michigan": (["carhartt active jacket", "carhartt michigan"], [["carhartt"], ["active", "michigan", "chore"]], ("active", ["Carhartt", "Carhartt WIP"], "klader")),
 "Patagonia fleece": (["patagonia fleece", "patagonia retro-x", "patagonia synchilla"], [["patagonia"], ["fleece", "retro", "synchilla", "snap"]], ("fleece", ["Patagonia"], "klader")),
 "Our Legacy": (["our legacy"], [["our legacy"]], ("", ["Our Legacy"], "klader")),
 "TNF Nuptse": (["north face nuptse"], [["nuptse"]], ("nuptse", ["The North Face"], "klader")),
 "Salomon XT-6": (["salomon xt-6"], [["salomon"], ["xt-6", "xt6", "xt 6"]], ("xt-6", ["Salomon"], "skor")),
 "Hestra handskar": (["hestra"], [["hestra"]], ("", ["Hestra"], "accessoarer")),
 "Acne Studios": (["acne studios"], [["acne"]], ("", ["Acne Studios"], "klader")),
 "Houdini": (["houdini power houdi", "houdini jacka"], [["houdini"]], ("", ["Houdini"], "klader")),
 "Haglöfs": (["haglöfs jacka", "haglöfs"], [["haglöfs", "haglofs"]], ("jacka", ["Haglöfs"], "klader")),
 "Peak Performance": (["peak performance jacka"], [["peak performance"], ["jack", "parka", "dun", "väst"]], ("jacka", ["Peak Performance"], "klader")),
 "Herno": (["herno jacka", "herno dunjacka", "herno väst"], [["herno"], ["jack", "dun", "väst", "parka", "rock", "kappa"]], ("", ["Herno"], "klader")),
 "Levi's 501 vintage": (["levis 501 vintage", "levis 501 made in usa"], [["501"], ["vintage", "usa", "big e", "80", "90"]], ("501 vintage", ["Levi's"], "klader")),
 "Lacoste": (["lacoste herr"], [["lacoste"]], ("", ["Lacoste"], "klader")),
 "LV plånbok": (["louis vuitton plånbok"], [["louis vuitton", "lv"], ["plånbok", "wallet", "korthållare", "card"]], ("plånbok", ["Louis Vuitton"], "accessoarer")),
 "Birkenstock Boston": (["birkenstock boston"], [["boston"]], ("boston", ["Birkenstock"], "skor")),
 "Dr Martens": (["dr martens"], [["martens"]], ("", ["Dr. Martens"], "skor")),
 "Tiger of Sweden kavaj": (["tiger of sweden kavaj"], [["tiger"], ["kavaj", "blazer"]], ("kavaj", ["Tiger of Sweden"], "klader")),
 "Oscar Jacobson kavaj": (["oscar jacobson kavaj"], [["jacobson"], ["kavaj", "blazer"]], ("kavaj", ["Oscar Jacobson"], "klader")),
 "Morris": (["morris herr", "morris stickad"], [["morris"]], ("", ["Morris"], "klader")),
 "Nudie jeans": (["nudie jeans"], [["nudie"]], ("", ["Nudie Jeans"], "klader")),
 "Stenströms skjorta": (["stenströms skjorta"], [["stenström"]], ("skjorta", ["Stenströms"], "klader")),
}

def ok_titel(t, grupper):
    t = t.lower()
    return all(any(o in t for o in g) for g in grupper)

def tradera_sida(sokord, status, sida):
    u = "https://www.tradera.com/search?" + urllib.parse.urlencode({"q": sokord, "itemStatus": status, "paging": sida} if sida > 1 else {"q": sokord, "itemStatus": status})
    text = vb.sidans_data(get(u))
    i = text.find('"discover/receiveSearchResults"')
    if i < 0:
        return []
    j = text.find('"result":', i)
    res, _ = json.JSONDecoder().raw_decode(text, j + len('"result":'))
    return res.get("items") or []

def senaste_id(v):
    a = vb.annonser_fran_sida(v.hamta(vb.VINTED + "/catalog?order=newest_first"))
    return max(x["id"] for x in a)

def main():
    v = vb.Vinted()
    t0, id0 = time.time(), senaste_id(v)
    ut = {"_start": [t0, id0]}
    minne = {}
    for namn, (tq, grupper, (vs, vm, vk)) in R.items():
        rad = {}
        salda, osalda = {}, {}
        for sokord in tq:
            for sida in (1, 2, 3):
                try:
                    its = tradera_sida(sokord, "Sold", sida)
                except Exception as e:
                    print("tradera fel", namn, e); its = []
                for it in its:
                    if ok_titel(it.get("shortDescription", ""), grupper):
                        salda[it["itemId"]] = it
                time.sleep(random.uniform(0.8, 1.6))
                if len(its) < 40:
                    break
            try:
                for it in tradera_sida(sokord, "Unsold", 1):
                    if ok_titel(it.get("shortDescription", ""), grupper):
                        osalda[it["itemId"]] = it
            except Exception as e:
                print("tradera fel", e)
            time.sleep(random.uniform(0.8, 1.6))
        pr = [it["price"] for it in salda.values() if it.get("price")]
        datum = sorted((it.get("endDate") or "")[:10] for it in salda.values())
        rad["tradera"] = {"antal_salda": len(pr), "p10": q(pr, .1), "p25": q(pr, .25), "median": q(pr, .5), "p75": q(pr, .75), "p90": q(pr, .9),
                          "datum": [datum[0], datum[-1]] if datum else None,
                          "osalda_i_urval": len(osalda), "osalda_median": q([it["price"] for it in osalda.values() if it.get("price")], .5),
                          "exempel": sorted([(it["price"], it.get("shortDescription", "")[:50], (it.get("endDate") or "")[:10]) for it in salda.values()], key=lambda x: -x[0])[::max(1, len(pr) // 15)][:15]}
        # Vinted: nyaste annonserna i alarmets form -> hur många nya per dygn + vad de nya kostar
        try:
            ids = []
            for m in vm:
                if m.lower() not in minne:
                    minne[m.lower()] = v.marke_id(m); time.sleep(1)
                if minne[m.lower()]:
                    ids.append(minne[m.lower()])
            s = {"sokord": vs, "kon": "herr" if vk else "", "kategorier": [vk] if vk else [], "lander": ["SE", "DK", "FI", "PL"]}
            nya = vb.annonser_fran_sida(v.hamta(vb.sok_url(s, ids, vs)))
            rad["vinted"] = {"nya": len(nya), "id_min": min(a["id"] for a in nya) if nya else None, "id_max": max(a["id"] for a in nya) if nya else None,
                             "nya_pris_p10": q([a["pris"] for a in nya], .1), "nya_pris_p25": q([a["pris"] for a in nya], .25), "nya_pris_median": q([a["pris"] for a in nya], .5),
                             "nya_lista": sorted([(a["pris"], a["titel"][:40], a["skick"], a["storlek"]) for a in nya])[:25]}
        except Exception as e:
            rad["vinted"] = {"fel": str(e)}
            v = vb.Vinted(); time.sleep(15)
        time.sleep(random.uniform(1.5, 3))
        ut[namn] = rad
        print(namn, rad["tradera"]["antal_salda"], rad["tradera"]["median"], rad.get("vinted", {}).get("nya"), flush=True)
    ut["_slut"] = [time.time(), senaste_id(v)]
    # Flashback-trådar
    fb = {}
    for t in ["/t3584842", "/t3707442", "/t3729350"]:
        for sida in ("", "p2", "p3"):
            try:
                b = get("https://www.flashback.org" + t + sida)
                inl = re.findall(r'<div class="post_message"[^>]*>(.*?)</div>', b, re.S)
                fb.setdefault(t, []).extend(re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", x))).strip()[:1200] for x in inl)
            except Exception as e:
                print("fb fel", t, e); break
            time.sleep(1.5)
    for ord_ in ["vinted vinst", "säljer vidare kläder", "reselling kläder", "flippa kläder", "köpa billigt sälja dyrt kläder"]:
        try:
            b = get("https://www.flashback.org/sok/?" + urllib.parse.urlencode({"query": ord_}))
            fb["sok:" + ord_] = re.findall(r'href="(/t\d+)"[^>]*>\s*([^<]{5,200})<', b)[:30]
        except Exception as e:
            print("fb sök fel", e)
        time.sleep(1.5)
    ut["_flashback"] = fb
    # Reddit via arkiv
    rd = []
    for sub, ord_ in [("Flipping", "vinted"), ("FlippingUK", "vinted"), ("vinted", "flip"), ("vinted", "resell"), ("Flipping", "arcteryx"), ("Flipping", "barbour"), ("FlippingUK", "brands"), ("Flipping", "ralph lauren")]:
        for u in ["https://arctic-shift.photon-reddit.com/api/posts/search?" + urllib.parse.urlencode({"subreddit": sub, "title": ord_, "limit": 50}),
                  "https://arctic-shift.photon-reddit.com/api/posts/search?" + urllib.parse.urlencode({"subreddit": sub, "selftext": ord_, "limit": 50})]:
            try:
                req = urllib.request.Request(u, headers={"User-Agent": "research-script/0.2"})
                with urllib.request.urlopen(req, timeout=40) as r:
                    d = json.load(r)
                for p in d.get("data") or []:
                    rd.append({"sub": sub, "titel": p.get("title"), "text": (p.get("selftext") or "")[:1200], "poang": p.get("score"), "n": p.get("num_comments"), "id": p.get("id")})
                print("reddit", sub, ord_, len(d.get("data") or []), d.get("error"))
            except Exception as e:
                print("reddit fel", sub, ord_, e, getattr(e, "read", lambda: b"")()[:300])
            time.sleep(1)
    kom = {}
    for p in sorted({p["id"]: p for p in rd}.values(), key=lambda p: -(p["n"] or 0))[:30]:
        try:
            req = urllib.request.Request("https://arctic-shift.photon-reddit.com/api/comments/search?" + urllib.parse.urlencode({"link_id": p["id"], "limit": 100}), headers={"User-Agent": "research-script/0.2"})
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.load(r)
            kom[p["id"]] = [(c.get("score"), (c.get("body") or "")[:600]) for c in sorted(d.get("data") or [], key=lambda c: -(c.get("score") or 0))[:20]]
        except Exception as e:
            print("kom fel", e)
        time.sleep(1)
    ut["_reddit"] = {"poster": rd, "kommentarer": kom}
    # BareliCloset
    bc = {}
    for namn, u in [("plick", "https://plick.se/profiler/barelicloset"), ("se", "https://barelicloset.se/"),
                    ("wayback", "https://web.archive.org/web/2025/https://barelicloset.se/"), ("wayback_shop", "https://web.archive.org/web/2025/https://barelicloset.se/shop")]:
        try:
            b = get(u)
            bc[namn + "_lankar"] = list(dict.fromkeys(re.findall(r'href="([^"]+)"[^>]*>\s*([^<]{3,120})<', b)))[:200]
            body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", b, flags=re.S)
            bc[namn + "_text"] = re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", body)))[-8000:]
            bc[namn + "_alt"] = re.findall(r'alt="([^"]{3,120})"', b)[:150]
        except Exception as e:
            bc[namn] = str(e)
    ut["_bareli"] = bc
    with open("research/runda2.json", "w", encoding="utf-8") as f:
        json.dump(ut, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
