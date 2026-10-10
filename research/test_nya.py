import json, sys, time, collections
sys.path.insert(0, ".")
import vinted_bot as vb
L = json.load(open("sokningar.json", encoding="utf-8"))[-10:]
v = vb.Vinted()
minne = {"marken": {}}
for s in L:
    ids = vb.hitta_marke_ids(v, s, minne)
    titlar = {}
    for m in vb.lista(s.get("marke")):
        b = v.api("/api/v2/brands?" + vb.urllib.parse.urlencode({"keyword": m})).get("brands") or []
        titlar[m] = [(x.get("id"), x.get("title")) for x in b[:4]]
    alla = []
    for ord_ in (vb.lista(s.get("sokord")) or [""]):
        alla += vb.annonser_fran_sida(v.hamta(vb.sok_url(s, ids, ord_)))
        time.sleep(1.5)
    tr = [a for a in alla if vb.matchar(a, s)]
    print("ALARM", s["namn"], "ids", ids, titlar)
    print("   sökträffar", len(alla), "matchar", len(tr), "märken i träffar", collections.Counter(a["marke"] for a in alla).most_common(4))
    for a in tr[:8]:
        print("     ", a["pris"], a["titel"][:50], "|", a["marke"], a["storlek"], a["skick"])
    time.sleep(2)
