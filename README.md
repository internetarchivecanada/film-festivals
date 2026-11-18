# Film Festival Finder

Find any of the ~16,000 film festivals on Wikidata, with each festival's website and the years its homepage was
captured by the Wayback Machine. Search by name, place or word; filter by country, kind, founding decade and
archive status; browse a world map.

Live: https://wayback-labs.sf.archive.org/film-festivals/ (Wayback Machine Labs studio, static tile `film-festivals`).

It grew out of the conference inventory pilot (internetarchivecanada/conference-inventory) and the
Double Exposure Explorer.

## Sources

- **Wikidata** (CC0): every item that is an instance of film festival (Q220505) or one of its subclasses
  (short film festival, documentary film festival, LGBT film festival…). Names, country, place, coordinates,
  founding/end dates, official website, social accounts, image/logo, English Wikipedia article, editions.
- **Country** comes from Wikidata, else from the festival's place, else is guessed from a country web address
  (`.it`, `.ca`; vanity domains such as `.tv`, `.io`, `.co` are ignored). Guesses are labelled on the page.
- **Kinds** are Wikidata types/genres plus keyword rules on the festival's names in several languages (`ff/site.py`, `KINDS`).
- **Wayback Machine**: years in which each website's homepage has a capture, from the public CDX API (`ff/wayback.py`).

## Build

```
python3 -m ff.harvest      # Wikidata -> raw/items.json        (~5 min)
python3 -m ff.labels       # referenced entities -> raw/labels.json
python3 -m ff.model        # -> data/festivals.json
python3 ff/wayback.py data/festivals.json raw/wayback.jsonl     # resumable, ~2 s/site; run on the studio
python3 -m ff.site         # -> public/ (committed)
python3 cover/make.py      # tile cover -> cover/film-festivals-cover.jpg
```

## Deploy

The studio dir `/opt/services/film-festivals` is a checkout of this repo (remote `canada`); Caddy serves `public/`.
Rebuild and commit `public/`, push `main`, then:

```
ssh wayback-labs.sf.archive.org sudo /opt/services/_scripts/deploy-tile plan film-festivals --expect "$(git rev-parse HEAD)"
ssh wayback-labs.sf.archive.org sudo /opt/services/_scripts/deploy-tile deploy film-festivals --expect "$(git rev-parse HEAD)"
```

The landing-page tile lives in internetarchivecanada/waybacklabs (`tiles/film-festivals.menu`, `covers/film-festivals-cover.jpg`).
