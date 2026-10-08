# Tillfälligt testskript: uppskattat säljpris för Charlies alarm.
import json, sys
sys.path.insert(0, ".")
import vinted_bot as vb
v = vb.Vinted()
minne = {"marken": {}, "marknad": {}}
for s in json.load(open("sokningar.json")):
    namn = vb.alarm_namn(s)
    ids = vb.hitta_marke_ids(v, s, minne)
    m = vb.kolla_marknad(v, s, ids, minne, namn)
    hittade = {}
    for u in m["url"].split("\n"):
        for a in v.sok(u):
            if vb.matchar(a, {k: x for k, x in s.items() if k not in ("maxpris", "minpris")}): hittade[a["id"]] = a
    pr = sorted(a["pris"] for a in hittade.values())
    print("==", namn, "| ditt säljpris:", s.get("saljpris"), "| uppskattat:", m["pris"], "| antal:", m["antal"], "| gillas median:", m["gillas"], "->", vb.efterfragan(m["gillas"]))
    print("   priser p10/p25/p40/p50/p75:", [vb.percentil(pr, q) for q in (.1, .25, .4, .5, .75)])
    print("   exempel:", [(a["titel"][:30], a["pris"], a["skick"], a["gillas"]) for a in list(hittade.values())[:6]])
