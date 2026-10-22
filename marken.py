"""Märkesnamn: samma märke ska alltid heta samma sak, oavsett hur säljaren skrev det.

Vinted har t.ex. "Ralph Lauren", "Polo Ralph Lauren" och "RALPH Ralph Lauren" som olika märken, och på Tradera
står märket ofta bara i titeln ("Moncler svart dunjacka"). Här slås varianterna ihop till ett namn, så att
börsen räknar rätt.

- kanon(namn): ett märkesnamn som säljaren valt (Vinted, Tradera, Plick) -> det gemensamma namnet.
- i_titel(titel, extra): letar upp ett känt märke i en annonstitel.
- UTAN_MARKE: namn som betyder "inget märke" (Vinted visar t.ex. "Vintage Dressing" för omärkta plagg).
- DAM: märken som bara gör damkläder. De räknas inte i herrkategorierna.
"""
import re
import unicodedata

# Gemensamt namn: varianter (skrivs som de brukar stå, jämförelsen bryr sig inte om stora bokstäver,
# punkter eller accenter). Varianter som är vanliga ord ("polo", "only") står inte med, så att en
# "polotröja" inte blir Ralph Lauren.
MARKEN = {
    # Stora familjer där Vinted har många varianter
    "Ralph Lauren": ["Polo Ralph Lauren", "Polo by Ralph Lauren", "Ralph Lauren Sport", "Polo Sport",
                     "Polo Sport Ralph Lauren", "RALPH Ralph Lauren", "Lauren Ralph Lauren", "Polo Jeans",
                     "Denim & Supply Ralph Lauren", "Polo Golf", "RLX", "Polo RL", "Ralph Lauren Golf"],
    "Chaps": ["Chaps Ralph Lauren"],
    "RRL": ["Double RL", "RRL Ralph Lauren"],
    "Ralph Lauren Purple Label": ["Purple Label"],
    "Hugo Boss": ["BOSS", "Boss Hugo Boss", "BOSS Hugo Boss", "Boss Orange", "Boss Black", "Boss Green", "HUGO",
                  "HUGO Hugo Boss", "Hugo Red", "BOSS Orange", "BOSS Black", "BOSS Green"],
    "Levi's": ["Levis", "Levi Strauss", "Levi Strauss & Co.", "Levi Strauss & Co", "Levi's Red Tab", "Levi’s",
               "Levi's Made & Crafted", "Levis Made & Crafted", "Levi's Silver Tab", "Levi's Engineered"],
    "Levi's Vintage Clothing": ["LVC", "Levis Vintage Clothing"],
    "Tommy Hilfiger": ["Hilfiger", "Hilfiger Denim", "Tommy Hilfiger Denim", "Tommy Hilfiger Golf"],
    "Tommy Jeans": ["Tommy Jeans Denim"],
    "Calvin Klein": ["Calvin Klein Jeans", "CK Calvin Klein", "Calvin Klein Performance"],
    "Emporio Armani": ["EA7", "EA7 Emporio Armani"],
    "Armani Exchange": ["A|X Armani Exchange", "AX Armani Exchange"],
    "Giorgio Armani": [],
    "Armani Jeans": [],
    "GANT": ["Gant", "GANT Rugger", "Gant Rugger", "Gant Diamond G"],
    "Jack & Jones": ["Jack and Jones", "Jack&Jones", "Jack & Jones Premium", "Jack & Jones Originals", "Jack & Jones Core",
                     "JACK & JONES PREMIUM", "Premium by Jack & Jones", "Jack & Jones Vintage", "Jack & Jones Tech"],
    "Selected Homme": ["Selected", "SLHSelected"],
    "Only & Sons": ["Only and Sons", "ONLY & SONS"],
    "H&M": ["H & M", "HM", "H&M Divided", "Divided", "H&M L.O.G.G", "LOGG", "H&M Premium", "H&M Conscious", "H&M Studio"],
    "Zara": ["Zara Man", "Zara Men", "ZARA MAN"],
    "Massimo Dutti": [],
    "COS": [],
    "Arket": [],
    "Weekday": [],
    "Uniqlo": ["Uniqlo U"],
    "Dressmann": [],
    "Lager 157": [],
    "KappAhl": ["Kappahl"],
    "Lindbergh": [],
    "Mango": ["Mango Man"],
    "Pull & Bear": ["Pull and Bear", "Pull&Bear"],
    "Bershka": [],
    "Reserved": [],
    "Cropp": [],
    "House": [],
    "4F": [],
    "Big Star": [],
    "Vistula": [],
    "Wólczanka": [],
    "Esprit": [],
    "s.Oliver": [],
    "Tom Tailor": [],
    "Mustang": [],
    "Next": [],
    "Primark": [],
    "Shein": [],
    "Cubus": [],
    "Clockhouse": [],
    "Livergy": [],
    "Celio": [],
    "Springfield": [],
    "Jules": [],
    "Burton Menswear": [],
    "River Island": [],
    "ASOS": ["ASOS Design"],
    "Topman": [],
    "Gap": [],
    "Banana Republic": [],
    "J.Crew": ["J Crew"],
    "Abercrombie & Fitch": ["Abercrombie", "Abercrombie and Fitch", "A&F"],
    "Hollister": ["Hollister Co."],
    "American Eagle": ["American Eagle Outfitters"],
    "Superdry": ["Super Dry"],
    "Lyle & Scott": ["Lyle and Scott"],
    "Fred Perry": [],
    "Ben Sherman": [],
    "Lacoste": ["Lacoste Live", "Lacoste Sport"],
    "Fila": [],
    "Champion": [],
    "Kappa": [],
    "Ellesse": [],
    "Sergio Tacchini": [],
    "Umbro": [],
    "Le Coq Sportif": [],
    "Björn Borg": [],
    "Napapijri": [],
    "Aeronautica Militare": [],
    "Paul & Shark": ["Paul and Shark"],
    "North Sails": [],
    "Gaastra": [],
    "Henri Lloyd": [],
    "Musto": [],
    "Helly Hansen": ["HH"],
    "Sail Racing": [],
    "Peak Performance": [],
    "J.Lindeberg": ["J Lindeberg", "J. Lindeberg", "JLindeberg", "J.LINDEBERG"],
    "Morris": ["Morris Stockholm", "Morris Heritage", "Morris Lady"],
    "Oscar Jacobson": [],
    "Tiger of Sweden": [],
    "Filippa K": [],
    "Acne Studios": ["Acne", "Acne Jeans"],
    "Our Legacy": [],
    "Whyred": [],
    "Hope": ["Hope Stockholm"],
    "Eton": [],
    "Stenströms": [],
    "A Day's March": ["A Days March", "ADM"],
    "Asket": [],
    "Sandqvist": [],
    "Nudie Jeans": ["Nudie", "Nudie Jeans Co", "Nudie Jeans Co."],
    "Dr. Denim": ["Dr Denim"],
    "Cheap Monday": [],
    "BLK DNM": [],
    "Neuw": ["Neuw Denim"],
    "Velour": ["Velour by Nostalgi"],
    "Brothers": [],
    "John Henric": [],
    "Riley": [],
    "These Glory Days": [],
    "Knowledge Cotton Apparel": ["KnowledgeCotton Apparel", "Knowledge Cotton", "KnowledgeCottonApparel"],
    "Woodbird": [],
    "Norse Projects": [],
    "Wood Wood": [],
    "Samsøe Samsøe": ["Samsoe Samsoe", "Samsøe & Samsøe", "Samsoe & Samsoe", "Samsøe"],
    "Les Deux": [],
    "NN07": ["No Nationality 07", "No Nationality"],
    "Mads Nørgaard": ["Mads Norgaard"],
    "Soulland": [],
    "Han Kjøbenhavn": ["Han Kjobenhavn"],
    "Holzweiler": [],
    "Matinique": [],
    "Sand Copenhagen": [],
    "Libertine-Libertine": ["Libertine Libertine"],
    "Fjällräven": ["Fjallraven"],
    "Haglöfs": ["Haglofs"],
    "Houdini": ["Houdini Sportswear"],
    "Norrøna": ["Norrona"],
    "Klättermusen": ["Klattermusen"],
    "Tretorn": [],
    "Didriksons": [],
    "Rains": [],
    "Stutterheim": [],
    "The North Face": ["North Face", "TNF"],
    "Patagonia": [],
    "Arc'teryx": ["Arcteryx", "Arc teryx"],
    "Mammut": [],
    "Columbia": ["Columbia Sportswear"],
    "Salomon": [],
    "Canada Goose": [],
    "Moncler": ["Moncler Grenoble"],
    "Woolrich": [],
    "Colmar": [],
    "Parajumpers": [],
    "Mackage": [],
    "Moose Knuckles": [],
    "Nobis": [],
    "Peuterey": [],
    "Herno": [],
    "Save the Duck": [],
    "Pyrenex": [],
    "Duvetica": [],
    "Ciesse Piumini": ["Ciesse"],
    "JOTT": ["Just Over The Top"],
    "Dolomite": [],
    "Barbour": ["Barbour International", "Barbour Beacon"],
    "Belstaff": [],
    "Schott": ["Schott NYC"],
    "Alpha Industries": [],
    "Stone Island": ["Stoneisland", "Stone Island Shadow Project"],
    "C.P. Company": ["CP Company", "C P Company", "CP Co"],
    "Carhartt": ["Carhartt WIP", "Carhartt Work In Progress"],
    "Dickies": [],
    "Stüssy": ["Stussy"],
    "Supreme": [],
    "Palace": [],
    "Off-White": ["Off White"],
    "Represent": [],
    "Fear of God": ["Fear of God Essentials"],
    "Burberry": ["Burberrys", "Burberry London", "Burberry Brit"],
    "Gucci": [],
    "Prada": [],
    "Miu Miu": [],
    "Louis Vuitton": [],
    "Balenciaga": [],
    "Saint Laurent": ["Yves Saint Laurent", "YSL"],
    "Givenchy": [],
    "Valentino": ["Valentino Garavani"],
    "Dior": ["Dior Homme", "Christian Dior"],
    "Versace": ["Versace Jeans", "Versace Jeans Couture", "Versus Versace"],
    "Dolce & Gabbana": ["Dolce and Gabbana", "D&G"],
    "Dsquared2": ["Dsquared", "DSQUARED"],
    "Moschino": [],
    "Kenzo": [],
    "Ami Paris": ["AMI", "Ami Alexandre Mattiussi"],
    "Maison Kitsuné": ["Maison Kitsune"],
    "A.P.C.": ["APC"],
    "Thom Browne": [],
    "Comme des Garçons": ["Comme des Garcons", "CDG", "Comme des Garcons Play"],
    "Paul Smith": ["PS Paul Smith", "PS by Paul Smith"],
    "Ted Baker": [],
    "AllSaints": ["All Saints"],
    "The Kooples": [],
    "Hackett": ["Hackett London"],
    "Brooks Brothers": [],
    "Boggi Milano": ["Boggi"],
    "Suitsupply": ["Suit Supply"],
    "Zegna": ["Ermenegildo Zegna"],
    "Canali": [],
    "Corneliani": [],
    "Boglioli": [],
    "Lardini": [],
    "Brunello Cucinelli": [],
    "Loro Piana": [],
    "Eleventy": [],
    "Aspesi": [],
    "Gran Sasso": [],
    "Drake's": ["Drakes"],
    "Sunspel": [],
    "John Smedley": [],
    "Johnstons of Elgin": [],
    "Alan Paine": [],
    "Margaret Howell": ["MHL", "MHL Margaret Howell"],
    "Lindbergh Black": [],
    "Replay": [],
    "Diesel": [],
    "Pepe Jeans": ["Pepe Jeans London"],
    "G-Star": ["G-Star Raw", "G Star", "Gstar", "G-Star RAW"],
    "Lee": [],
    "Lee Cooper": [],
    "Wrangler": [],
    "Jacob Cohën": ["Jacob Cohen"],
    "Edwin": [],
    "Frame": ["Frame Denim"],
    "Eytys": [],
    "Axel Arigato": [],
    "Common Projects": [],
    "Golden Goose": [],
    "Veja": [],
    "Nike": ["Nike Sportswear", "Nike ACG", "Nike Golf", "Nike SB"],
    "Jordan": ["Air Jordan", "Nike Jordan"],
    "adidas": ["Adidas Originals", "adidas Originals", "Adidas Performance"],
    "New Balance": [],
    "Asics": [],
    "Puma": [],
    "Reebok": [],
    "Vans": [],
    "Converse": [],
    "Hoka": ["Hoka One One"],
    "On Running": ["On Cloud"],
    "Saucony": [],
    "Timberland": [],
    "Dr. Martens": ["Dr Martens", "Doc Martens", "Dr. Marten"],
    "Clarks": ["Clarks Originals"],
    "ECCO": ["Ecco"],
    "Birkenstock": [],
    "UGG": [],
    "Red Wing": ["Red Wing Shoes"],
    "Church's": ["Churchs"],
    "Loake": [],
    "Crockett & Jones": ["Crockett and Jones"],
    "Sebago": [],
    "Skechers": [],
    "Rieker": [],
    "Vagabond": [],
    "Pier One": [],
    "Playboy": [],
    "Myrqvist": [],
    "Cole Haan": [],
    "Guess": [],
    "Michael Kors": [],
}
# Märken som bara gör damkläder: hamnar de i en herrkategori är det fel kategori.
DAM = ["Gina Tricot", "Perfect Jeans", "Vero Moda", "Lindex", "Monki", "Nelly", "NA-KD", "Bik Bok", "Object",
       "Pieces", "Vila", "Y.A.S", "Stradivarius", "& Other Stories", "Ellos", "Josefssons", "Stockh Lm", "Toteme",
       "By Malene Birger", "Twist & Tango", "Odd Molly", "Nly Trend", "Make Way", "Rut & Circle", "Envii"]
# Namn som betyder att det inte finns något märke.
UTAN_MARKE = ["Vintage", "Vintage Dressing", "Vintage Love", "Vintage Lux", "Japan Style", "Okänt", "Okänd",
              "Okänt märke", "Inget märke", "Ingen", "Inget", "Vet ej", "Vet inte", "No name", "Noname", "Unbranded",
              "Utan märke", "Handgjord", "Handmade", "Hemmagjord", "Egen design", "Annat", "Övrigt", "Övriga",
              "Other", "Others", "Unknown", "Brak", "Bez marki", "Ei merkkiä", "Kein Label", "Sans marque",
              "Homemade", "Second hand", "Secondhand", "Basic", "Classic", "Italy", "Made in Italy"]

# Ord som är vanliga i titlar och inte får räknas som märken där (även om någon säljer ett märke med det namnet).
INTE_I_TITEL = {"polo", "only", "next", "house", "hope", "sand", "tiger", "on", "hugo", "frame", "brothers",
                "riley", "edwin", "represent", "palace", "supreme", "guess", "champion", "columbia", "vintage",
                "basic", "classic", "denim", "jeans", "sport", "original", "premium", "selected", "divided", "hm",
                "a f", "apc", "ami", "adm", "hh", "ea7", "cdg", "mhl", "lvc", "tnf", "ysl", "d g", "logg", "kappa",
                "ciesse", "reserved", "big star", "jordan", "lee", "gap", "mango", "jott", "asket", "velour",
                "celio", "jules", "mustang", "playboy", "schott", "frame denim", "nudie", "veja", "converse"}


def nyckel(text):
    """'Samsøe & Samsøe' -> 'samsoe and samsoe', "A Day's March" -> 'a days march', 'J.Lindeberg' -> 'j lindeberg'."""
    t = (text or "").lower().replace("ø", "o").replace("æ", "ae").replace("ß", "ss").replace("&", " and ")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"['’´`]", "", t)
    return " ".join(re.findall(r"[a-z0-9]+", t))


_ALIAS = {}
for _namn, _var in MARKEN.items():
    for _v in [_namn] + _var:
        _ALIAS.setdefault(nyckel(_v), _namn)
_DAM = {nyckel(m) for m in DAM}
_UTAN = {nyckel(m) for m in UTAN_MARKE}
# Till titelsökning: längsta varianten först, så att "Polo Ralph Lauren" går före "Ralph Lauren".
_TITEL = sorted(((" %s " % k, v) for k, v in _ALIAS.items() if k not in INTE_I_TITEL and len(k) >= 3),
                key=lambda p: -len(p[0]))

UTAN = "Utan märke"


def snyggt(namn):
    """Okända märken: 'THESE GLORY DAYS' -> 'These Glory Days', 'arket' -> 'Arket'. Korta förkortningar behålls."""
    namn = re.sub(r"\s+", " ", (namn or "").strip())
    if (namn.isupper() and len(namn) > 4) or namn.islower():
        return " ".join(o if len(o) <= 2 else o[:1].upper() + o[1:].lower() for o in namn.split(" "))
    return namn


def kanon(namn):
    """Säljarens märkesnamn -> det gemensamma namnet. 'Utan märke' för omärkta, None för tomt."""
    k = nyckel(namn)
    if not k:
        return None
    if k in _UTAN:
        return UTAN
    if k in _ALIAS:
        return _ALIAS[k]
    # 'BOSS Hugo Boss Orange' eller 'Polo Sport Ralph Lauren Golf': längsta kända namnet som står i det.
    t = " %s " % k
    for v, m in _TITEL:
        if v in t:
            return m
    return snyggt(namn)


def ar_dam(namn):
    return nyckel(namn) in _DAM


def i_titel(titel, extra=()):
    """Ett känt märke i en annonstitel, eller None. extra = fler märken att leta efter (t.ex. de största på Vinted)."""
    t = " %s " % nyckel(titel)
    for v, m in _TITEL:
        if v in t:
            return m
    for m in sorted(extra, key=lambda x: -len(nyckel(x))):
        k = nyckel(m)
        if len(k) >= 3 and k not in INTE_I_TITEL and k not in _UTAN and " %s " % k in t:
            return kanon(m)
    return None
