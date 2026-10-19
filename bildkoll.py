"""Bildkollen: tittar på annonsens bild och säger om plagget verkligen passar alarmet.

Två sätt, det första som finns används:
- Claude (bäst, kostar per bild): när hemligheten ANTHROPIC_API_KEY finns.
- CLIP (gratis): en öppen bildmodell som körs direkt på GitHub. Den jämför bilden med alarmets
  "bild_ja" (t.ex. "a knitted hoodie") och "bild_nej" (t.ex. "a cotton sweatshirt") i sokningar.json.
Finns inget av dem gör den ingenting, och boten fungerar som förut.
Svaren sparas per annons, så samma bild granskas bara en gång.
"""
import base64
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
VERSION = {"claude": "claude-1", "clip": "clip-1"}  # nytt nummer = gamla svar granskas om

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
                from fastembed import ImageEmbedding, TextEmbedding
                self.clip = (ImageEmbedding(model_name=CLIP_BILD, cache_dir=CLIP_MAPP),
                             TextEmbedding(model_name=CLIP_TEXT, cache_dir=CLIP_MAPP))
                self.satt = "clip"
            except Exception as e:  # paketet saknas eller modellen gick inte att hämta
                logg("CLIP gick inte att starta (%s), hoppar över bilderna." % e)
        self.kvar = int(os.environ.get("BILD_PER_RUNDA", "15" if self.satt == "claude" else "40"))

    @property
    def pa(self):
        return self.satt is not None

    def svar(self, annons):
        """True/False om annonsen redan är granskad med det här sättet, annars None."""
        v = self.minne.get(str(annons["id"]))
        if not v or (self.satt and (len(v) < 4 or v[3] != VERSION[self.satt])):
            return None
        return v[0]

    def passar(self, annons, s, reserv=0):
        """True = passar, False = fel plagg, None = inte granskad (avstängd, slut på rundans kvot eller fel).
        reserv = så många granskningar som ska sparas till nya träffar i rundans övriga alarm."""
        tidigare = self.svar(annons)
        if tidigare is not None or not self.pa or not annons.get("bild") or self.kvar <= reserv:
            return tidigare
        if self.satt == "clip" and not s.get("bild_ja"):
            return None  # alarmet har inga bildbeskrivningar
        self.kvar -= 1
        try:
            req = urllib.request.Request(annons["bild"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                bild, typ = r.read(), (r.headers.get_content_type() or "image/jpeg")
            ok, plagg, varfor = (self.fraga_claude if self.satt == "claude" else self.fraga_clip)(bild, typ, annons, s)
        except Exception as e:  # nätet, tjänsten eller bilden krånglar: låt annonsen vara som förut och försök igen nästa runda
            logg("kunde inte granska annons %s: %s" % (annons["id"], e))
            return None
        if ok is None:
            return None
        self.minne[str(annons["id"])] = [ok, plagg[:80], round(time.time()), VERSION[self.satt]]
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
        ja, nej = list(s["bild_ja"]), list(s.get("bild_nej") or [])
        etiketter = ja + nej
        nyckel = "\n".join(etiketter)
        if nyckel not in self.texter:
            self.texter[nyckel] = [normera(v) for v in self.clip[1].embed(["a photo of " + t for t in etiketter])]
        with tempfile.NamedTemporaryFile(suffix=".jpg") as f:
            f.write(bild)
            f.flush()
            bv = normera(next(iter(self.clip[0].embed([f.name]))))
        # Samma räkning som CLIP själv: likhet gånger 100, sedan softmax.
        likhet = [100 * sum(a * b for a, b in zip(bv, t)) for t in self.texter[nyckel]]
        topp = max(likhet)
        vikt = [pow(2.718281828, x - topp) for x in likhet]
        summa = sum(vikt)
        andel_ja = sum(vikt[:len(ja)]) / summa
        basta = max(range(len(etiketter)), key=lambda i: likhet[i])
        return andel_ja >= CLIP_ANDEL, etiketter[basta], ", %d %% rätt sorts plagg" % round(100 * andel_ja)

    def stada(self):
        grans = time.time() - SPARA_DAGAR * 86400
        for k in [k for k, v in self.minne.items() if v[2] < grans]:
            del self.minne[k]


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
