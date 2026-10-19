"""Klipper ihop blazer-videon: studio-rutor, frys + annonskort med bildkarusell, text."""
import os, sys, glob, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps

V = os.path.dirname(os.path.abspath(__file__))
W, H, FPS = 1080, 1920, 30
FONT = '/usr/share/fonts/opentype/inter/Inter-%s.otf'
SALJ = '/mnt/project-files/saljbilder'


def font(vikt, storlek):
    return ImageFont.truetype(FONT % vikt, storlek)


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def ease_io(t):
    t = min(max(t, 0.0), 1.0)
    return 3 * t * t - 2 * t * t * t


def avrunda(bild, radie):
    m = Image.new('L', bild.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, *bild.size), radie, fill=255)
    bild = bild.convert('RGBA')
    bild.putalpha(m)
    return bild


PRODUKTER = {
    'olymp': dict(
        marke='Olymp Level Five', titel='Stickad blazer, grå', detalj='Storlek M  ·  Bra skick', pris='349 kr',
        bilder=sorted(glob.glob(SALJ + '/07-olymp-stickad-blazer-gra/[123]-*.jpg'))),
    'keylargo': dict(
        marke='Key Largo', titel='Stickad blazer, svart', detalj='Storlek L  ·  Bra skick', pris='349 kr',
        bilder=sorted(glob.glob(SALJ + '/06-key-largo-blazer-svart/[12]-*.jpg'))),
}

KW, FOTO_H, TEXT_H, RADIE = 720, 900, 250, 34
KH = FOTO_H + TEXT_H


def kort_bas(p):
    """Kortet utan foto: vit yta med texten."""
    kort = Image.new('RGBA', (KW, KH), (255, 255, 255, 255))
    d = ImageDraw.Draw(kort)
    x, y = 40, FOTO_H + 30
    d.text((x, y), p['marke'].upper(), font=font('SemiBold', 26), fill=(120, 120, 120))
    d.text((x, y + 40), p['titel'], font=font('Bold', 44), fill=(25, 25, 25))
    d.text((x, y + 102), p['detalj'], font=font('Regular', 30), fill=(110, 110, 110))
    d.text((x, y + 152), p['pris'], font=font('Bold', 50), fill=(25, 25, 25))
    # Liten etikett nere till höger.
    f = font('SemiBold', 26)
    txt = 'Finns på Vinted & Plick'
    tw = d.textlength(txt, font=f)
    bx1, by1 = KW - 40, y + 207
    d.rounded_rectangle((bx1 - tw - 44, by1 - 50, bx1, by1), 25, fill=(0, 119, 130))
    d.text((bx1 - tw - 22, by1 - 25), txt, font=f, fill=(255, 255, 255), anchor='lm')
    return kort


def foton(p):
    ut = []
    for f in p['bilder']:
        b = ImageOps.fit(Image.open(f).convert('RGB'), (KW, FOTO_H), Image.LANCZOS, centering=(0.5, 0.45))
        ut.append(b)
    return ut


def karusell(bilder, pos):
    """pos = flyttal i bildindex, 1.5 = mitt i svepet mellan bild 2 och 3."""
    yta = Image.new('RGB', (KW, FOTO_H), (240, 240, 240))
    i = int(np.floor(pos)); fr = pos - i
    off = int(round(fr * KW))
    yta.paste(bilder[i], (-off, 0))
    if fr > 0 and i + 1 < len(bilder):
        yta.paste(bilder[i + 1], (KW - off, 0))
    # Prickar för bildnummer.
    d = ImageDraw.Draw(yta)
    n = len(bilder); r = 7; mel = 26
    x0 = KW / 2 - (n - 1) * mel / 2
    aktiv = int(round(pos))
    for k in range(n):
        c = (255, 255, 255) if k == aktiv else (255, 255, 255, 120)
        fill = (255, 255, 255) if k == aktiv else (200, 200, 200)
        d.ellipse((x0 + k * mel - r, FOTO_H - 36 - r, x0 + k * mel + r, FOTO_H - 36 + r), fill=fill,
                  outline=(90, 90, 90), width=1)
    return yta


def skugga_for(radie=34):
    m = Image.new('L', (KW + 160, KH + 160), 0)
    ImageDraw.Draw(m).rounded_rectangle((80, 95, 80 + KW, 95 + KH), radie, fill=110)
    return m.filter(ImageFilter.GaussianBlur(30))


SKUGGA = None


def lagg_kort(bas, kort, t_in):
    """Kortet glider upp underifrån. t_in i [0,1]."""
    global SKUGGA
    if SKUGGA is None:
        SKUGGA = skugga_for()
    e = ease(t_in)
    x = (W - KW) // 2
    y_mal = H - KH - 150
    y = int(round(H + 40 + (y_mal - H - 40) * e))
    bild = bas.copy()
    # Lätt nedtoning av bakgrunden så kortet lyfter.
    if e > 0:
        mork = Image.new('RGB', (W, H), (0, 0, 0))
        bild = Image.blend(bild, mork, 0.18 * e)
    bild.paste((0, 0, 0), (x - 80, y - 80), Image.eval(SKUGGA, lambda v: int(v * e)))
    bild.paste(kort, (x, y), kort)
    return bild


def text_overlay(bild, rader, alfa, y_mitt):
    """Centrerad rubriktext med mjuk skugga, alfa 0..1."""
    if alfa <= 0:
        return bild
    lager = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lager)
    tot = sum(f.size + 18 for _, f, _ in rader)
    y = y_mitt - tot / 2
    for txt, f, farg in rader:
        d.text((W / 2, y), txt, font=f, fill=farg + (int(255 * alfa),), anchor='mt')
        y += f.size + 18
    return Image.alpha_composite(bild.convert('RGBA'), lager).convert('RGB')


def main():
    plan = json.load(open(os.path.join(V, 'plan.json')))
    ut = os.path.join(V, 'ut'); os.makedirs(ut, exist_ok=True)
    for f in glob.glob(ut + '/*.png'):
        os.remove(f)
    nr = [0]

    def spara(b):
        nr[0] += 1
        b.save(f'{ut}/{nr[0]:05d}.png', compress_level=1)

    rubrik = font('Bold', 84); under = font('Medium', 44)
    tom = Image.open(os.path.join(V, plan['tom_ruta'])).convert('RGB')
    i_ = plan['intro']
    for i in range(int(i_['sek'] * FPS)):
        a = ease_io(i / 10) * (1 - ease_io((i - (i_['sek'] * FPS - 10)) / 10))
        spara(text_overlay(tom, [(i_['rad1'], rubrik, (30, 30, 30)), (i_['rad2'], under, (90, 90, 90))], a, 900))
    for k, sek in enumerate(plan['sekvenser']):
        rutor = sorted(glob.glob(os.path.join(V, sek['mapp'], '*.png')))[sek['start'] - 1:sek['slut']]
        p = PRODUKTER[sek['produkt']]
        kort = kort_bas(p); bilder = foton(p)
        frys = sek['frys'] - sek['start']
        for i, f in enumerate(rutor):
            b = Image.open(f).convert('RGB')
            # Mjuk övergång från/till tomma studion i början och slutet.
            if k == 0 and i < 6:
                b = Image.blend(tom, b, (i + 1) / 7)
            if k == len(plan['sekvenser']) - 1 and len(rutor) - i <= 8:
                b = Image.blend(b, tom, (8 - (len(rutor) - i) + 1) / 9)
            spara(b)
            if i == frys:
                n = len(bilder)
                IN, VISA, SVEP = 14, 34, 10
                total = IN + n * VISA + (n - 1) * SVEP + IN
                for j in range(total):
                    if j < IN:
                        t_in, pos = j / IN, 0.0
                    elif j >= total - IN:
                        t_in, pos = 1 - (j - (total - IN)) / IN, n - 1.0
                        # Sista fotot ligger kvar när kortet glider ner.
                    else:
                        t_in = 1.0
                        jj = j - IN
                        cyk = VISA + SVEP
                        idx = jj // cyk; inne = jj % cyk
                        pos = idx + (ease_io((inne - VISA) / SVEP) if inne >= VISA and idx < n - 1 else 0)
                        pos = min(pos, n - 1.0)
                    if j == total - IN:
                        pos = n - 1.0
                    kk = kort.copy()
                    kk.paste(karusell(bilder, pos), (0, 0))
                    kk = avrunda(kk, RADIE)
                    spara(lagg_kort(b, kk, t_in))
    # Avslutning: sista rutan står kvar med text.
    o = plan['outro']
    for i in range(int(o['sek'] * FPS)):
        a = ease_io(i / 12)
        spara(text_overlay(tom, [(o['rad1'], rubrik, (30, 30, 30)), (o['rad2'], under, (90, 90, 90))], a, 900))
    print('rutor', nr[0])


if __name__ == '__main__':
    main()
