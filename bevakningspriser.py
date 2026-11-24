"""Plockar ut det senaste mittenpriset per märke och kategori ur bors.json, till låsets bevakningar.

Låset (betalning/worker.js) jämför varje morgon med det här och mejlar den som bevakar ett märke när
priset ändrats mycket. Filen är liten så att låset hinner läsa den. Användning:
    python3 bevakningspriser.py bors.json priser.json
"""
import json
import sys


def priser(B):
    ut = {}
    for kat, marken in ((B.get("marke") or {}).get("tradera") or {}).items():
        for m, punkter in (marken or {}).items():
            if not punkter:
                continue
            d, n30, median, *rest = punkter[-1]
            per_vecka = rest[2] if len(rest) > 2 and rest[2] is not None else 0
            if median and n30 and n30 >= 3:
                ut.setdefault(kat, {})[m] = [round(median), n30, round(per_vecka, 1)]
    return {"d": B.get("uppdaterad"), "kat": {k["id"]: k["namn"] for k in B.get("kategorier") or []}, "p": ut}


if __name__ == "__main__":
    B = json.load(open(sys.argv[1], encoding="utf-8"))
    json.dump(priser(B), open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
