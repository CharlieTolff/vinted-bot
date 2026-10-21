"""Förbereder hemsidans "Skriv beskrivning" så att den känner igen plagget på
bilden. Samma gratis bildmodell (CLIP) som bildkollen använder, men den körs i
besökarens webbläsare.

- Bilddelen av CLIP krymps med krymp_modell.py och läggs på hemsidan.
- Textdelen behövs inte i webbläsaren: vektorerna för alla plagg och mönster
  räknas ut här och sparas i en liten JSON-fil.

Användning:
    python3 clip_etiketter.py ut-mapp
"""
import glob
import json
import os
import sys

import numpy as np

from bildkoll import CLIP_BILD, CLIP_MAPP, CLIP_TEXT
from krymp_modell import kvantisera

# Svenskt namn på sidan -> engelska beskrivningar som CLIP förstår.
PLAGG = {
    "T-shirt": ["a t-shirt"],
    "Långärmad tröja": ["a long sleeve t-shirt"],
    "Pikétröja": ["a polo shirt with a collar"],
    "Skjorta": ["a button-up shirt", "a dress shirt"],
    "Linne": ["a tank top"],
    "Stickad tröja": ["a knitted sweater", "a knit jumper"],
    "Sweatshirt": ["a crewneck sweatshirt"],
    "Hoodie": ["a hoodie", "a hooded sweatshirt"],
    "Zip-hoodie": ["a zip-up hoodie"],
    "Kofta": ["a cardigan", "a knitted zip cardigan"],
    "Halvzip-tröja": ["a quarter-zip sweater", "a half-zip pullover"],
    "Fleecetröja": ["a fleece jacket", "a fleece pullover"],
    "Jacka": ["a jacket", "a windbreaker jacket"],
    "Dunjacka": ["a puffer jacket", "a down jacket"],
    "Jeansjacka": ["a denim jacket"],
    "Skinnjacka": ["a leather jacket"],
    "Rock": ["a long wool coat", "an overcoat"],
    "Trenchcoat": ["a trench coat"],
    "Väst": ["a puffer vest", "a gilet"],
    "Kavaj": ["a blazer", "a suit jacket"],
    "Jeans": ["a pair of jeans"],
    "Byxor": ["a pair of trousers", "a pair of chinos"],
    "Mjukisbyxor": ["a pair of sweatpants", "a pair of joggers"],
    "Shorts": ["a pair of shorts"],
    "Kjol": ["a skirt"],
    "Klänning": ["a dress"],
    "Sneakers": ["a pair of sneakers"],
    "Kängor": ["a pair of boots"],
    "Skor": ["a pair of leather shoes", "a pair of loafers"],
    "Keps": ["a baseball cap"],
    "Mössa": ["a beanie hat"],
    "Väska": ["a handbag", "a bag"],
    "Ryggsäck": ["a backpack"],
    "Halsduk": ["a scarf"],
    "Bälte": ["a belt"],
}
MONSTER = {
    "": ["a plain solid color garment", "a single color garment"],
    "Randig": ["a striped garment", "a garment with stripes"],
    "Rutig": ["a checkered plaid garment", "a flannel check pattern garment"],
    "Blommigt mönster": ["a floral pattern garment"],
    "Kamouflagemönster": ["a camouflage pattern garment"],
    "Tryck på framsidan": ["a garment with a large graphic print", "a garment with a big printed logo"],
}
MALLAR = ["a photo of {}.", "a photo of a person wearing {}.", "a product photo of {}."]


def main(ut):
    from fastembed import ImageEmbedding, TextEmbedding
    ImageEmbedding(model_name=CLIP_BILD, cache_dir=CLIP_MAPP)  # laddar ner bilddelen om den saknas
    text = TextEmbedding(model_name=CLIP_TEXT, cache_dir=CLIP_MAPP)

    def vektor(beskrivningar):
        texter = [m.format(b) for b in beskrivningar for m in MALLAR]
        v = np.mean([x / np.linalg.norm(x) for x in text.embed(texter)], axis=0)
        return [round(float(x), 5) for x in v / np.linalg.norm(v)]

    data = {"plagg": {k: vektor(v) for k, v in PLAGG.items()},
            "monster": {k: vektor(v) for k, v in MONSTER.items()}}
    os.makedirs(ut, exist_ok=True)
    with open(os.path.join(ut, "clip-etiketter.json"), "w") as f:
        json.dump(data, f, separators=(",", ":"))

    namn = CLIP_BILD.replace("/", "--")
    kandidater = glob.glob(os.path.join(CLIP_MAPP, "**", "*%s*" % namn.split("--")[-1], "**", "*.onnx"), recursive=True) \
        or glob.glob(os.path.join(CLIP_MAPP, "**", "*.onnx"), recursive=True)
    bild = [k for k in kandidater if "vision" in k.lower() or "visual" in k.lower()] or kandidater
    print("bildmodell:", bild[0], os.path.getsize(bild[0]) // 1_000_000, "MB")
    kvantisera(bild[0], os.path.join(ut, "clip-bild.onnx"))


if __name__ == "__main__":
    main(sys.argv[1])
