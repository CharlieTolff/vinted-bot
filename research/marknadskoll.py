"""Hämtar riktiga marknadsdata för research: Vinted (begärda priser, gillningar, utbud)
och Tradera (faktiska slutpriser på sålda annonser + andel sålda). Skriver research/resultat.json."""
import json, random, re, statistics, sys, time, urllib.parse, urllib.request
sys.path.insert(0, ".")
import vinted_bot as vb
from research.kandidater import K

def q(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(len(xs) * p))]) if xs else None

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": vb.WEBBLASARE, "Accept": "text/html", "Accept-Language": "sv-SE,sv;q=0.9"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def vinted_sida(v, url):
    sida = v.hamta(url)
    text = vb.sidans_data(sida)
    m = re.search(r'"pagination":(\{[^{}]*\})', text)
    pag = json.loads(m.group(1)) if m else {}
    return vb.annonser_fran_sida(sida), pag.get("total_entries")

def kolla_vinted(v, minne, sokord, marken, kat):
    s = {"sokord": sokord, "kon": "herr" if kat else "", "kategorier": [kat] if kat else []}
    ids = []
    for m in marken:
        if m.lower() not in minne:
            try:
                minne[m.lower()] = v.marke_id(m)
            except Exception as e:
                minne[m.lower()] = None
            time.sleep(1)
        if minne[m.lower()]:
            ids.append(minne[m.lower()])
    if marken and not ids:
        return {"fel": "märket hittades inte"}
    bas = vb.sok_url(s, ids, sokord)
    relevans = [(k, val) for k, val in urllib.parse.parse_qsl(urllib.parse.urlsplit(bas).query, keep_blank_values=True) if k != "order"]
    annonser, totalt = [], None
    for sidnr in (1, 2):
        u = vb.VINTED + "/catalog?" + urllib.parse.urlencode(relevans + [("page", sidnr)])
        a, t = vinted_sida(v, u)
        annonser += a
        totalt = totalt or t
        time.sleep(random.uniform(1.5, 3))
    nya, _ = vinted_sida(v, bas)
    time.sleep(random.uniform(1.5, 3))
    priser = [a["pris"] for a in annonser]
    med = q(priser, 0.5)
    gill = [a["gillas"] for a in annonser]
    return {
        "url": bas, "utbud_totalt": totalt, "antal_i_urval": len(annonser),
        "pris_p10": q(priser, 0.1), "pris_p25": q(priser, 0.25), "pris_median": med, "pris_p75": q(priser, 0.75),
        "gillas_median": q(gill, 0.5), "gillas_p75": q(gill, 0.75),
        "nya_96": len(nya), "nya_under_40pct": sum(1 for a in nya if med and a["pris"] <= 0.4 * med),
        "nya_billigaste": sorted([(a["pris"], a["titel"][:50], a["marke"]) for a in nya])[:6],
        "nya_id_spann": [min(a["id"] for a in nya), max(a["id"] for a in nya)] if nya else None,
    }

def tradera(sokord, status):
    u = "https://www.tradera.com/search?" + urllib.parse.urlencode({"q": sokord, "itemStatus": status})
    text = vb.sidans_data(get(u))
    i = text.find('"discover/receiveSearchResults"')
    if i < 0:
        return None
    j = text.find('"result":', i)
    res, _ = json.JSONDecoder().raw_decode(text, j + len('"result":'))
    return res

def kolla_tradera(sokord):
    sold = tradera(sokord, "Sold"); time.sleep(random.uniform(1, 2))
    unsold = tradera(sokord, "Unsold"); time.sleep(random.uniform(1, 2))
    if not sold:
        return {"fel": "inga data"}
    items = sold.get("items") or []
    priser = [it["price"] for it in items if it.get("price")]
    ns, nu = sold.get("totalItemCount") or 0, (unsold or {}).get("totalItemCount") or 0
    return {
        "salda_totalt": ns, "osalda_totalt": nu,
        "saljgrad": round(ns / (ns + nu), 2) if ns + nu else None,
        "antal_priser": len(priser), "slutpris_p25": q(priser, 0.25), "slutpris_median": q(priser, 0.5), "slutpris_p75": q(priser, 0.75),
        "exempel": [(it.get("price"), it.get("shortDescription", "")[:60], (it.get("endDate") or "")[:10], it.get("totalBids")) for it in items[:12]],
        "datum_spann": [min((it.get("endDate") or "")[:10] for it in items), max((it.get("endDate") or "")[:10] for it in items)] if items else None,
    }

def main():
    v = vb.Vinted()
    minne, ut = {}, {}
    for namn, sokord, marken, kat, tq in K:
        rad = {}
        try:
            rad["vinted"] = kolla_vinted(v, minne, sokord, marken, kat)
        except Exception as e:
            rad["vinted"] = {"fel": str(e)}
            v = vb.Vinted(); time.sleep(20)
        try:
            rad["tradera"] = kolla_tradera(tq)
        except Exception as e:
            rad["tradera"] = {"fel": str(e)}
        ut[namn] = rad
        print(namn, json.dumps({k: {kk: vv for kk, vv in d.items() if kk in ("pris_median", "gillas_median", "utbud_totalt", "slutpris_median", "saljgrad", "fel")} for k, d in rad.items()}, ensure_ascii=False), flush=True)
    ut["_marken"] = minne
    ut["_tid"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    with open("research/resultat.json", "w", encoding="utf-8") as f:
        json.dump(ut, f, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
