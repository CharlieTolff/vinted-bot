import json, sys, time, collections
sys.path.insert(0, ".")
import vinted_bot as vb
L = json.load(open("sokningar.json", encoding="utf-8"))[-4:]
v = vb.Vinted()
minne = {"marken": {}}
for s in L:
    ids = vb.hitta_marke_ids(v, s, minne)
    alla = []
    for ord_ in (vb.lista(s.get("sokord")) or [""]):
        alla += vb.annonser_fran_sida(v.hamta(vb.sok_url(s, ids, ord_)))
        time.sleep(1.5)
    tr = [a for a in alla if vb.matchar(a, s)]
    print("ALARM", s["namn"], "ids", ids, "sökträffar", len(alla), "matchar", len(tr))
    for a in tr[:12]:
        print("     ", a["pris"], a["titel"][:55], "|", a["marke"], a["storlek"], a["skick"])
    time.sleep(2)
# rerun
