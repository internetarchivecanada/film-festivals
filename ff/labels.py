"""Labels (and, for places, country + coordinates) of every entity the festivals point at.

    python3 -m ff.labels     raw/items.json -> raw/labels.json
"""
import json

from .harvest import LANGS, RAW, qid, sparql

PROPS = ("P17", "P131", "P276", "P159", "P136", "P921", "P664", "P31", "P361", "P179", "P155", "P156")

Q = """SELECT ?e ?l ?country ?countryLabel ?coord ?iso WHERE {
  VALUES ?e { %s }
  OPTIONAL { ?e rdfs:label ?l0 FILTER(LANG(?l0) = "en") }
  OPTIONAL { ?e wdt:P17 ?country . }
  OPTIONAL { ?e wdt:P625 ?coord . }
  OPTIONAL { ?e wdt:P297 ?iso . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "%s". ?e rdfs:label ?l . ?country rdfs:label ?countryLabel . }
}"""


def main():
    items = json.loads((RAW / "items.json").read_text())
    ents = set()
    for v in items.values():
        for p in PROPS:
            for x in v.get(p, []):
                if x["v"].startswith("http://www.wikidata.org/entity/Q"):
                    ents.add(qid(x["v"]))
        ents.update(v["_class"])
    ents = sorted(ents)
    out = {}
    for k in range(0, len(ents), 400):
        chunk = ents[k:k + 400]
        for r in sparql(Q % (" ".join("wd:" + e for e in chunk), LANGS)):
            e = qid(r["e"]["value"])
            d = out.setdefault(e, {"label": r.get("l", {}).get("value")})
            if "country" in r:
                d["country"] = qid(r["country"]["value"])
                d["countryLabel"] = r.get("countryLabel", {}).get("value")
            if "coord" in r and "coord" not in d:
                d["coord"] = r["coord"]["value"]
            if "iso" in r:
                d["iso"] = r["iso"]["value"]
        print(f"{k + len(chunk)}/{len(ents)}", flush=True)
    (RAW / "labels.json").write_text(json.dumps(out))


if __name__ == "__main__":
    main()
