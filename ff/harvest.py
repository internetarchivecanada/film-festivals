"""Harvest every film festival on Wikidata (instances of film festival Q220505 and its subclasses).

    python3 -m ff.harvest        -> raw/items.json (one record per item, all fields as lists)

Step 1 lists items per class; step 2 fetches details in batches of 300 items with VALUES.
Wikidata data is CC0.
"""
import json
import time
from pathlib import Path

import requests

EP = "https://query.wikidata.org/sparql"
UA = "WaybackLabs-FilmFestivalFinder/0.1 (Internet Archive research)"
RAW = Path(__file__).resolve().parent.parent / "raw"
LANGS = "en,mul,fr,es,de,it,pt,nl,pl,ru,uk,cs,sv,da,nb,fi,tr,el,he,ar,fa,hi,bn,ja,ko,zh,id,vi,th,ca,eu,gl,hu,ro,bg,sr,hr,sl,sk,lt,lv,et"
S = requests.Session()
S.headers["User-Agent"] = UA


def sparql(q, tries=5):
    for i in range(tries):
        try:
            r = S.post(EP, data={"query": q, "format": "json"}, timeout=180)
            if r.status_code == 200:
                return r.json()["results"]["bindings"]
            print("  HTTP", r.status_code, flush=True)
        except requests.RequestException as e:
            print("  err", e, flush=True)
        time.sleep(15 * (i + 1))
    raise RuntimeError("SPARQL failed")


def qid(v):
    return v.rsplit("/", 1)[1]


def classes():
    b = sparql("SELECT ?c WHERE { ?c wdt:P279* wd:Q220505 }")
    return [qid(x["c"]["value"]) for x in b]


DETAIL = """
SELECT ?i ?p ?v ?vLabel WHERE {
  VALUES ?i { %s }
  {
    VALUES ?p { wdt:P17 wdt:P131 wdt:P276 wdt:P159 wdt:P136 wdt:P921 wdt:P664 wdt:P31 wdt:P361 wdt:P179 wdt:P155 wdt:P156 }
    ?i ?p ?v .
    SERVICE wikibase:label { bd:serviceParam wikibase:language "%s". }
  } UNION {
    VALUES ?p { wdt:P856 wdt:P625 wdt:P571 wdt:P576 wdt:P580 wdt:P582 wdt:P585 wdt:P18 wdt:P154 wdt:P2002 wdt:P2013 wdt:P1813 }
    ?i ?p ?v .
  } UNION {
    ?i rdfs:label ?v . BIND("label" AS ?p)
  } UNION {
    ?i schema:description ?v . FILTER(LANG(?v) = "en") BIND("desc" AS ?p)
  } UNION {
    ?i wikibase:sitelinks ?v . BIND("sitelinks" AS ?p)
  } UNION {
    ?v schema:about ?i ; schema:isPartOf <https://en.wikipedia.org/> . BIND("enwiki" AS ?p)
  } UNION {
    ?e wdt:P179|wdt:P361 ?i . BIND("edition" AS ?p) BIND(?e AS ?v)
  }
}"""

# Coordinates of the place, when the festival item has none of its own.
PLACECOORD = """
SELECT ?i ?c WHERE { VALUES ?i { %s } ?i wdt:P131|wdt:P276|wdt:P159 ?pl . ?pl wdt:P625 ?c . }"""


def main():
    RAW.mkdir(exist_ok=True)
    cls = classes()
    print(len(cls), "classes", flush=True)
    items = {}
    for c in cls:
        for x in sparql(f"SELECT ?i WHERE {{ ?i wdt:P31 wd:{c} }}"):
            items.setdefault(qid(x["i"]["value"]), {"_class": []})["_class"].append(c)
        time.sleep(0.5)
    print(len(items), "items", flush=True)
    ids = sorted(items)
    for k in range(0, len(ids), 300):
        chunk = ids[k:k + 300]
        vals = " ".join("wd:" + i for i in chunk)
        for r in sparql(DETAIL % (vals, LANGS)):
            i = qid(r["i"]["value"])
            p = r["p"]["value"]
            p = p.rsplit("/", 1)[1] if p.startswith("http") else p
            v = r["v"]
            rec = {"v": v["value"]}
            if "xml:lang" in v:
                rec["lang"] = v["xml:lang"]
            if "vLabel" in r:
                rec["label"] = r["vLabel"]["value"]
            items[i].setdefault(p, [])
            if rec not in items[i][p]:
                items[i][p].append(rec)
        for r in sparql(PLACECOORD % vals):
            items[qid(r["i"]["value"])].setdefault("placecoord", []).append({"v": r["c"]["value"]})
        print(f"{k + len(chunk)}/{len(ids)}", flush=True)
        time.sleep(1)
    (RAW / "items.json").write_text(json.dumps(items))
    print("done", flush=True)


if __name__ == "__main__":
    main()
