"""Bildkollen: en AI tittar på annonsens bild och säger om plagget verkligen passar alarmet.

Utan nyckel (ANTHROPIC_API_KEY) gör den ingenting, och boten fungerar som förut.
Svaren sparas per annons, så samma bild granskas bara en gång.
"""
import base64
import json
import os
import time
import urllib.request

MODELL = os.environ.get("BILD_MODELL", "claude-opus-5-5")
PER_RUNDA = int(os.environ.get("BILD_PER_RUNDA", "15"))  # högst så många bilder per runda, så kostnaden hålls nere
SPARA_DAGAR = 30

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


class Bildkoll:
    def __init__(self, minne):
        self.minne = minne.setdefault("bilder", {})
        self.kvar = PER_RUNDA
        self.klient = None
        if os.environ.get("ANTHROPIC_API_KEY"):
            try:
                import anthropic
                self.klient = anthropic.Anthropic(max_retries=1, timeout=60)
            except ImportError:
                print("Bildkollen: paketet anthropic saknas, hoppar över bilderna.")

    @property
    def pa(self):
        return self.klient is not None

    def svar(self, annons):
        """True/False om annonsen redan är granskad, annars None."""
        v = self.minne.get(str(annons["id"]))
        return v[0] if v else None

    def passar(self, annons, s, reserv=0):
        """True = passar, False = fel plagg, None = inte granskad (ingen nyckel, slut på rundans kvot eller fel).
        reserv = så många granskningar som ska sparas till nya träffar i rundans övriga alarm."""
        tidigare = self.svar(annons)
        if tidigare is not None or not self.pa or not annons.get("bild") or self.kvar <= reserv:
            return tidigare
        self.kvar -= 1
        try:
            req = urllib.request.Request(annons["bild"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                bild, typ = r.read(), (r.headers.get_content_type() or "image/jpeg")
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
                return None
            data = json.loads(next(b.text for b in svar.content if b.type == "text"))
        except Exception as e:  # nätet, API:t eller bilden krånglar: låt annonsen vara som förut och försök igen nästa runda
            print("Bildkollen: kunde inte granska annons %s: %s" % (annons["id"], e))
            return None
        self.minne[str(annons["id"])] = [bool(data["passar"]), data["plagg"][:80], round(time.time())]
        if not data["passar"]:
            print("Bildkollen: '%s' passar inte (%s: %s)" % (annons["titel"][:60], data["plagg"][:40], data["varfor"][:80]))
        return bool(data["passar"])

    def stada(self):
        grans = time.time() - SPARA_DAGAR * 86400
        for k in [k for k, v in self.minne.items() if v[2] < grans]:
            del self.minne[k]


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
