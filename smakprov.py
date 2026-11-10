"""Smakprovet: det lilla ur bors.json som de öppna sidorna (väntelistan och börsens startsida) visar.

Hela bors.json ligger bakom låset hos Cloudflare. Hit kommer bara det som syns gratis: hur mycket som mäts,
vilka märken som ökat mest, de fem dyraste som säljer, de fem mest sålda och ett exempel till vinstkalkylen.

Körs när hemsidan byggs (bevaka.yml): python3 smakprov.py bors.json _site/smakprov.json
"""
import json
import sys

INTE = {"övriga", "vintage", "okänt", "no brand", "handgjord", "diverse"}  # samma som på sidorna
VECKOR = 6       # veckor med märken kvar (trenderna räknas på den senaste månaden)
TOPP = 5
INKOP = 199      # vinstexemplet på startsidan


def ok(m):
    return m.lower() not in INTE


def smakprov(B):
    kats = B.get("kategorier") or []
    andel = B.get("andel") or {}
    ut = {"kategorier": kats, "uppdaterad": B.get("uppdaterad")}

    marken, annonser = set(), 0
    for per in andel.values():
        for k in kats:
            pts = per.get(k["id"]) or []
            if pts:
                annonser += pts[-1][1]
                marken.update(pts[-1][2])
    ut["antal"] = {"annonser": annonser, "marken": len(marken)}

    # Dyrast som säljer: bara de fem som visas, inte alla märkens priser.
    dyra = []
    for k in kats:
        pts = (andel.get("tradera") or {}).get(k["id"]) or []
        if pts:
            dyra += [(v[1], m, k["id"]) for m, v in pts[-1][2].items() if v[0] >= 3 and v[1] and ok(m)]
    valda, sett = {}, set()
    for _, m, kat in sorted(dyra, reverse=True):
        if m in sett:
            continue
        sett.add(m)
        valda.setdefault(kat, set()).add(m)
        if len(sett) >= TOPP:
            break
    ut["andel"] = {"tradera": {}}
    for k in kats:
        pts = (andel.get("tradera") or {}).get(k["id"]) or []
        if pts:
            d, n, m, *_ = pts[-1]
            ut["andel"]["tradera"][k["id"]] = [[d, n, {x: v for x, v in m.items() if x in valda.get(k["id"], ())}]]

    # Veckorna: antal sålda för alla veckor, märkenas antal för den senaste månaden (för trenderna) och
    # priser bara för de mest sålda i veckan som startsidan visar.
    veckor = {}
    for kat, v in (B.get("tradera_veckor") or {}).items():
        fulla = [p for p in v if p[1] >= 5]
        visad = fulla[-2] if len(fulla) > 1 else (fulla[-1] if fulla else None)
        mest = set()
        if visad:
            mest = {m for _, m in sorted(((c[0], m) for m, c in visad[2].items() if ok(m)), reverse=True)[:TOPP]}
        rader = []
        for i, p in enumerate(v):
            if i < len(v) - VECKOR:
                rader.append([p[0], p[1], {}])
            else:
                rader.append([p[0], p[1], {m: (c if p is visad and m in mest else [c[0], None]) for m, c in p[2].items()}])
        veckor[kat] = rader
    ut["tradera_veckor"] = veckor

    # Vinstexemplet: ett märke med många sålda, helst en stickad tröja.
    kandidater = []
    for k in kats:
        for m, pts in ((B.get("marke") or {}).get("tradera") or {}).get(k["id"], {}).items():
            p = pts[-1] if pts else None
            if p and p[2] and p[1] >= 10 and 80 <= p[2] - INKOP < 2000 and ok(m):
                kandidater.append((k["id"] == "stickat", p[1], k["id"], m, p))
    if kandidater:
        _, _, kat, m, p = max(kandidater, key=lambda x: (x[0], x[1]))
        ut["marke"] = {"tradera": {kat: {m: [p]}}}
    return ut


def main(fran, till):
    try:
        with open(fran, encoding="utf-8") as f:
            B = json.load(f)
    except (OSError, ValueError):
        B = {}
    with open(till, "w", encoding="utf-8") as f:
        json.dump(smakprov(B), f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
