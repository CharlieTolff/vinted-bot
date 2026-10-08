# Tillfälligt testskript: hur ser en såld/raderad annons ut hos Vinted?
import json, re, sys, urllib.request, urllib.error
sys.path.insert(0, ".")
import vinted_bot as vb
t = json.load(urllib.request.urlopen("https://charlietolff.github.io/vinted-bot/traffar.json"))
ids = []
for namn, d in t.items():
    for a in d.get("annonser", [])[-6:]:
        ids.append((a["id"], a["lank"]))
ids = ids[:40]
v = vb.Vinted()
v.hamta(vb.VINTED + "/")
for i, (id_, lank) in enumerate(ids):
    rad = [str(id_)]
    for vag in ["/api/v2/items/%s" % id_, "/api/v2/items/%s/details" % id_]:
        try:
            j = v.api(vag)
            it = j.get("item") or {}
            rad.append("API%s ok keys=%s sold=%s closed=%s hidden=%s status=%s can_buy=%s" % (vag[-8:], list(j)[:4], it.get("is_sold"), it.get("is_closed"), it.get("is_hidden"), it.get("item_closing_action"), it.get("can_buy")))
        except urllib.error.HTTPError as e:
            rad.append("API%s %s" % (vag[-8:], e.code))
        except Exception as e:
            rad.append("API err %s" % e)
    try:
        req = urllib.request.Request(lank, headers={"User-Agent": vb.WEBBLASARE, "Accept": "text/html"})
        r = v.oppnare.open(req, timeout=30)
        sida = r.read().decode("utf-8", "replace")
        bitar = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', sida)
        text = "".join(json.loads(b) for b in bitar) or sida
        flaggor = {k: re.findall(r'"%s":(true|false|null|"[^"]*")' % k, text)[:2] for k in ["is_closed", "is_sold", "is_hidden", "is_reserved", "item_closing_action", "can_buy", "is_visible", "transaction_permitted"]}
        rad.append("HTML %s url=%s %s" % (r.status, r.geturl()[-40:], flaggor))
        if i < 2: rad.append("SAMPLE " + text[:200].replace("\n", " "))
    except urllib.error.HTTPError as e:
        rad.append("HTML %s" % e.code)
    print(" | ".join(rad), flush=True)
