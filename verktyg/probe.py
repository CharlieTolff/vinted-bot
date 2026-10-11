"""Tillfälligt: provkör märkesbörsen på GitHub."""
import base64, gzip, json, re, sys, time
sys.path.insert(0, ".")
import vinted_bot as vb
import marknad

# Herr-kategorier hos Vinted
v = vb.Vinted()
text = vb.sidans_data(v.hamta(vb.VINTED + "/catalog?catalog_ids[]=2050"))
i = text.find('"catalogTree":')
trad, _ = json.JSONDecoder().raw_decode(text, i + len('"catalogTree":'))
def ga(noder, djup, inne):
    for n in noder:
        inne2 = inne or n.get("id") == 2050
        if inne2 and djup <= 4:
            print("KAT", "  " * djup, n["id"], n["title"])
        ga(n.get("catalogs") or [], djup + 1, inne2)
ga(trad, 0, False)

b = marknad.hamta("https://plick.se/produkter?query=j.lindeberg+cardigan")
bit = b.split('class="listing-card-component"')[1]
print("PLICKKORT", bit[:3000])
print("PLICKPARSE", json.dumps(marknad.plick_kort(b)[:5], ensure_ascii=False))

marknad.kor(tidsgrans=int(sys.argv[1]) if len(sys.argv) > 1 else 600)
d = open("bors.json", "rb").read()
print("BORSSTORLEK", len(d))
print("BORS_START")
s = base64.b64encode(gzip.compress(d)).decode()
for i in range(0, len(s), 4000):
    print(s[i:i+4000])
print("BORS_SLUT")
