"""Which years has the Wayback Machine captured each festival's website homepage?

    python3 ff/wayback.py data/festivals.json raw/wayback.jsonl     (resumable; one line per site)

Public CDX API, one request at a time; backs off on 429.
"""
import json
import sys
import time

import requests

S = requests.Session()
S.headers["User-Agent"] = "WaybackLabs-FilmFestivalFinder/0.1 (Internet Archive research)"


def years(url):
    for i in range(6):
        try:
            r = S.get("https://web.archive.org/cdx/search/cdx",
                      params={"url": url, "fl": "timestamp,statuscode", "collapse": "timestamp:4"}, timeout=90)
            if r.status_code == 200:
                ys = sorted({l[:4] for l in r.text.split()[::2]})
                return [int(y) for y in ys if y.isdigit()]
            if r.status_code in (429, 502, 503, 504):
                time.sleep(30 * (i + 1)); continue
            return None
        except requests.RequestException:
            time.sleep(10 * (i + 1))
    return None


def main(src, out):
    fest = json.load(open(src))["festivals"]
    done = set()
    try:
        for l in open(out):
            done.add(json.loads(l)["id"])
    except FileNotFoundError:
        pass
    todo = sorted((f for f in fest.values() if f["site"] and f["id"] not in done),
                  key=lambda f: -f["sitelinks"])
    with open(out, "a") as fo:
        for k, f in enumerate(todo):
            y = years(f["site"])
            fo.write(json.dumps({"id": f["id"], "site": f["site"], "years": y}) + "\n")
            fo.flush()
            time.sleep(1)
            if k % 200 == 0:
                print(k, "/", len(todo), flush=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
