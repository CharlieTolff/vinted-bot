"""Felsökning av Märkesbörsen: skriver ut hur mätningarna ser ut i loggen, så att de går att granska.

Körs för hand från Actions (Diagnos av börsen). Ändrar inget i den sparade historiken, eftersom Diagnos
aldrig sparar något tillbaka.

  python3 diagnos.py           sammanfattning av det sparade
  python3 diagnos.py --dump    dessutom bors.json packad i loggen (för att prova hemsidan med riktiga data)
"""
import base64
import gzip
import json
import sys

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
        salda = [p for p in poster.values() if p[5]]
        med_attr = sum(1 for p in salda if p[6])
        print("affärer %s: %d sålda (%d med märke), %d osålda, %s..%s" % (
            kat, len(salda), med_attr, len(poster) - len(salda),
            min((p[0] for p in poster.values()), default=""), max((p[0] for p in poster.values()), default="")))
    return bors


def tradera_aktiva():
    """Hur Traderas aktiva annonser kan hämtas: fält, sortering, hur långt sidorna räcker och underkategorier."""
    import random, time
    rubrik("TRADERA AKTIVA")
    t = mk.TraderaKalla({})
    def visa(namn, par):
        try:
            res = t.sok(par)
        except Exception as e:
            print(namn, "fel", e); return None
        it = res.get("items") or []
        print("%s: total=%s n=%d forsta=%s" % (namn, res.get("totalItemCount"), len(it),
              [(x.get("startDate", "")[:10], x.get("endDate", "")[:10], x.get("price"), x.get("itemType")) for x in it[:3]]))
        time.sleep(random.uniform(1, 2))
        return res
    res = visa("1639 utan status", [("categoryId", 1639)])
    if res:
        print("nycklar:", sorted(res.keys()))
        for k, v in res.items():
            if isinstance(v, (list, dict)) and k != "items":
                print("  %s: %s" % (k, json.dumps(v, ensure_ascii=False)[:1500]))
        if res.get("items"):
            print("annons:", json.dumps(res["items"][0], ensure_ascii=False)[:1500])
    visa("1639 Active", [("categoryId", 1639), ("itemStatus", "Active")])
    for sort in ["AddedOn", "AddedOnAsc", "AddedOnDesc", "AddedOnAscending", "EndDate", "EndDateAscending", "PriceAscending", "PriceDescending", "Relevance"]:
        visa("343837 sortBy=" + sort, [("categoryId", 343837), ("sortBy", sort)])
    for sida in (100, 125, 126, 140):
        visa("1639 sida %d" % sida, [("categoryId", 1639), ("sortBy", "AddedOn"), ("paging", sida)])
    for cid in (1000678, 1000675, 1000696, 1000695, 344184, 340327, 340304, 1000656, 343837):
        visa("kategori %d" % cid, [("categoryId", cid)])


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
