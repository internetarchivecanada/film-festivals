"""data/festivals.json (+ raw/wayback.jsonl if present) -> public/ (static site, served at /film-festivals/).

    python3 -m ff.site
"""
import hashlib
import html
import json
import re
import shutil
import urllib.parse
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "public"
ASSETS = ROOT / "ff" / "assets"
BASE = "https://wayback-labs.sf.archive.org/film-festivals/"
V = "3"

# Kinds: Wikidata types and genres, plus words in the festival's names (many languages).
KINDS = [
    ("Short film", r"\bshorts?\b|court[s]?[- ]m[ée]trage|\bcorto|cortometra|kurzfilm|\bkurz|krótk|curtas?\b|\bshort film", ["short film"]),
    ("Documentary", r"documentar|\bdocs?\b|dokument|documentaire|non-?fiction", ["documentary"]),
    ("Animation", r"anima[tcz]|trickfilm|cartoon|\banime\b", ["animat"]),
    ("LGBTQ+", r"lgbt|queer|\bgay\b|lesbi|\bpride\b|transgender|\btrans\b|outfest|frameline", ["lgbt", "gay", "lesbian", "transgender"]),
    ("Horror, fantasy & sci-fi", r"horror|terror|fantas|sci-?fi|science fiction|\bgenre\b|zombie|\bcult\b", ["horror", "fantasy", "science fiction", "speculative"]),
    ("Environment & nature", r"environment|\beco\b|ecolog|green|wildlife|nature|climate|mountain|outdoor|\bocean|\bwild\b", ["environment"]),
    ("Human rights", r"human rights|droits de l|derechos humanos|menschenrecht|diritti umani|\brights\b", ["human rights"]),
    ("Women", r"\bwom[ae]n\b|femmes?\b|mujer|frauen|\bdonne\b|feminis|\bgirls?\b", ["women", "feminism"]),
    ("Children & youth", r"child|\bkids?\b|youth|jeune|infantil|kinder|ragazzi|family|\byoung|\bteen", ["children"]),
    ("Students & schools", r"student|school|universit|campus|college|\bfilm school", ["student"]),
    ("Jewish", r"jewish|juif|judío|jüdisch|ebraic|israeli", ["jewish"]),
    ("Indigenous", r"indigenous|\bnative\b|aborigin|first nations|imaginenative|indígena", ["indigenous"]),
    ("Music & dance", r"music|\bdance\b|musique|música|musik|musica", []),
    ("Experimental & art", r"experimental|avant|video ?art|\bart film|underground", []),
    ("Online & mobile", r"\bonline\b|mobile|smartphone|\bphone|virtual|one[- ]minute|\b1[- ]minute|micro", ["online"]),
    ("Faith & spirituality", r"christian|\bfaith|religio|spiritual|catholic|bible|islamic", []),
    ("Comedy", r"comedy|comed|humou?r|\bfunny", ["comedy"]),
    ("African & diaspora", r"\bblack\b|african|\bafro|pan[- ]?african|diaspora", []),
    ("Latin American", r"\blatin|latino|latinoameric|ibero", []),
    ("Asian", r"\basian?\b|asiatic", []),
    ("Disability", r"disabilit|\bdeaf\b|handicap|inclusive|accessib", ["disability"]),
    ("Sport & adventure", r"\bsports?\b|surf|\bski\b|adventure|climb", []),
]
KRX = [(k, re.compile(rx, re.I), t) for k, rx, t in KINDS]


def esc(s):
    return html.escape(str(s or ""), quote=True)


def kinds(f):
    text = " ".join([f["name"]] + f["alt"] + [f.get("desc") or ""])
    tl = " ".join(f["types"]).lower()
    return [k for k, rx, tw in KRX if rx.search(text) or any(w in tl for w in tw)]


def th(f):
    """Thumbnail name made by ff/shots.py on the studio: public/thumbs/<th>.webp, -l.webp and .json."""
    return hashlib.sha1(f["site"].encode()).hexdigest()[:16] if f["site"] else ""


def card(f, rel="../", label=""):
    where = ", ".join(x for x in [f["place"], f["country"]] if x)
    h = th(f)
    img = (f'<img src="{rel}thumbs/{h}.webp" alt="" loading="lazy" width="480" height="300" '
           f'onerror="this.remove()">' if h else "")
    return (f'<li class="card"><a href="{rel}f/{f["id"]}.html">{f"<span class=lbl>{esc(label)}</span>" if label else ""}'
            f'<span class="ph">{img}</span>'
            f'<b>{esc(f["name"])}</b><span class="m">{esc(where)}{" · since " + str(f["founded"]) if f["founded"] else ""}</span></a></li>')


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def page(title, body, rel="", active="", desc="", canonical=""):
    nav = "".join(
        f'<a href="{rel}{h}"{" aria-current=page" if a == active else ""}>{t}</a>'
        for h, t, a in [("index.html", "Find", "find"), ("index.html?site=lost", "Lost sites", "lost"), ("map.html", "Map", "map"),
                        ("countries.html", "Countries", "countries"), ("kinds.html", "Kinds", "kinds"),
                        ("about.html", "About", "about")])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{BASE}{canonical}">
<link rel="icon" href="{rel}favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{rel}style.css?v={V}">
</head><body>
<a class="skip" href="#main">Skip to content</a>
<header class="top"><div class="wrap">
<a class="brand" href="{rel}index.html"><svg class="reel" viewBox="0 0 32 32" aria-hidden="true"><use href="{rel}favicon.svg#r"/></svg><span>Film Festival <em>Finder</em></span></a>
<nav aria-label="Main">{nav}</nav>
</div></header>
<main id="main" class="wrap">
{body}
</main>
<footer class="foot"><div class="wrap">
<p>A <a href="https://wayback-labs.sf.archive.org/">Wayback Machine Labs</a> experiment, <a href="https://archive.org/">Internet Archive</a>.
Made by Claude (Anthropic) at the direction of Mark Graham. Feedback? <a href="mailto:info@archive.org?subject=Film%20Festival%20Finder">Email us</a>.</p>
<p>Data: <a href="https://www.wikidata.org/">Wikidata</a> (CC0), retrieved 17 November 2026. Archive history: the <a href="https://web.archive.org/">Wayback Machine</a>.
<a href="{rel}about.html">About this site</a> · <a href="{rel}about.html#accessibility">Accessibility</a></p>
</div></footer>
</body></html>
"""


def wb_line(f, wb):
    ys = wb.get(f["id"])
    if not f["site"]:
        return ""
    link = f'https://web.archive.org/web/*/{esc(f["site"])}'
    if ys is None:
        return f'<a href="{link}">See its captures in the Wayback Machine</a>'
    if not ys:
        return (f'The Wayback Machine has <b>no capture</b> of this homepage yet. '
                f'<a href="https://web.archive.org/save/{esc(f["site"])}">Save it now</a>')
    span = f"{ys[0]}" if len(ys) == 1 else f"{ys[0]}–{ys[-1]}"
    return (f'Archived in <b>{len(ys)}</b> year{"s" if len(ys) != 1 else ""} ({span}). '
            f'<a href="{link}">Browse the captures</a>')


def years_strip(ys, founded):
    if not ys:
        return ""
    lo = min(ys[0], founded or ys[0], 1996)
    lo = max(lo, 1996)
    cells = "".join(f'<span class="{"on" if y in ys else ""}" title="{y}"></span>' for y in range(lo, 2027))
    return f'<div class="strip" aria-label="Years with captures">{cells}</div><div class="strip-l"><span>{lo}</span><span>2026</span></div>'


def main():
    fest = json.loads((ROOT / "data" / "festivals.json").read_text())["festivals"]
    wb = {}
    wbf = ROOT / "raw" / "wayback.jsonl"
    if wbf.exists():
        for l in wbf.read_text().splitlines():
            r = json.loads(l)
            if r["years"] is not None:
                wb[r["id"]] = r["years"]
    if PUB.exists():
        shutil.rmtree(PUB)
    (PUB / "f").mkdir(parents=True)
    for a in ASSETS.iterdir():
        shutil.copy(a, PUB / a.name)

    for f in fest.values():
        f["kinds"] = kinds(f)
    main_list = [f for f in fest.values() if not f["parent"]]
    countries = Counter(f["country"] for f in main_list if f["country"])
    kind_count = Counter(k for f in main_list for k in f["kinds"])
    knames = [k for k, _, _ in KINDS]
    n = len(main_list)

    # Client data: compact rows.
    rows = []
    for f in sorted(main_list, key=lambda f: (-f["sitelinks"], f["name"].lower())):
        ys = wb.get(f["id"])
        rows.append([f["id"], f["name"], " | ".join(f["alt"]), f["country"] or "", f["place"] or "",
                     f["founded"] or 0, f["ended"] or 0, [knames.index(k) for k in f["kinds"]],
                     f["host"] or "", f["sitelinks"], (ys[0] if ys else (0 if ys == [] else -1)),
                     f["coord"][0] if f["coord"] else None, f["coord"][1] if f["coord"] else None,
                     1 if f["country_from"] == "web address" else 0, th(f)])
    (PUB / "data.json").write_text(json.dumps({"kinds": knames, "rows": rows}, ensure_ascii=False,
                                              separators=(",", ":")))

    # Festival pages.
    by_place = defaultdict(list)
    for f in main_list:
        if f["country"]:
            by_place[(f["country"], f["place"])].append(f)
    by_country = defaultdict(list)
    for f in sorted(main_list, key=lambda f: (-f["sitelinks"], f["name"].lower())):
        by_country[f["country"] or ""].append(f)
    pos = {f["id"]: (c, i) for c, fs in by_country.items() for i, f in enumerate(fs)}
    for f in fest.values():
        facts = []
        if f["country"]:
            note = ' <span class="note">(guessed from its web address)</span>' if f["country_from"] == "web address" else ""
            facts.append(("Country", f'<a href="../index.html?country={urllib.parse.quote(f["country"])}">{esc(f["country"])}</a>{note}'))
        if f["place"]:
            facts.append(("Place", esc(f["place"])))
        if f["founded"]:
            facts.append(("Founded", str(f["founded"])))
        if f["ended"]:
            facts.append(("Ended", str(f["ended"])))
        if f["kinds"]:
            facts.append(("Kind", ", ".join(f'<a href="../index.html?kind={urllib.parse.quote(k)}">{esc(k)}</a>' for k in f["kinds"])))
        if f["organizer"]:
            facts.append(("Organiser", esc(", ".join(f["organizer"]))))
        if f["parent"] and f["parent"] in fest:
            p = fest[f["parent"]]
            facts.append(("Part of", f'<a href="{p["id"]}.html">{esc(p["name"])}</a>'))
        links = []
        if f["site"]:
            links.append(f'<a class="btn primary" href="{esc(f["site"])}" rel="nofollow">Website <span class="h">{esc(f["host"])}</span></a>')
            links.append(f'<a class="btn wb" href="https://web.archive.org/web/*/{esc(f["site"])}">Wayback Machine</a>')
        if f["enwiki"]:
            links.append(f'<a class="btn" href="{esc(f["enwiki"])}">Wikipedia</a>')
        if f["facebook"]:
            links.append(f'<a class="btn" href="https://www.facebook.com/{esc(f["facebook"])}" rel="nofollow">Facebook</a>')
        if f["twitter"]:
            links.append(f'<a class="btn" href="https://x.com/{esc(f["twitter"])}" rel="nofollow">X</a>')
        links.append(f'<a class="btn" href="https://www.wikidata.org/wiki/{f["id"]}">Wikidata</a>')
        if f["coord"]:
            lat, lon = f["coord"]
            links.append(f'<a class="btn" href="https://www.openstreetmap.org/?mlat={lat}&amp;mlon={lon}#map=12/{lat}/{lon}">Map</a>')
        ys = wb.get(f["id"])
        arch = ""
        if f["site"]:
            arch = (f'<section class="arch"><h2>In the Wayback Machine</h2><p>{wb_line(f, wb)}</p>'
                    f'<p id="spn" hidden></p>{years_strip(ys, f["founded"])}</section>')
        eds = ""
        if f["edition_items"]:
            eds = "<section><h2>Editions on Wikidata</h2><ul>" + "".join(
                f'<li><a href="{e["id"]}.html">{esc(e["name"])}</a></li>' for e in f["edition_items"]) + "</ul></section>"
        near = [g for g in by_place.get((f["country"], f["place"]), []) if g["id"] != f["id"]] if f["place"] else []
        near = sorted(near, key=lambda g: -g["sitelinks"])[:12]
        nearby = ""
        if near:
            nearby = (f'<section><h2>Other festivals in {esc(f["place"])}</h2><ul class="cards">'
                      + "".join(card(g) for g in near) + "</ul></section>")
        pn = ""
        if f["id"] in pos:
            c, i = pos[f["id"]]
            fs = by_country[c]
            seen = {g["id"] for g in near} | {f["id"]}
            more = [g for g in fs if g["id"] not in seen][:8] if c else []
            prev_, next_ = (fs[i - 1] if i > 0 else None), (fs[i + 1] if i + 1 < len(fs) else None)
            scope = f"in {esc(c)}" if c else "with no country"
            if prev_ or next_:
                pn = (f'<nav class="pn" aria-label="Previous and next festival {scope}"><ul class="cards two">'
                      + (card(prev_, label=f"← Previous {scope}") if prev_ else "<li></li>")
                      + (card(next_, label=f"Next {scope} →") if next_ else "<li></li>")
                      + f'</ul><p class="note">Festival {i + 1:,} of {len(fs):,} {scope}, best known first.</p></nav>')
            if more:
                nearby += (f'<section><h2>Best-known festivals in {esc(c)}</h2><ul class="cards">' + "".join(card(g) for g in more)
                           + f'</ul><p><a href="../index.html?country={urllib.parse.quote(c)}">All {len(fs):,} festivals in {esc(c)} →</a></p></section>')
        img = ""
        if f["image"] or f["logo"]:
            src = f["logo"] or f["image"]
            img = f'<img class="pic" src="{esc(src)}" alt="" loading="lazy">'
        shot = ""
        if f["site"]:
            shot = (f'<figure class="shot" id="shot" data-h="{th(f)}" data-site="{esc(f["site"])}" data-name="{esc(f["name"])}" hidden>'
                    f'<a class="frame"><img alt="" width="960" height="600"></a><figcaption></figcaption></figure>')
        alt = f'<p class="alt">Also: {esc(" · ".join(f["alt"]))}</p>' if f["alt"] else ""
        desc = f'<p class="lede">{esc(f["desc"][0].upper() + f["desc"][1:])}</p>' if f.get("desc") else ""
        body = f"""<p class="crumb"><a href="../index.html">All festivals</a>{f' › <a href="../index.html?country={urllib.parse.quote(f["country"])}">{esc(f["country"])}</a>' if f["country"] else ""}</p>
<article class="fest">{img}<h1>{esc(f["name"])}</h1>{alt}{desc}
<dl class="facts">{"".join(f"<dt>{k}</dt><dd>{v}</dd>" for k, v in facts)}</dl>
<p class="links">{"".join(links)}</p></article>
{shot}{arch}{eds}{pn}{nearby}
<script src="../fest.js?v={V}"></script>"""
        where = ", ".join(x for x in [f["place"], f["country"]] if x)
        (PUB / "f" / f"{f['id']}.html").write_text(page(
            f"{f['name']} · Film Festival Finder", body, rel="../",
            desc=f"{f['name']}{' — film festival in ' + where if where else ''}: website, archive history and details.",
            canonical=f"f/{f['id']}.html"))

    # Home / finder.
    copts = "".join(f'<option value="{esc(c)}">{esc(c)} ({k:,})</option>' for c, k in sorted(countries.items()))
    kopts = "".join(f'<option value="{esc(k)}">{esc(k)} ({kind_count[k]:,})</option>' for k in knames if kind_count[k])
    decs = "".join(f'<option value="{d}">{d}s</option>' for d in range(2020, 1920, -10)) + '<option value="1900">before 1930</option>'
    archived = sum(1 for f in main_list if wb.get(f["id"]))
    never = sum(1 for f in main_list if f["id"] in wb and not wb[f["id"]])
    checked = sum(1 for f in main_list if f["id"] in wb)
    body = f"""<section class="hero">
<h1>Find a film festival</h1>
<p class="lede"><b>{n:,}</b> film festivals in <b>{len(countries)}</b> countries, from the biggest to the smallest, each with
its website and its history in the Wayback Machine.</p>
<form class="finder" id="finder" role="search" onsubmit="return false">
<label class="vh" for="q">Search festivals</label>
<input id="q" name="q" type="search" placeholder="A festival, a city, a word in its name…" autocomplete="off">
<div class="filters">
<label><span>Country</span><select id="country"><option value="">Any country</option>{copts}</select></label>
<label><span>Kind</span><select id="kind"><option value="">Any kind</option>{kopts}</select></label>
<label><span>Founded</span><select id="decade"><option value="">Any year</option>{decs}</select></label>
<label><span>Archive</span><select id="arch"><option value="">Any</option><option value="yes">Archived</option><option value="no">Not yet archived</option></select></label>
<label><span>Website today</span><select id="site"><option value="">Any</option><option value="pic">Has a picture</option><option value="live">Up and running</option><option value="lost">Gone or taken over</option><option value="gone">Gone or not loading</option><option value="taken">Parked or taken over</option></select></label>
<label><span>Sort</span><select id="sort"><option value="known">Best known first</option><option value="name">Name A–Z</option><option value="new">Newest founded</option><option value="old">Oldest founded</option><option value="wb">Longest archived</option></select></label>
</div></form>
</section>
<div class="bar"><p class="count" id="count" aria-live="polite"></p>
<div class="views" role="group" aria-label="Show results as"><button type="button" id="v-grid" aria-pressed="true">Pictures</button><button type="button" id="v-list" aria-pressed="false">List</button></div></div>
<p class="lostnote" id="lostnote" hidden>These festivals’ websites are gone, or their web addresses now belong to someone else.
Where the Wayback Machine kept a copy, the picture shows how the site looked before.</p>
<ol class="results grid" id="results"></ol>
<p class="more"><button id="more" hidden>Show more</button></p>
<noscript><p>The finder needs JavaScript. You can still browse by <a href="countries.html">country</a> or <a href="kinds.html">kind</a>.</p></noscript>
<script src="app.js?v={V}"></script>"""
    (PUB / "index.html").write_text(page("Film Festival Finder", body, active="find",
                                         desc=f"Find any of {n:,} film festivals around the world, with their websites and their archive history."))

    # Countries.
    cl = "".join(f'<li><a href="index.html?country={urllib.parse.quote(c)}">{esc(c)}</a> <span>{k:,}</span></li>'
                 for c, k in sorted(countries.items(), key=lambda x: (-x[1], x[0])))
    unknown = sum(1 for f in main_list if not f["country"])
    body = f"""<h1>Festivals by country</h1>
<p class="lede">{len(countries)} countries. {unknown:,} festivals have no country on Wikidata and no country web address, so they appear only in searches.</p>
<ol class="tally">{cl}</ol>"""
    (PUB / "countries.html").write_text(page("Countries · Film Festival Finder", body, active="countries",
                                             desc="Film festivals by country.", canonical="countries.html"))

    # Kinds.
    kl = "".join(f'<li><a href="index.html?kind={urllib.parse.quote(k)}">{esc(k)}</a> <span>{kind_count[k]:,}</span></li>'
                 for k in sorted(knames, key=lambda k: -kind_count[k]) if kind_count[k])
    body = f"""<h1>Festivals by kind</h1>
<p class="lede">Kinds come from Wikidata’s type for the festival and from words in its name in several languages
(“short”, “court métrage”, “cortometraje”, “Kurzfilm”…). A festival can be several kinds; most have none.</p>
<ol class="tally">{kl}</ol>"""
    (PUB / "kinds.html").write_text(page("Kinds · Film Festival Finder", body, active="kinds",
                                         desc="Film festivals by kind: short film, documentary, animation, LGBTQ+ and more.",
                                         canonical="kinds.html"))

    # Map.
    mapped = sum(1 for f in main_list if f["coord"])
    body = f"""<h1 class="maph">Map <span>{mapped:,} festivals with a known place</span></h1>
<div id="map" class="map"></div>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/MarkerCluster.Default.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet.markercluster/1.5.3/leaflet.markercluster.min.js"></script>
<script src="map.js?v={V}"></script>"""
    (PUB / "map.html").write_text(page("Map · Film Festival Finder", body, active="map",
                                       desc="A world map of film festivals.", canonical="map.html"))

    # About.
    by_from = Counter(f["country_from"] for f in main_list)
    body = f"""<article class="prose"><h1>About the Film Festival Finder</h1>
<p>Film festivals are a big part of how films find audiences, and most of them live on the web: programmes,
catalogues, juries, winners. Those pages change every year, and many small festivals disappear altogether. This finder
lists every film festival that has an entry on <a href="https://www.wikidata.org/">Wikidata</a>, the free knowledge
base behind Wikipedia, and shows how well each festival’s website has been kept in the
<a href="https://web.archive.org/">Wayback Machine</a>.</p>
<p>It grew out of the <a href="../dxfest/">Double Exposure Explorer</a>: to build that, we gathered nine years of the
festival’s printed catalogues, and eight of the nine had never been archived. This is the first step toward checking
every festival the same way.</p>
<h2>What is in it</h2>
<ul>
<li><b>{n:,} festivals</b>: every Wikidata item that is a film festival, or a kind of one (short film festival,
documentary film festival, LGBT film festival, and others), as of 17 November 2026. Items that are a single year of
another festival are listed on that festival’s page.</li>
<li><b>Country</b> for {n - unknown:,}: from Wikidata ({by_from['wikidata']:,}), from the festival’s place
({by_from['place']:,}), or guessed from a country web address such as <code>.it</code> or <code>.ca</code>
({by_from['web address']:,}, marked as guessed). {unknown:,} have no country.</li>
<li><b>Map</b>: {mapped:,} festivals whose item or place has coordinates.</li>
<li><b>Website</b> for {sum(1 for f in main_list if f["site"]):,}, from Wikidata’s “official website”. The others
have no picture.</li>
<li><b>Wayback Machine history</b>: for each website, the years in which its homepage was captured, from the Wayback
Machine’s capture index. Checked on 18 November 2026: {checked:,} sites; {archived:,} have captures, {never:,} have none.
The check is still running and the site is rebuilt as it goes.</li>
</ul>
<h2 id="pictures">Pictures of the homepages, and saving them</h2>
<p>Starting on 19 November 2026 we are visiting every festival website once, in a web browser on a Wayback Machine Labs
computer, to take a picture of its homepage, and asking the Wayback Machine’s
<a href="https://web.archive.org/save">Save Page Now</a> to archive each homepage, with a screenshot, the same day.
Pictures and links appear on the site as they are made; the first pass takes about a day.</p>
<ul>
<li>If a website is <b>up</b>, the picture is the homepage as it looked that day.</li>
<li>If it is <b>gone</b> (its address no longer works, it shows an error, or it would not load), or its address now
belongs to <b>someone else</b> (a parked or for-sale domain, a server’s default page, or an unrelated site such as an
online casino), we show the most recent copy in the Wayback Machine that still looks like the festival’s own site,
with its date. Those festivals are gathered under <a href="index.html?site=lost">Lost sites</a>.</li>
<li>Pictures of unrelated sites that took over a festival’s address are never shown. The check for them is automatic and
can miss; please tell us if you see one.</li>
<li>Pictures show the top of the page, 1280 by 800 pixels; videos are not loaded, so some show a dark space where a video
would play.</li>
</ul>
<h2>Limits</h2>
<ul>
<li>Wikidata is not complete. Big festivals are well described; many small ones have only a name and a website, and
many festivals are missing altogether. Wikidata welcomes additions.</li>
<li>The homepage history says nothing about the deeper pages (programmes, catalogues, film pages), which are the ones
most often missing.</li>
<li>“Kind” is a best guess from Wikidata types and from words in the festival’s name.</li>
</ul>
<p>Map tiles © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors.</p>
<h2 id="accessibility">Accessibility</h2>
<p>The site is plain HTML with a skip link, labelled navigation and form fields, and enough colour contrast in light
and dark mode. The finder’s search and filters and the map need JavaScript; every festival page, and the
<a href="countries.html">country</a> and <a href="kinds.html">kind</a> lists, work without it. It is meant to meet
WCAG 2.2 AA (Web Content Accessibility Guidelines). If something does not work for you, please write to
<a href="mailto:info@archive.org?subject=Film%20Festival%20Finder">info@archive.org</a>.</p>
<h2 id="web-archives">Web archives</h2>
<p>Web archives are welcome to capture this site. If your crawler has trouble capturing it, contact info@archive.org.
There is a <a href="sitemap.xml">sitemap</a>.</p>
<h2 id="who">Who made this</h2>
<p>This site was made by Claude, an AI model made by Anthropic, working in Claude Code at the direction of Mark Graham
(Internet Archive). Mark Graham decided what it should be and what it should cover; Claude did the research and wrote
the code. Built 17 November 2026.</p>
</article>"""
    (PUB / "about.html").write_text(page("About · Film Festival Finder", body, active="about",
                                         desc="How the Film Festival Finder was made.", canonical="about.html"))
    (PUB / "404.html").write_text(page("Not found · Film Festival Finder",
                                       '<h1>Not found</h1><p><a href="/film-festivals/index.html">Find a festival</a></p>',
                                       rel="/film-festivals/"))
    urls = ["index.html", "map.html", "countries.html", "kinds.html", "about.html"] + [f"f/{i}.html" for i in fest]
    (PUB / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                     + "".join(f"<url><loc>{BASE}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    (PUB / "robots.txt").write_text(f"Sitemap: {BASE}sitemap.xml\n")
    print(n, "festivals;", len(countries), "countries;", mapped, "mapped;", checked, "wayback-checked")


if __name__ == "__main__":
    main()
