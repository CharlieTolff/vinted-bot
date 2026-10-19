"""Daglig marknadsföringsvideo (9:16) av produktbilderna för ett plagg.

Användning:
  python3 daglig_video.py --mapp /mnt/project-files/saljbilder/02-replay-jeans-bla \
      --marke Replay --titel "Anbass jeans, mörkblå" --detalj "W31 L32  ·  Bra skick" \
      [--pris "299 kr"] [--rubrik "Dagens fynd"] --ut video.mp4
"""
import argparse, glob, os, shutil, subprocess, tempfile
import numpy as np
from PIL import Image, ImageFilter, ImageOps
import klipp_ihop as k

W, H, FPS = k.W, k.H, k.FPS
VISA, SVEP, SLUT = 2.6, 0.35, 4.2


def zoom(bild, t):
    """Långsam inzoomning (Ken Burns) över bildens visningstid, t i [0,1]."""
    s = 1.0 + 0.07 * t
    w, h = int(W * s), int(H * s)
    b = bild.resize((w, h), Image.LANCZOS)
    x, y = (w - W) // 2, int((h - H) * 0.4)
    return b.crop((x, y, x + W, y + H))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--mapp', required=True)
    p.add_argument('--marke', required=True); p.add_argument('--titel', required=True)
    p.add_argument('--detalj', required=True); p.add_argument('--pris', default='')
    p.add_argument('--rubrik', default='Dagens fynd'); p.add_argument('--ut', required=True)
    a = p.parse_args()

    filer = sorted(glob.glob(os.path.join(a.mapp, '*.jpg')))[:4]
    foton = [ImageOps.fit(Image.open(f).convert('RGB'), (W, H), Image.LANCZOS, centering=(0.5, 0.45)) for f in filer]
    prod = dict(marke=a.marke, titel=a.titel, detalj=a.detalj, pris=a.pris or 'Fynd', bilder=filer)
    kort = k.kort_bas(prod)
    kort_bilder = k.foton(prod)

    tmp = tempfile.mkdtemp()
    nr = [0]

    def spara(b):
        nr[0] += 1
        b.save(f'{tmp}/{nr[0]:05d}.png', compress_level=1)

    rubrik = k.font('Bold', 76); under = k.font('SemiBold', 44)
    nv, ns = int(VISA * FPS), int(SVEP * FPS)
    for i, foto in enumerate(foton):
        for j in range(nv):
            t = j / nv
            b = zoom(foto, t)
            if i == 0:
                # Rubrik överst första bilden, med mörk ton bakom för läsbarhet.
                a_ = k.ease_io(j / 10) * (1 - k.ease_io((j - nv + 12) / 12))
                if a_ > 0:
                    band = Image.new('RGBA', (W, 420), (0, 0, 0, 0))
                    gr = np.linspace(110, 0, 420).astype(np.uint8)
                    band.putalpha(Image.fromarray(np.repeat(gr[:, None], W, 1)).point(lambda v: int(v * a_)))
                    b = Image.alpha_composite(b.convert('RGBA'), _band(b, band)).convert('RGB')
                    b = k.text_overlay(b, [(a.rubrik.upper(), under, (255, 255, 255)),
                                           (f'{a.marke} {a.titel.split(",")[0]}', rubrik, (255, 255, 255))], a_, 190)
            spara(b)
        if i < len(foton) - 1:
            # Svep till nästa bild.
            fran, till = zoom(foto, 1.0), zoom(foton[i + 1], 0.0)
            for j in range(ns):
                off = int(k.ease_io((j + 1) / ns) * W)
                b = Image.new('RGB', (W, H))
                b.paste(fran, (-off, 0)); b.paste(till, (W - off, 0))
                spara(b)
    # Slut: suddig bakgrund + annonskortet som glider upp.
    bas = foton[0].filter(ImageFilter.GaussianBlur(28))
    kk = kort.copy(); kk.paste(k.karusell(kort_bilder, 0.0), (0, 0)); kk = k.avrunda(kk, k.RADIE)
    for j in range(int(SLUT * FPS)):
        b = k.lagg_kort(bas, kk, j / 14)
        b = k.text_overlay(b, [('Länk i bio', under, (255, 255, 255))], k.ease_io((j - 14) / 10), 300)
        spara(b)

    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(FPS), '-i', f'{tmp}/%05d.png',
                    '-c:v', 'libx264', '-preset', 'slow', '-crf', '19', '-pix_fmt', 'yuv420p',
                    '-movflags', '+faststart', a.ut], check=True)
    shutil.rmtree(tmp)
    print(a.ut, nr[0] / FPS, 's')


def _band(b, band):
    lager = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    lager.paste(Image.new('RGBA', band.size, (0, 0, 0, 255)), (0, 0), band)
    return lager


if __name__ == '__main__':
    main()
