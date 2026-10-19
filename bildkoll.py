"""Bildkollen: tittar på annonsens bild och säger om plagget verkligen passar alarmet.

Två sätt, det första som finns används:
- Claude (bäst, kostar per bild): när hemligheten ANTHROPIC_API_KEY finns.
- CLIP (gratis): en öppen bildmodell som körs direkt på GitHub. Den jämför bilden med alarmets
  "bild_ja" (t.ex. "a knitted hoodie") och "bild_nej" (t.ex. "a cotton sweatshirt") i sokningar.json,
  och med alarmets inspirationsbilder ("bild_exempel", bilder i mappen exempelbilder som du lägger in på hemsidan).
Finns inget av dem gör den ingenting, och boten fungerar som förut.
Svaren sparas per annons, så samma bild granskas bara en gång.
"""
import base64
import hashlib
import json
import os
import tempfile
import time
import urllib.request

MAPP = os.path.dirname(os.path.abspath(__file__))
MODELL = os.environ.get("BILD_MODELL", "claude-opus-5-5")
SPARA_DAGAR = 30
CLIP_BILD = "Qdrant/clip-ViT-B-32-vision"
CLIP_TEXT = "Qdrant/clip-ViT-B-32-text"
CLIP_MAPP = os.path.join(MAPP, ".bildmodell")
CLIP_ANDEL = 0.5  # så stor del av sannolikheten måste ligga på bild_ja för att plagget ska passa
VERSION = {"claude": "claude-1", "clip": "clip-2"}  # nytt nummer = gamla svar granskas om
# Likhet med närmaste inspirationsbild (1 = samma bild). Två bilder av samma sorts plagg hamnar oftast runt 0,8-0,9.
EXEMPEL_SAKERT = 0.85  # så lik: passar, vad orden än säger
EXEMPEL_ALDRIG = 0.62  # så olik: passar inte, vad orden än säger
EXEMPEL_ENSAM = 0.78   # alarm med bara bilder och inga ord: så lik måste den vara

SCHEMA = {
    "type": "object",
    "properties": {
        "passar": {"type": "boolean"},
        "plagg": {"type": "string"},
        "varfor": {"type": "string"},
    },
    "required": ["passar", "plagg", "varfor"],
    "additionalProperties": False,
}


def logg(text):
    print(time.strftime("%H:%M:%S") + " Bildkollen: " + text, flush=True)


class Bildkoll:
    def __init__(self, minne):
        self.minne = minne.setdefault("bilder", {})
        self.satt = None
        self.klient = self.clip = None
        self.texter = {}
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                import anthropic
                self.klient = anthropic.Anthropic(max_retries=1, timeout=60)
                self.satt = "claude"
            except ImportError:
                logg("paketet anthropic saknas.")
        if not self.satt and os.environ.get("BILDKOLL", "clip") == "clip":
            try:
                self.clip = Clip(text=True)
                self.satt = "clip"
            except Exception as e:  # paketet saknas eller modellen gick inte att hämta
                logg("CLIP gick inte att starta (%s), hoppar över bilderna." % e)
        self.kvar = int(os.environ.get("BILD_PER_RUNDA", "15" if self.satt == "claude" else "40"))

    @property
    def pa(self):
        return self.satt is not None

    def version(self, s):
        """Byts inspirationsbilderna ut granskas alarmets annonser om."""
        v = VERSION[self.satt]
        if self.satt == "clip" and exempel(s):
            v += ":" + hashlib.sha1("\n".join(exempel(s)).encode()).hexdigest()[:8]
        return v

    def svar(self, annons, s):
        """True/False om annonsen redan är granskad med det här sättet, annars None."""
        v = self.minne.get(str(annons["id"]))
        if not v or (self.satt and (len(v) < 4 or v[3] != self.version(s))):
            return None
        return v[0]

    def passar(self, annons, s, reserv=0):
        """True = passar, False = fel plagg, None = inte granskad (avstängd, slut på rundans kvot eller fel).
        reserv = så många granskningar som ska sparas till nya träffar i rundans övriga alarm."""
        tidigare = self.svar(annons, s)
        if tidigare is not None or not self.pa or not annons.get("bild") or self.kvar <= reserv:
            return tidigare
        if self.satt == "clip" and not s.get("bild_ja") and not exempel(s):
            return None  # alarmet har varken bildbeskrivningar eller inspirationsbilder
        self.kvar -= 1
        try:
            bild, typ = hamta_bild(annons["bild"])
            ok, plagg, varfor = (self.fraga_claude if self.satt == "claude" else self.fraga_clip)(bild, typ, annons, s)
        except Exception as e:  # nätet, tjänsten eller bilden krånglar: låt annonsen vara som förut och försök igen nästa runda
            logg("kunde inte granska annons %s: %s" % (annons["id"], e))
            return None
        if ok is None:
            return None
        self.minne[str(annons["id"])] = [ok, plagg[:80], round(time.time()), self.version(s)]
        if not ok:
            logg("'%s' passar inte '%s' (%s%s)" % (annons["titel"][:60], s.get("namn", ""), plagg[:40], varfor))
        return ok

    def fraga_claude(self, bild, typ, annons, s):
        if typ not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
            typ = "image/jpeg"
        fraga_ = dict(
            model=MODELL,
            max_tokens=2000,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": typ, "data": base64.standard_b64encode(bild).decode()}},
                {"type": "text", "text": fraga(annons, s)},
            ]}],
        )
        try:  # om modellen nekar tar en annan modell över i samma anrop
            svar = self.klient.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **fraga_)
        except TypeError:  # äldre version av paketet som inte känner till fallbacks
            svar = self.klient.messages.create(**fraga_)
        if svar.stop_reason == "refusal":
            return None, "", ""
        data = json.loads(next(b.text for b in svar.content if b.type == "text"))
        return bool(data["passar"]), data["plagg"], ": " + data["varfor"][:80]

    def fraga_clip(self, bild, typ, annons, s):
        bv = self.clip.bildvektor(bild)
        delar, ok_ord, plagg = [], None, ""
        ja, nej = list(s.get("bild_ja") or []), list(s.get("bild_nej") or [])
        if ja:
            etiketter = ja + nej
            nyckel = "\n".join(etiketter)
            if nyckel not in self.texter:
                self.texter[nyckel] = self.clip.textvektorer(["a photo of " + t for t in etiketter])
            # Samma räkning som CLIP själv: likhet gånger 100, sedan softmax.
            likhet = [100 * skal(bv, t) for t in self.texter[nyckel]]
            topp = max(likhet)
            vikt = [pow(2.718281828, x - topp) for x in likhet]
            andel_ja = sum(vikt[:len(ja)]) / sum(vikt)
            ok_ord, plagg = andel_ja >= CLIP_ANDEL, etiketter[max(range(len(etiketter)), key=lambda i: likhet[i])]
            delar.append("%d %% rätt sorts plagg" % round(100 * andel_ja))
        lik = self.clip.likhet(bv, exempel(s))
        if lik is None:
            ok = ok_ord
        else:
            delar.append("%d %% lik inspirationsbilden" % round(100 * lik))
            if ok_ord is None:
                ok = lik >= EXEMPEL_ENSAM
            else:
                ok = lik >= EXEMPEL_SAKERT or (ok_ord and lik >= EXEMPEL_ALDRIG)
            if ok:  # de som inte passar skrivs ut ändå, så här syns det hur lika de som passar är
                logg("'%s' passar '%s' (%s)" % (annons["titel"][:60], s.get("namn", ""), ", ".join(delar)))
        return ok, plagg, (", " if plagg else "") + ", ".join(delar)

    def stada(self):
        grans = time.time() - SPARA_DAGAR * 86400
        for k in [k for k, v in self.minne.items() if v[2] < grans]:
            del self.minne[k]


class Clip:
    """Den gratis bildmodellen. Används av bildkollen och av börsens bildspaning."""
    def __init__(self, text=False):
        from fastembed import ImageEmbedding, TextEmbedding
        self.bild = ImageEmbedding(model_name=CLIP_BILD, cache_dir=CLIP_MAPP)
        self.text = TextEmbedding(model_name=CLIP_TEXT, cache_dir=CLIP_MAPP) if text else None
        self.exempel = {}  # inspirationsbild -> dess bildvektor

    def textvektorer(self, texter):
        return [normera(v) for v in self.text.embed(texter)]

    def bildvektor(self, bild):
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            f.write(bild)
            f.flush()
            return normera(next(iter(self.bild.embed([f.name]))))

    def exempelvektor(self, vag):
        if vag not in self.exempel:
            try:
                with open(os.path.join(MAPP, vag), "rb") as f:
                    self.exempel[vag] = self.bildvektor(f.read())
            except Exception as e:
                logg("kunde inte läsa inspirationsbilden %s: %s" % (vag, e))
                self.exempel[vag] = None
        return self.exempel[vag]

    def likhet(self, bv, vagar):
        """Likheten med den mest lika av inspirationsbilderna, None om ingen gick att läsa."""
        lik = None
        for vag in vagar:
            ev = self.exempelvektor(vag)
            if ev is not None:
                lik = max(lik or 0.0, skal(bv, ev))
        return lik


def hamta_bild(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read(), (r.headers.get_content_type() or "image/jpeg")


def exempel(s):
    """Alarmets inspirationsbilder (sökvägar i repot)."""
    return [v for v in (s.get("bild_exempel") or []) if isinstance(v, str) and v]


def skal(a, b):
    return sum(x * y for x, y in zip(a, b))


def normera(v):
    v = [float(x) for x in v]
    langd = sum(x * x for x in v) ** 0.5 or 1.0
    return [x / langd for x in v]


def fraga(annons, s):
    def lista(v):
        return ", ".join(v) if isinstance(v, list) else (v or "")
    return (
        "Du hjälper en person som köper begagnade herrkläder på Vinted för att sälja vidare. "
        "Titta på bilden och titeln och avgör om plagget är det som alarmet letar efter.\n\n"
        "Alarm: %s\nSökord: %s\nOrd som ska stå i titeln: %s\nMärken: %s\n\n"
        "Annonsens titel: %s\nMärke enligt annonsen: %s\n\n"
        "passar = true bara om plagget på bilden är rätt sorts plagg för alarmet (till exempel en stickad hoodie "
        "och inte en sweatshirt, eller en fältjacka och inte en skjorta) och det ser ut att vara ett herrplagg. "
        "Är bilden otydlig men titeln stämmer, svara true. "
        "plagg = vad plagget på bilden är, med några ord på svenska. varfor = en kort mening på svenska."
        % (s.get("namn", ""), lista(s.get("sokord")), lista(s.get("maste")), lista(s.get("marke")),
           annons.get("titel", ""), annons.get("marke", ""))
    )
