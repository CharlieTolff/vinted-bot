import json, sys, time
sys.path.insert(0, ".")
import research.runda2 as r2
r2.R = {
 "J.Lindeberg": (["j.lindeberg", "j lindeberg"], [["lindeberg"]], ("", ["J.Lindeberg"], "klader")),
 "Massimo Dutti herr": (["massimo dutti herr"], [["massimo dutti"]], ("", ["Massimo Dutti"], "klader")),
 "A.P.C.": (["a.p.c.", "apc jeans", "apc skjorta"], [["a.p.c", "apc"]], ("", ["A.P.C."], "klader")),
 "Dondup": (["dondup"], [["dondup"]], ("", ["Dondup"], "klader")),
 "Duno": (["duno jacka"], [["duno"]], ("", ["Duno"], "klader")),
 "Mason's": (["mason's", "masons byxor"], [["mason"]], ("", ["Mason's"], "klader")),
 "Woolrich": (["woolrich"], [["woolrich"]], ("", ["Woolrich"], "klader")),
 "Gaastra": (["gaastra"], [["gaastra"]], ("", ["Gaastra"], "klader")),
 "Filippa K herr": (["filippa k herr"], [["filippa"]], ("", ["Filippa K"], "klader")),
 "Norse Projects": (["norse projects"], [["norse"]], ("", ["Norse Projects"], "klader")),
 "Sail Racing": (["sail racing"], [["sail racing"]], ("", ["Sail Racing"], "klader")),
 "Vaxjacka utan märke": (["vaxjacka"], [["vax", "wax"]], ("vaxjacka", [], "klader")),
}
_orig_dump = json.dump
def main():
    import builtins
    real_open = builtins.open
    def fake_open(p, *a, **k):
        if p == "research/runda2.json":
            p = "research/runda4.json"
        return real_open(p, *a, **k)
    builtins.open = fake_open
    # hoppa över forum-delarna: begränsa till marknadsdata
    r2.main()
if __name__ == "__main__":
    main()
