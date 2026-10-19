"""Byter väggen bakom en produktbild mot en vit studiobakgrund.

Målet är att det ska se ut som en riktig vit papprulle/plansch, inte ett
platt urklipp: väggens mjuka skuggor runt plagget/personen följer med, och
bakgrunden får en svag ljusvariation (ljusast i mitten, lite mörkare mot
kanterna) som på en riktig studiobild.

Användning:
    python3 vit_bakgrund.py bild.jpg [fler.jpg ...] [--ut mapp]

Första körningen laddar ner segmenteringsmodellerna (~350 MB) till
~/.cache/vit_bakgrund. Kräver numpy, Pillow och onnxruntime.
"""

import argparse
import os
import sys
import urllib.request

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageFilter, ImageOps

MODELLER = {
    "isnet": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/isnet-general-use.onnx",
    "human": "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net_human_seg.onnx",
}
CACHE = os.environ.get("VIT_BAKGRUND_MODELLER", os.path.expanduser("~/.cache/vit_bakgrund"))

# Utseende
VIT_MITT = 250.0      # ljusaste punkten på bakgrunden (0-255)
VIT_KANT = 228.0      # mörkaste hörnet, ger "studioljus"-känslan
SKUGGSTYRKA = 0.85    # hur mycket av väggens skugga som följer med (0-1)
VITBALANS = 0.6      # hur mycket rummets färgstick tas bort från motivet (0-1)
SKUGGLYFT = 0.85      # <1 lyfter mörka partier i motivet (1 = av)
KONTRAST = 0.15       # svag S-kurva på motivet (0 = av)
KASTSKUGGA = 0.07     # styrka på den mjuka skuggan bakom motivet (0-1)


def hamta_modell(namn):
    os.makedirs(CACHE, exist_ok=True)
    sokvag = os.path.join(CACHE, namn + ".onnx")
    if not os.path.exists(sokvag):
        print(f"Laddar ner modell {namn} ...", file=sys.stderr)
        urllib.request.urlretrieve(MODELLER[namn], sokvag + ".tmp")
        os.replace(sokvag + ".tmp", sokvag)
    return ort.InferenceSession(sokvag, providers=["CPUExecutionProvider"])


def kor_modell(sess, bild, storlek, medel, std):
    x = np.asarray(bild.convert("RGB").resize((storlek, storlek), Image.LANCZOS), np.float32) / 255.0
    x = (x / max(x.max(), 1e-6) - medel) / std
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    ut = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
    ut = (ut - ut.min()) / max(ut.max() - ut.min(), 1e-6)
    return np.asarray(Image.fromarray((ut * 255).astype(np.uint8)).resize(bild.size, Image.LANCZOS),
                      np.float32) / 255.0


def gauss(a, sigma):
    """Gaussisk oskärpa via FFT (fungerar på 2D-array)."""
    if sigma <= 0:
        return a
    h, w = a.shape
    pad = int(3 * sigma)
    p = np.pad(a, pad, mode="reflect")
    fy = np.fft.fftfreq(p.shape[0])[:, None]
    fx = np.fft.rfftfreq(p.shape[1])[None, :]
    k = np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    ut = np.fft.irfft2(np.fft.rfft2(p) * k, s=p.shape)
    return ut[pad:pad + h, pad:pad + w]


def normaliserad_blur(v, vikt, sigma):
    """Oskärpa som bara räknar med pixlar där vikt > 0 (fyller hål)."""
    return gauss(v * vikt, sigma) / np.maximum(gauss(vikt, sigma), 1e-4)


def mask_for(bild):
    isnet = kor_modell(hamta_modell("isnet"), bild, 1024, 0.5, 1.0)
    human = kor_modell(hamta_modell("human"), bild, 320,
                       np.array([0.485, 0.456, 0.406]), np.array([0.229, 0.224, 0.225]))
    # Människomodellen avgör vad som hör till motivet (så element o.d. åker bort),
    # den skarpare isnet-modellen ger kanterna.
    grov = gauss((human > 0.5).astype(np.float32), 6) > 0.2
    alfa = np.where(grov, isnet, 0.0)
    alfa = np.clip((alfa - 0.1) / 0.8, 0, 1)
    return alfa


def gor_vit(bild):
    bild = ImageOps.exif_transpose(bild).convert("RGB")
    I = np.asarray(bild, np.float32)
    h, w = I.shape[:2]
    alfa = mask_for(bild)
    lum = I @ np.array([0.299, 0.587, 0.114], np.float32)

    # Väggpixlar som säkert är vägg (inte motiv, inte saker som element/lister).
    bort_fran_motiv = gauss(alfa, 4) < 0.02
    # Saker på väggen (element, lister, kontakter) skiljer sig i ljus från väggen
    # runt omkring; de räknas bort så att de försvinner i stället för att följa med.
    sm = max(h, w)
    vikt = bort_fran_motiv.astype(np.float32)
    for _ in range(2):
        jamfor = normaliserad_blur(lum, vikt, sm / 25)
        avvikelse = np.abs(lum / np.maximum(jamfor, 1) - 1)
        vikt = (bort_fran_motiv & (avvikelse < 0.12)).astype(np.float32)
        vikt = (gauss(vikt, 4) > 0.97).astype(np.float32)

    # Väggens ljus utan detaljer: storskaligt (belysning) och lokalt (skuggor nära motivet).
    ljus_stor = normaliserad_blur(lum, vikt, sm / 6)
    tackning = gauss(vikt, sm / 50)
    ljus_lokal = np.where(tackning > 0.05, normaliserad_blur(lum, vikt, sm / 50), ljus_stor)
    t = np.clip((tackning - 0.1) / 0.4, 0, 1)
    ljus_lokal = t * ljus_lokal + (1 - t) * ljus_stor
    skugga = gauss(np.clip(ljus_lokal / np.maximum(ljus_stor, 1), 0.8, 1.0), sm / 100)
    # Skuggan behålls bara nära motivet; längre bort är det väggens ojämnheter,
    # och där ska studiobakgrunden vara slät.
    nara = np.clip(gauss(alfa, sm / 40) * 6, 0, 1)
    skugga = 1 - SKUGGSTYRKA * nara * (1 - skugga)
    # Svag mjuk kastskugga, som när man står en bit framför en papprulle.
    forskj = np.roll(np.roll(alfa, int(sm * 0.006), 1), int(sm * 0.008), 0)
    skugga = skugga * (1 - KASTSKUGGA * gauss(forskj, sm / 70))

    # Studioljus: mjuk radiell avtoning från strax ovanför mitten.
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w * 0.75)) ** 2 + ((yy - h * 0.42) / (h * 0.85)) ** 2)
    studio = VIT_MITT - (VIT_MITT - VIT_KANT) * np.clip(r, 0, 1) ** 1.6
    ny_bg = (studio * skugga)[..., None] * np.array([1.0, 0.997, 0.99], np.float32)

    # Rensa bort väggfärg i kanterna på motivet innan det läggs på den vita bakgrunden.
    vagg_farg = np.stack([normaliserad_blur(I[..., c], vikt + 1e-3, sm / 60) for c in range(3)], -1)
    a = alfa[..., None]
    forgrund = np.where(a > 0.05, (I - (1 - a) * vagg_farg) / np.maximum(a, 0.05), I)
    # Vitbalans: rummets ljus (t.ex. gul taklampa) syns på väggen. Motivet
    # neutraliseras mot den färgen så att det matchar den vita bakgrunden.
    vagg_medel = I[vikt > 0].mean(0)
    forstarkning = (vagg_medel.mean() / vagg_medel) ** VITBALANS
    forstarkning /= forstarkning @ np.array([0.299, 0.587, 0.114], np.float32)
    forgrund = np.clip(forgrund * forstarkning, 0, 255)

    # Lyft skuggorna lite så att tygstrukturen syns även i mörka plagg,
    # och ge en svag kontrastkurva i mellantonerna.
    flum = np.maximum(forgrund @ np.array([0.299, 0.587, 0.114], np.float32), 0.5) / 255.0
    ny_lum = flum ** SKUGGLYFT
    ny_lum = ny_lum + KONTRAST * ny_lum * (1 - ny_lum) * (ny_lum - 0.5) * 4
    forgrund = np.clip(forgrund * (ny_lum / flum)[..., None], 0, 255)

    ut = forgrund * a + ny_bg * (1 - a)
    # Lite filmkorn på bakgrunden så den inte ser datorgenererad ut.
    korn = np.random.default_rng(0).normal(0, 1.2, (h, w, 1)).astype(np.float32)
    ut = ut + korn * (1 - a)
    ut = Image.fromarray(np.clip(ut + 0.5, 0, 255).astype(np.uint8))
    # Skärpning bara på motivet, bakgrunden ska förbli mjuk.
    skarp = ut.filter(ImageFilter.UnsharpMask(radius=2, percent=70, threshold=2))
    ut = Image.composite(skarp, ut, Image.fromarray((alfa * 255).astype(np.uint8)))
    return ut, alfa


def beskar(bild, alfa, format_):
    """Beskär till t.ex. 3:4 stående, centrerat på motivet."""
    bw, bh = (float(x) for x in format_.split(":"))
    w, h = bild.size
    if w / h > bw / bh:
        ny_w, ny_h = int(round(h * bw / bh)), h
    else:
        ny_w, ny_h = w, int(round(w * bh / bw))
    kol = alfa.sum(0)
    rad = alfa.sum(1)
    cx = (kol * np.arange(w)).sum() / max(kol.sum(), 1)
    cy = (rad * np.arange(h)).sum() / max(rad.sum(), 1)
    x0 = int(np.clip(cx - ny_w / 2, 0, w - ny_w))
    y0 = int(np.clip(cy - ny_h / 2, 0, h - ny_h))
    return bild.crop((x0, y0, x0 + ny_w, y0 + ny_h))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("bilder", nargs="+")
    p.add_argument("--ut", default=None, help="mapp att spara i (standard: bredvid originalet)")
    p.add_argument("--format", default=None, help="beskär till bildformat, t.ex. 3:4 (standard: behåll)")
    args = p.parse_args()
    for sokvag in args.bilder:
        ut_mapp = args.ut or os.path.dirname(os.path.abspath(sokvag))
        os.makedirs(ut_mapp, exist_ok=True)
        namn = os.path.splitext(os.path.basename(sokvag))[0] + "-vit.jpg"
        ut, alfa = gor_vit(Image.open(sokvag))
        if args.format:
            ut = beskar(ut, alfa, args.format)
        ut.save(os.path.join(ut_mapp, namn), quality=95, subsampling=0)
        print(os.path.join(ut_mapp, namn))


if __name__ == "__main__":
    main()
