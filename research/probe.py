import json, re, sys, urllib.request, urllib.parse, time, html as H
sys.path.insert(0, ".")
import vinted_bot as vb
UA = vb.WEBBLASARE
def get(url):
    h = {"User-Agent": UA, "Accept": "text/html", "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8"}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return getattr(e, "code", "ERR"), str(e)

v = vb.Vinted()
sida = v.hamta(vb.VINTED + "/catalog?search_text=barbour&catalog_ids[]=2050")
t = vb.sidans_data(sida)
for k in ["total_entries", "totalEntries", "total_pages", "pagination", "created_at", "timestamp"]:
    i = t.find(k); print("VINTED", k, i, t[max(0,i-100):i+200].replace("\n"," ") if i >= 0 else "")
st, b = get(vb.VINTED + "/items/10314966324")
t2 = vb.sidans_data(b) if st == 200 else ""
for k in ["created_at", "updated_at", "last_push_up", "view_count", "favourite_count", "timestamp"]:
    i = t2.find(k); print("ITEM", k, t2[max(0,i-80):i+120] if i >= 0 else "-")

st, b = get("https://www.tradera.com/search?q=barbour%20bedale&itemStatus=Ended")
t = vb.sidans_data(b)
print("TRADERA data len", len(t))
for k in ["Avslutad", "Såld", "itemId", "bidCount", "price", "isSold", "hasBids", "endDate"]:
    i = t.find(k); print("TR", k, t.count(k), t[max(0,i-300):i+500].replace("\n"," ") if i >= 0 else "-")
    print("----")
i = b.find("Avslutad"); print("TR HTML around Avslutad:", re.sub(r"\s+", " ", b[max(0,i-1500):i+300]))

for q in ["vinted+resell", "vinted+tjäna+pengar", "köpa+och+sälja+kläder+vinst", "secondhand+resell+märken"]:
    st, b = get("https://www.flashback.org/sok/?query=" + q)
    titles = re.findall(r'<a[^>]+href="(/t\d+)"[^>]*>([^<]+)</a>', b)
    print("FLASHBACK", q, st, titles[:25])
    if not titles: print(re.sub(r"\s+"," ",b[:1500]))
st, b = get("https://plick.se/profiler/barelicloset")
print("PLICK", re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", b))[:6000])
st, b = get("https://www.tiktok.com/discover/best-brands-to-resell-on-vinted")
txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", b))
print("TIKTOK", txt[:5000])
