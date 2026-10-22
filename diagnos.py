"""Felsökning av Märkesbörsen: skriver ut hur mätningarna ser ut i loggen, så att de går att granska.

Körs för hand från Actions (Diagnos av börsen). Ändrar inget i den sparade historiken, eftersom Diagnos
aldrig sparar något tillbaka.

  python3 diagnos.py           sammanfattning av det sparade
  python3 diagnos.py --dump    dessutom bors.json packad i loggen (för att prova hemsidan med riktiga data)
  python3 diagnos.py --tradera hur Traderas aktiva annonser delas upp och hur länge sålda legat ute
"""
import base64
import gzip
import json
import sys
from collections import Counter

import marknad as mk
import vinted_bot as vb


def rubrik(t):
    print("\n===== %s =====" % t, flush=True)


def sparat():
    bors = vb.las_json(mk.BORS_FIL, {})
    rubrik("SPARAT")
    print("version", bors.get("version"), "uppdaterad", bors.get("uppdaterad"), "kö", bors.get("ko"))
    print("kategorier", [k["id"] for k in bors.get("kategorier", [])])
    print("alarm-märken", sorted(bors.get("alarm", {})))
    print("tradera_bakat", bors.get("tradera_bakat"))
    print("tradera_forsta", bors.get("tradera_forsta"))
    print("tradera_kategorier", bors.get("tradera_kategorier"))
    print("vinted_marke_ids", bors.get("vinted_marke_ids"))
    for kat, k in ((bors.get("marknad") or {}).get("kategorier") or {}).items():
        print("\n%s: sålda %s (förra %s), osålda %s, utan märke %s, median %s kr, %s dagar, ute %s, från %s/%s, vinted %s (%s)" % (
            kat, k["s"], k["sf"], k["o"], k["u"], k["p"], k["d"], k["ute"], k["fran"], k["fran_o"], k["vn"], k["vd"]))
        for r in k["marken"][:25]:
            print("   ", json.dumps(r, ensure_ascii=False))
    affarer = vb.las_json(mk.AFFAR_FIL, {})
    for kat, poster in affarer.items():
        if kat.startswith("_"):
            continue
        salda = [p for p in poster.values() if p[5]]
        med_attr = sum(1 for p in salda if p[6])
        print("affärer %s: %d sålda (%d med märke), %d osålda, %s..%s" % (
            kat, len(salda), med_attr, len(poster) - len(salda),
            min((p[0] for p in poster.values()), default=""), max((p[0] for p in poster.values()), default="")))
    for kat, pts in (affarer.get("_ute_hist") or {}).items():
        for d, tot, sett, per in pts[-3:]:
            print("aktiva %s %s: %d i kategorin, %d genomgångna, största: %s" % (kat, d, tot, sett, Counter(per).most_common(12)))
    for kat, till in (affarer.get("_ute") or {}).items():
        print("aktiva pågår %s: sökning %s av %d, %d annonser" % (kat, till.get("i"), len(till.get("delar") or []), len(till.get("ids") or {})))
    for kat, mm in ((bors.get("marke") or {}).get("tradera") or {}).items():
        print("märken tradera %s: %d, t.ex. %s" % (kat, len(mm), [(m, pts[-1]) for m, pts in list(mm.items())[:5]]))
    return bors


def tradera_aktiva():
    """Hur Traderas aktiva annonser kan delas upp under 10 000 (sidtaket), om det finns märkesfilter, och hur
    länge sålda annonser legat ute (för att se om 35 dagar bakåt räcker)."""
    import random, time
    from collections import Counter
    rubrik("TRADERA AKTIVA 2")
    t = mk.TraderaKalla({})
    def tot(namn, par):
        try:
            res = t.sok(par)
        except Exception as e:
            print(namn, "fel", e); return None
        print("%s: total=%s" % (namn, res.get("totalItemCount")), flush=True)
        time.sleep(random.uniform(1, 2))
        return res
    res = tot("1639", [("categoryId", 1639)])
    if res:
        f = res.get("filters") or {}
        for grupp, lista in f.items():
            if not isinstance(lista, list):
                print("filter", grupp, json.dumps(lista, ensure_ascii=False)[:300]); continue
            for x in lista:
                if isinstance(x, dict):
                    print("filter %s %s typ=%s: %s" % (grupp, x.get("parameter"), x.get("type"),
                          json.dumps(x.get("options") or x, ensure_ascii=False)[:700]))
    for cid in (1639, 340327):
        for s in ("Private", "Company"):
            tot("%d %s" % (cid, s), [("categoryId", cid), ("sellerType", s)])
            for it in ("Auction", "FixedPrice", "ContactOnly"):
                tot("%d %s %s" % (cid, s, it), [("categoryId", cid), ("sellerType", s), ("itemType", it)])
    for par in ([("brand", "Hugo Boss")], [("brands", "Hugo Boss")], [("attr_brand", "Hugo Boss")], [("q", "boss")]):
        tot("1639 %s" % par, [("categoryId", 1639)] + par)
    rubrik("SÅLDA: DAGAR UTE")
    affarer = vb.las_json(mk.AFFAR_FIL, {})
    grans = mk.dagstr(time.time() - 30 * 86400)
    for kat, poster in affarer.items():
        d = [(mk.tid(p[0]) - mk.tid(p[1])) // 86400 for p in poster.values() if p[5] and p[1] and p[0] > grans]
        if not d:
            continue
        d.sort()
        n = len(d)
        print("%s: %d sålda senaste 30 d, median %d dagar ute, >14: %.1f%%, >35: %.1f%%, >60: %.1f%%, max %d" % (
            kat, n, d[n // 2], 100 * sum(x > 14 for x in d) / n, 100 * sum(x > 35 for x in d) / n,
            100 * sum(x > 60 for x in d) / n, d[-1]))
        print("   start", min(p[1] for p in poster.values() if p[1]), "slut", min(p[0] for p in poster.values()))


def dump():
    """bors.json gzippad och base64 i loggen, i rader om 2000 tecken."""
    rubrik("DUMP")
    with open(mk.BORS_FIL, "rb") as f:
        data = base64.b64encode(gzip.compress(f.read())).decode()
    for i in range(0, len(data), 2000):
        print("DUMP " + data[i:i + 2000])
    print("DUMP-SLUT")


def main():
    if "--tradera" in sys.argv:
        tradera_aktiva()
        return
    sparat()
    if "--dump" in sys.argv:
        dump()


if __name__ == "__main__":
    main()
