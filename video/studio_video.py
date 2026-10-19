"""Studiobakgrund på en hel videosekvens utan flimmer.

Användning: python3 studio_video.py ramar_mapp mask_mapp ut_mapp [--crop-x X]
Ramarna är PNG från ffmpeg, maskerna är alfa-PNG (samma namn) från vit_bakgrund.mask_for.
"""
import sys, os, glob, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import numpy as np
from PIL import Image, ImageFilter, ImageOps, ImageDraw
import vit_bakgrund as v

LUM = np.array([0.299, 0.587, 0.114], np.float32)
UT_W, UT_H = 1080, 1920


def las(f, mode='RGB'):
    return np.asarray(Image.open(f).convert(mode), np.float32)


def gor_plate(ramar, A, h, w, sm):
    """Tom vägg: för varje pixel tas den av första/sista rutorna där personen är längst bort."""
    n = len(ramar)
    kand = sorted(set([0, 1, 2, 4, 6, n - 7, n - 5, n - 3, n - 2, n - 1]))
    basta = np.full((h, w), 9.0, np.float32)
    plate = np.zeros((h, w, 3), np.float32)
    for i in kand:
        narhet = v.gauss(A[i], 12)
        I = np.asarray(Image.open(ramar[i]).convert('RGB'), np.float32)
        b = narhet < basta - 1e-3
        plate[b] = I[b]
        basta = np.minimum(basta, narhet)
    return plate


def main():
    p = argparse.ArgumentParser()
    p.add_argument('ramar'); p.add_argument('masker'); p.add_argument('ut')
    p.add_argument('--fran', type=int, default=0); p.add_argument('--till', type=int, default=10**6)
    p.add_argument('--bara', type=str, default='')
    p.add_argument('--hojd', type=float, default=1.0, help='andel av höjden (uppifrån) som behålls')
    a = p.parse_args()
    os.makedirs(a.ut, exist_ok=True)
    ramar = sorted(glob.glob(a.ramar + '/*.png'))
    n = len(ramar)
    masker = [os.path.join(a.masker, os.path.basename(f)) for f in ramar]
    h, w = las(ramar[0], 'L').shape
    sm = max(h, w)

    # Alfa per ruta, temporalt medianfiltrerad (tar bort enstaka hopp i masken).
    print('laddar masker', flush=True)
    A0 = np.stack([np.asarray(Image.open(m).convert('L')) for m in masker])
    A = np.empty(A0.shape, np.float32)
    for i in range(n):
        p_, c_, n_ = A0[max(i - 1, 0)], A0[i], A0[min(i + 1, n - 1)]
        A[i] = np.maximum(np.minimum(p_, c_), np.minimum(np.maximum(p_, c_), n_))
    A /= 255
    del A0

    # Tom vägg (clean plate): median över rutor där pixeln inte är skymd.
    print('clean plate', flush=True)
    cache = a.ut.rstrip('/') + '_cache.npz'
    if os.path.exists(cache):
        plate = np.load(cache)['plate']
    else:
        plate = gor_plate(ramar, A, h, w, sm)
        np.savez(cache, plate=plate)
    plate_lum = plate @ LUM
    vagg_farg = np.stack([v.gauss(plate[..., c], 3) for c in range(3)], -1)

    # Statisk studiobakgrund (samma ljus som produktbilderna).
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / (w * 0.75)) ** 2 + ((yy - h * 0.42) / (h * 0.85)) ** 2)
    studio = v.VIT_MITT - (v.VIT_MITT - v.VIT_KANT) * np.clip(r, 0, 1) ** 1.6
    studio = studio * (1 + v.SIDLJUS / 2 - v.SIDLJUS * xx / w)
    bg_ton = np.array(v.BG_TON, np.float32)

    # Fast vitbalans för hela klippet, räknad på väggen och motivet i mitten av klippet.
    mitt = int(np.argmax(A.reshape(n, -1).sum(1)))
    I = las(ramar[mitt]); al = A[mitt]
    fg = np.where(al[..., None] > 0.05, (I - (1 - al[..., None]) * vagg_farg) / np.maximum(al[..., None], 0.05), I)
    vagg_medel = plate.reshape(-1, 3).mean(0)
    motiv_medel = fg[al > 0.9].mean(0)
    for styrka in np.arange(v.VITBALANS, -0.001, -0.05):
        gain = (vagg_medel.mean() / vagg_medel) ** styrka
        gain /= gain @ LUM
        rr, _, bb = motiv_medel * gain
        if bb <= rr * v.BG_TON[2]:
            break
    print('vitbalans', styrka, gain, flush=True)

    # Exponering per ruta (telefonen justerar när man kliver in), mätt på fri vägg.
    expo = np.ones(n, np.float32)
    for i in range(n):
        f = las(ramar[i]) @ LUM
        m = v.gauss(A[i], 6) < 0.01
        expo[i] = np.median(f[m] / np.maximum(plate_lum[m], 1)) if m.sum() > 1000 else 1
    expo = np.convolve(np.pad(expo, 5, mode='edge'), np.ones(11) / 11, 'valid')

    # Fast beskärning till 9:16 kring motivets mittpunkt.
    ch = int(round(h * a.hojd))
    cw = int(round(ch * UT_W / UT_H))
    tyngd = A[:, :ch].sum((1, 2))
    kol = (A[:, :ch].sum(1) * np.arange(w)).sum(1) / np.maximum(tyngd, 1)
    stor = tyngd > tyngd.max() * 0.5
    cx = float(np.median(kol[stor]))
    x0 = int(np.clip(cx - cw / 2, 0, w - cw))
    print('crop', x0, cw, flush=True)

    rng = np.random.default_rng(1)
    hal_zon = np.clip((0.42 * h - yy) / (0.05 * h), 0, 1)
    ovre_zon = np.clip((0.6 * h - yy) / (0.05 * h), 0, 1)
    pmax, pmin = plate.max(-1), plate.min(-1)
    plate_varme = (plate[..., 0] - plate[..., 2]) / (plate_lum + 1)
    plate_farg = (pmax - pmin) / np.maximum(plate_lum, 1) > 0.1
    lista = [int(x) - 1 for x in a.bara.split(',')] if a.bara else range(max(a.fran, 0), min(a.till, n))
    for i in lista:
        dst = os.path.join(a.ut, f'{i + 1:04d}.png')
        if os.path.exists(dst) and not a.bara:
            continue
        I = las(ramar[i]); al = A[i]
        lum = I @ LUM
        # Kameran står still, så skillnaden mot tomma väggen hittar det modellen
        # missar när man går (rörelseoskärpa på ben och fötter).
        pl = plate_lum * expo[i] + 1
        dc = np.sqrt((((I / (lum + 1)[..., None]) - plate / (plate_lum + 1)[..., None]) ** 2).sum(-1))
        ratio = (lum + 1) / pl
        # Hål i masken (vit t-shirt) och missade ben/fötter fylls där bilden
        # tydligt skiljer sig från tomma väggen/golvet.
        hud_ovre = (I[..., 0] > 1.22 * np.maximum(I[..., 1], 1)) & (lum > 95) & (yy < 0.3 * h)
        cue = np.maximum(np.clip((ratio - 1.12) / 0.06, 0, 1), hud_ovre) * ovre_zon
        cue = v.gauss(cue, 2) * (v.gauss(al, 30) > 0.02)
        cue = (v.gauss((cue > 0.5).astype(np.float32), 6) > 0.7).astype(np.float32)
        # Helt inneslutna hål i masken (t.ex. fläckar på t-shirten) fylls.
        bg = Image.fromarray(((np.maximum(al, cue) < 0.5) * 255).astype(np.uint8)).resize((w // 4, h // 4), Image.BILINEAR)
        bg = ImageOps.expand(bg.point(lambda x: 255 if x > 127 else 0), 1, fill=255)
        # Överkanten räknas inte som öppen: hål som bara når upp till bildkanten
        # (mellan slagen, under hakan) är också t-shirt.
        ImageDraw.Draw(bg).line((0, 0, w // 4 + 1, 0), fill=0)
        ImageDraw.floodfill(bg, (0, h // 4), 128)
        ImageDraw.floodfill(bg, (w // 4 + 1, h // 4), 128)
        hal = np.asarray(bg.crop((1, 1, w // 4 + 1, h // 4 + 1)).resize((w, h), Image.BILINEAR), np.float32)
        cue = np.maximum(cue, v.gauss((hal > 190).astype(np.float32), 2) * hal_zon)
        tillagd = np.clip((v.gauss(cue, 3) - 0.2) / 0.4, 0, 1)
        modell = al
        al = np.maximum(al, tillagd)
        # Ta bort små lösa fläckar (golvbitar) som inte hänger ihop med kroppen.
        oppnad = v.gauss((v.gauss((al > 0.5).astype(np.float32), 5) > 0.85).astype(np.float32), 5) > 0.15
        behall = v.gauss((v.gauss(oppnad.astype(np.float32), 4) > 0.05).astype(np.float32), 1.5)
        al = al * behall
        modell = modell * behall
        tillagd = tillagd * behall
        # Glipor (mellan arm och kropp) som modellen tagit med: samma färg som
        # tomma väggen/golvet, även om det ligger i skugga. Hud räknas aldrig bort.
        # Väggen i skugga blir minst lika varm (brun) som väggen; plaggen är grå/svarta/blå.
        hud = (I[..., 0] > 1.22 * np.maximum(I[..., 1], 1)) & (lum > 90)
        varme = (I[..., 0] - I[..., 2]) / (lum + 1)
        likt = (varme > np.maximum(0.13, 0.75 * plate_varme)) & (ratio > 0.15) & (ratio < 1.1) & ~hud & (lum > 38) & (lum < 185) & plate_farg & (yy > 0.35 * h)
        # Det som ser exakt ut som tomma väggen (eluttag, list) räknas också bort.
        likt |= (dc < 0.03) & (np.abs(ratio - 1) < 0.08) & (yy > 0.35 * h)
        likt = v.gauss((v.gauss(likt.astype(np.float32), 7) > 0.8).astype(np.float32), 6) > 0.2
        bort = v.gauss(likt.astype(np.float32), 2)
        al = al * (1 - bort); modell = modell * (1 - bort); tillagd = tillagd * (1 - bort)
        a3 = al[..., None]
        # Verklig skugga från personen: rutan delat med tomma väggen.
        fri = (1 - np.clip(v.gauss(al, 3) * 4, 0, 1)).astype(np.float32)
        kvot = lum / np.maximum(plate_lum * expo[i], 1)
        kvot = v.normaliserad_blur(np.clip(kvot, 0.4, 1.1), fri + 1e-4, sm / 120)
        kvot = np.clip(kvot, 0.8, 1.0)
        nara = np.clip(v.gauss(al, sm / 40) * 6, 0, 1)
        skugga = 1 - v.SKUGGSTYRKA * 0.8 * nara * (1 - kvot)
        forskj = np.roll(np.roll(al, int(sm * 0.006), 1), int(sm * 0.008), 0)
        skugga = skugga * (1 - v.KASTSKUGGA * v.gauss(forskj, sm / 70))
        ny_bg = (studio * skugga)[..., None] * bg_ton

        m3 = modell[..., None]
        fg = np.where(m3 > 0.05, (I - (1 - m3) * vagg_farg * expo[i]) / np.maximum(m3, 0.05), I)
        # Där bara skillnaden mot väggen lagt till motiv används bilden som den är.
        fg = np.where((tillagd > modell)[..., None], I, fg)
        fg = np.clip(fg * gain, 0, 255)
        flum = np.maximum(fg @ LUM, 0.5) / 255.0
        nl = flum ** v.SKUGGLYFT
        nl = nl + v.KONTRAST * nl * (1 - nl) * (nl - 0.5) * 4
        fg = np.clip(fg * (nl / flum)[..., None], 0, 255)

        ut = fg * a3 + ny_bg * (1 - a3)
        ut = ut + rng.normal(0, 1.0, (h, w, 1)).astype(np.float32) * (1 - a3)
        ut = Image.fromarray(np.clip(ut + 0.5, 0, 255).astype(np.uint8))
        skarp = ut.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
        ut = Image.composite(skarp, ut, Image.fromarray((al * 255).astype(np.uint8)))
        ut = ut.crop((x0, 0, x0 + cw, ch)).resize((UT_W, UT_H), Image.LANCZOS)
        ut.save(dst, compress_level=1)
        if i % 20 == 0:
            print('ruta', i + 1, flush=True)


if __name__ == '__main__':
    main()
