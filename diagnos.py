# Tillfälligt testskript: hitta Vinteds färg-id.
import json, re, sys, urllib.request, urllib.error
sys.path.insert(0, ".")
import vinted_bot as vb
v = vb.Vinted()
v.hamta(vb.VINTED + "/")
for vag in ["/api/v2/colors", "/api/v2/catalog/colors", "/api/v2/item_colors"]:
    try: print("API", vag, json.dumps(v.api(vag), ensure_ascii=False)[:3000])
    except Exception as e: print("API", vag, e)
sida = v.hamta(vb.VINTED + "/catalog?search_text=tr%C3%B6ja&color_ids[]=1")
bitar = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', sida)
text = "".join(json.loads(b) for b in bitar)
for m in re.finditer(r'"(?:hex|colorHex|color_hex)"', text):
    print("HEX", text[max(0, m.start()-200):m.start()+120].replace("\n", " ")); break
for ord_ in ["Svart", "Marinblå", "Vinröd", "Beige"]:
    for m in list(re.finditer(ord_, text))[:3]:
        print("ORD", ord_, text[max(0, m.start()-150):m.start()+100].replace("\n", " "))
