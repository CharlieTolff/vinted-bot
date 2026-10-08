# Tillfälligt testskript: hur ser en såld/raderad annons ut hos Vinted?
import json, re, sys, time, urllib.request, urllib.error
sys.path.insert(0, ".")
import vinted_bot as vb
v = vb.Vinted()
v.hamta(vb.VINTED + "/")
for id_ in ["10270115978", "10270179102", "10270115970", "123"]:
    try:
        req = urllib.request.Request(vb.VINTED + "/items/" + id_, headers={"User-Agent": vb.WEBBLASARE, "Accept": "text/html"})
        r = v.oppnare.open(req, timeout=30)
        sida = r.read().decode("utf-8", "replace")
        bitar = re.findall(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)', sida)
        text = "".join(json.loads(b) for b in bitar)
        print("ID", id_, r.status, r.geturl(), len(text))
        for m in list(re.finditer(r'"can_buy"', text))[:1]:
            print("  CTX", text[max(0, m.start()-1500):m.start()+600].replace("\n", " "))
        for ord_ in ["Såld", "sold", "closed", "is_reserved", "status_id", "item_status", "Reserverad"]:
            for m in list(re.finditer(ord_, text))[:2]:
                print("  ORD", ord_, text[max(0, m.start()-120):m.start()+120].replace("\n", " "))
    except urllib.error.HTTPError as e:
        print("ID", id_, "HTTP", e.code, e.geturl())
    time.sleep(2)
