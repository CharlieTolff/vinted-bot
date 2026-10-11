#!/usr/bin/env python3
"""Bokföringen till hemsidan.

Läser Lager-fliken i Google-arket "Valto Resell", gör om raderna till JSON och krypterar
med ett lösenord, så att bara den som kan lösenordet kan se siffrorna på hemsidan
(GitHub Pages är öppen för alla som har länken).

  python3 bokforing.py                 hämtar arket och skriver bokforing.enc
  python3 bokforing.py --fran rader.json   krypterar rader som redan hämtats

Miljövariabler (GitHub-secrets):
  BOKFORING_ARK    länken till arket (arket måste vara delat med "alla som har länken")
  BOKFORING_LOSEN  lösenordet till bokföringssidan

Saknas någon av dem används den sparade kopian hemsida/bokforing.enc.
Krypteringen är AES-256-CBC med PBKDF2 (openssl), som sidan låser upp i webbläsaren.
"""
import csv
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone

HAR = os.path.dirname(os.path.abspath(__file__))
SPARAD = os.path.join(HAR, "hemsida", "bokforing.enc")
UT = os.path.join(HAR, "bokforing.enc")
LAGER_GID = "1191378209"
VARV = 200000  # PBKDF2-varv, samma som i bokforing.html

# Rubrik i arket -> nyckel i JSON. Talkolumnerna görs om till siffror.
KOLUMNER = {
    "ID": "id", "Produkt": "produkt", "Märke": "marke", "Kategori": "kategori", "Typ": "typ",
    "Källa": "kalla", "Inköpsdatum": "kopt", "Inköp (kr)": "inkop", "ZM-avgift": "zm",
    "Frakt (andel)": "frakt", "Tull/moms": "tull", "Totalkostnad": "kostnad", "Status": "status",
    "Målpris": "malpris", "Säljpris": "salj", "Säljavgifter": "avgift", "Plattform": "plattform",
    "Säljdatum": "sald", "Vinst": "vinst", "ROI": "roi", "Potentiell vinst": "potvinst",
    "Pot. ROI": "potroi", "Dagar i lager": "dagar", "Anteckning": "anteckning",
}
TAL = {"inkop", "zm", "frakt", "tull", "kostnad", "malpris", "salj", "avgift", "vinst", "roi", "potvinst", "potroi", "dagar"}


def tal(t):
    """'1 673 kr' -> 1673, '36,1%' -> 36.1, '-' eller tomt -> None."""
    t = str(t or "").replace(" ", "").replace(" ", "").replace(" ", "").replace("kr", "").replace("%", "")
    t = t.replace("−", "-").replace(",", ".")
    if t in ("", "-"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def rader_fran_tabell(tabell):
    """Tar arkets celler (lista av rader) och ger varorna som dictar."""
    huvud = next((i for i, r in enumerate(tabell) if r and r[0].strip() == "ID"), None)
    if huvud is None:
        raise SystemExit("Hittade inte rubrikraden (ID, Produkt, ...) i Lager-fliken")
    namn = [KOLUMNER.get(c.strip()) for c in tabell[huvud]]
    varor = []
    for r in tabell[huvud + 1:]:
        v = {}
        for k, cell in zip(namn, r):
            if k:
                v[k] = tal(cell) if k in TAL else str(cell).strip()
        if v.get("produkt"):
            varor.append(v)
    return varor


def hamta_ark(lank):
    m = re.search(r"/d/([\w-]+)", lank)
    ark_id = m.group(1) if m else lank.strip()
    g = re.search(r"gid=(\d+)", lank)
    url = f"https://docs.google.com/spreadsheets/d/{ark_id}/export?format=csv&gid={g.group(1) if g else LAGER_GID}"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "valto-resell"}), timeout=30) as svar:
        text = svar.read().decode("utf-8")
    if text.lstrip().startswith("<"):
        raise SystemExit("Fick en inloggningssida i stället för arket. Dela arket med 'alla som har länken'.")
    return list(csv.reader(io.StringIO(text)))


def kryptera(data, losen, ut):
    subprocess.run(
        ["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-iter", str(VARV), "-md", "sha256", "-salt",
         "-pass", "env:BOKFORING_LOSEN", "-out", ut],
        input=json.dumps(data, ensure_ascii=False).encode("utf-8"), check=True,
        env={**os.environ, "BOKFORING_LOSEN": losen},
    )


def main():
    losen = os.environ.get("BOKFORING_LOSEN", "")
    if "--fran" in sys.argv:
        # Rader som redan hämtats, t.ex. via Google Sheets-kopplingen: {"values": [[...], ...]}
        with open(sys.argv[sys.argv.index("--fran") + 1], encoding="utf-8") as f:
            tabell = json.load(f)
        tabell = tabell.get("values", tabell) if isinstance(tabell, dict) else tabell
        ut = SPARAD
    else:
        lank = os.environ.get("BOKFORING_ARK", "")
        if not (lank and losen):
            if os.path.exists(SPARAD):
                shutil.copyfile(SPARAD, UT)
                print("Bokföring: använder den sparade kopian (BOKFORING_ARK eller BOKFORING_LOSEN saknas)")
            return
        tabell = hamta_ark(lank)
        ut = UT
    if not losen:
        raise SystemExit("BOKFORING_LOSEN saknas")
    varor = rader_fran_tabell(tabell)
    data = {"uppdaterad": datetime.now(timezone.utc).isoformat(timespec="seconds"), "varor": varor}
    kryptera(data, losen, ut)
    print(f"Bokföring: {len(varor)} varor krypterade till {os.path.relpath(ut, HAR)}")


if __name__ == "__main__":
    main()
