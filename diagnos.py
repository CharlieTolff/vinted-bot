# Tillfälligt testskript: kör nya botten mot riktiga Vinted, utan Telegram.
import json, os, sys, tempfile
sys.path.insert(0, ".")
import vinted_bot as vb
d = tempfile.mkdtemp()
vb.SEDDA_FIL, vb.TRAFFAR_FIL, vb.MINNE_FIL = [os.path.join(d, x) for x in ("s.json", "t.json", "m.json")]
alarm = [
    {"namn": "Nudie herr", "sokord": "nudie jeans", "marke": "Nudie", "kon": "herr", "kategorier": ["klader"], "lander": ["SE", "DK", "FI"], "saljpris": 450, "maxpris": 400, "telegram": "alla"},
    {"namn": "Ralph dam", "sokord": "ralph lauren", "kon": "dam", "skick": ["Mycket bra", "Ny utan prislapp"], "telegram": "alla"},
]
v = vb.Vinted()
sedda, tl, minne = {}, {}, {"priser": {}, "saljare": {}, "marken": {}, "sokningar": {}}
vb.en_runda(v, {"telegram_token": "", "telegram_chat_id": ""}, alarm, sedda, tl, minne)
print("URL", minne["sokningar"]); print("MÄRKEN", minne["marken"])
for n, x in tl.items():
    print("==", n, "vanligt", x["vanligt_pris"], "visas", len(x["annonser"]))
    for a in x["annonser"][:8]:
        print("  ", a["pris"], a["titel"][:40], "|", a["marke"], "|", a["storlek"], a["skick"], "|", a.get("saljare"), "vinst", a.get("vinst"), "kap", a["kap"])
# Andra rundan: låtsas att några annonser är nya
for n in sedda: sedda[n] = sedda[n][5:]
vb.en_runda(v, {"telegram_token": "", "telegram_chat_id": ""}, alarm, sedda, tl, minne)
print("SÄLJARE KOLLADE", len(minne["saljare"]))
