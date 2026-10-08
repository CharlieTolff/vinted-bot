# Tillfälligt testskript: kolla finns_kvar mot riktiga annonser.
import json, sys, time, urllib.request
sys.path.insert(0, ".")
import vinted_bot as vb
t = json.load(urllib.request.urlopen("https://charlietolff.github.io/vinted-bot/traffar.json"))
alla = [a for d in t.values() for a in d.get("annonser", [])]
print("annonser på hemsidan:", len(alla), "unika:", len({a["id"] for a in alla}))
v = vb.Vinted()
start = time.time()
for id_ in ["10270115978", "123"] + [str(a["id"]) for a in alla[-30:]]:
    print(id_, v.finns_kvar(id_), flush=True)
    time.sleep(1.5)
print("tid", round(time.time() - start))
