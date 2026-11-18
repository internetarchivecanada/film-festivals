"""raw/items.json + raw/labels.json -> data/festivals.json (one clean record per festival).

    python3 -m ff.model
"""
import json
import re
import urllib.parse
from collections import Counter
from pathlib import Path

from .harvest import RAW, qid

ROOT = RAW.parent
ALT_LANGS = ["mul", "en", "fr", "es", "de", "it", "pt", "nl", "pl", "ca", "sv", "cs", "tr", "ru", "uk", "ja", "zh", "ko", "ar", "he", "fa", "hi", "el"]
NAME_LANGS = ["en", "mul", "fr", "es", "de", "it", "pt", "nl", "pl", "ru", "ja", "zh", "ko"]
GENERIC = {"Q220505", "Q65255256", "Q123980018"}          # film festival, "International Film Festival", annual
# ccTLDs that are mostly used as generic names, so they say nothing about the festival's country
VANITY = {"tv", "fm", "io", "co", "me", "ws", "to", "ly", "am", "la", "cc", "ai", "gg", "is", "it", "do", "nu", "tk", "sh", "ag", "vc"}
SOCIAL = re.compile(r"(facebook|instagram|twitter|x)\.com/", re.I)
POINT = re.compile(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)")


def year(s):
    m = re.match(r"^\+?(-?\d{1,4})-", s or "")
    return int(m.group(1)) if m else None


def vals(it, p):
    return [x["v"] for x in it.get(p, [])]


def ents(it, p):
    return [qid(v) for v in vals(it, p) if v.startswith("http://www.wikidata.org/entity/Q")]


def best_name(it):
    by = {}
    for x in it.get("label", []):
        by.setdefault(x.get("lang", ""), x["v"])
    for l in NAME_LANGS:
        if l in by:
            return by[l], by
    return (next(iter(by.values())) if by else None), by


def commons(fn, width):
    return ("https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(fn.rsplit("/", 1)[-1])
            + f"?width={width}")


def main():
    items = json.loads((RAW / "items.json").read_text())
    L = json.loads((RAW / "labels.json").read_text())
    iso2country = {}
    for e, d in L.items():
        if d.get("iso") and d.get("label"):
            iso2country[d["iso"].lower()] = (e, d["label"])
    iso2country["uk"] = iso2country.get("gb")

    def lab(e):
        return (L.get(e) or {}).get("label") or e

    fest = {}
    for i, it in items.items():
        name, names = best_name(it)
        if not name:
            continue
        sites = vals(it, "P856")
        site = next((s for s in sites if not SOCIAL.search(s)), sites[0] if sites else None)
        host = urllib.parse.urlsplit(site).hostname.lower().removeprefix("www.") if site else None
        places = ents(it, "P131") + ents(it, "P276") + ents(it, "P159")
        place = next((lab(p) for p in places if lab(p) != p), None)
        countries = [lab(c) for c in ents(it, "P17")]
        cfrom = "wikidata" if countries else None
        if not countries:
            for p in places:
                if L.get(p, {}).get("countryLabel"):
                    countries, cfrom = [L[p]["countryLabel"]], "place"
                    break
        if not countries and host:
            tld = host.rsplit(".", 1)[-1]
            if tld not in VANITY and tld in iso2country and iso2country[tld]:
                countries, cfrom = [iso2country[tld][1]], "web address"
        coord = None
        for v in vals(it, "P625") + vals(it, "placecoord") + [L.get(p, {}).get("coord") for p in places if L.get(p, {}).get("coord")]:
            m = POINT.match(v or "")
            if m:
                coord = [round(float(m.group(2)), 4), round(float(m.group(1)), 4)]
                break
        founded = min([y for y in map(year, vals(it, "P571") + vals(it, "P580")) if y] or [None]) \
            if (vals(it, "P571") or vals(it, "P580")) else None
        ended = min([y for y in map(year, vals(it, "P576") + vals(it, "P582")) if y] or [None]) \
            if (vals(it, "P576") or vals(it, "P582")) else None
        types = sorted({lab(c) for c in it["_class"] if c not in GENERIC}
                       | {lab(c) for c in ents(it, "P136") + ents(it, "P921")})
        types = [t for t in types if not re.match(r"^Q\d+$", t)]
        parents = [p for p in ents(it, "P361") + ents(it, "P179") if p in items]
        # Other names: the festival's short name, then names in the main languages, in that order.
        alt = []
        for n in vals(it, "P1813") + [names[l] for l in ALT_LANGS if l in names]:
            if n.lower() != name.lower() and n.lower() not in [a.lower() for a in alt]:
                alt.append(n)
        fest[i] = {
            "id": i, "name": name, "alt": alt[:4], "desc": (vals(it, "desc") or [None])[0],
            "country": countries[0] if countries else None, "country_from": cfrom,
            "place": place, "coord": coord, "founded": founded, "ended": ended,
            "types": types, "site": site, "host": host,
            "facebook": (vals(it, "P2013") or [None])[0], "twitter": (vals(it, "P2002") or [None])[0],
            "image": commons(vals(it, "P18")[0], 640) if vals(it, "P18") else None,
            "logo": commons(vals(it, "P154")[0], 240) if vals(it, "P154") else None,
            "enwiki": (vals(it, "enwiki") or [None])[0],
            "sitelinks": int((vals(it, "sitelinks") or ["0"])[0]),
            "editions": sorted({qid(v) for v in vals(it, "edition")}),
            "parent": parents[0] if parents else None,
            "organizer": [lab(o) for o in ents(it, "P664")][:3],
            "short": (vals(it, "P1813") or [None])[0],
        }
    # Edition items (part of another festival in the set) are listed under their parent.
    for f in fest.values():
        f["edition_items"] = [{"id": e, "name": fest[e]["name"], "year": fest[e]["founded"]}
                              for e in f["editions"] if e in fest]
    out = {"festivals": fest}
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "festivals.json").write_text(json.dumps(out, ensure_ascii=False))
    c = Counter(f["country_from"] for f in fest.values())
    print(len(fest), "festivals; country from", dict(c), "; mapped", sum(1 for f in fest.values() if f["coord"]),
          "; site", sum(1 for f in fest.values() if f["site"]), "; editions-as-items",
          sum(1 for f in fest.values() if f["parent"]))
    print(Counter(t for f in fest.values() for t in f["types"]).most_common(25))
    print(Counter(f["country"] for f in fest.values()).most_common(15))


if __name__ == "__main__":
    main()
