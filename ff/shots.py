"""Thumbnails of every festival homepage: the live site, or its last good Wayback capture if the site is gone.

    python3 ff/shots.py data/festivals.json STATE.sqlite THUMBS_DIR run         resumable
    python3 ff/shots.py data/festivals.json STATE.sqlite THUMBS_DIR stats
    python3 ff/shots.py data/festivals.json STATE.sqlite THUMBS_DIR export OUT.jsonl
    python3 ff/shots.py - - THUMBS_DIR one URL                                   test one site

For each website: load it in Chrome (1280x800), and keep the shot unless the page failed, came back blank, is a
parked or for-sale domain, a server default page, or was taken over (gambling, adult, scam); then fall back to the
latest Wayback capture that is none of those (stepping back two years at a time, up to four tries).
Files: THUMBS/<sha1(url)[:16]>.webp (480x300) and <...>-l.webp (960x600).

Uses system Chrome with its sandbox and one reused page per browser: on the studio, Chrome crashes when
Playwright closes a page (see salon-explorer/app/shots.py).
"""
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request

from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

VIEWPORT = {"width": 1280, "height": 800}
UA_SUFFIX = "WaybackMachineLabs-FilmFestivalFinder/0.2 (Internet Archive; +https://wayback-labs.sf.archive.org/film-festivals/)"
BLOCK = {"media", "websocket", "eventsource", "manifest", "texttrack"}

PARKED = re.compile(
    r"(this domain|the domain|domain name)[^.]{0,40}(is|may be) (for sale|available)|buy this domain|domain (is )?for sale|"
    r"\bparked (free|domain|by)|hugedomains|sedoparking|sedo\.com|dan\.com|afternic|bodis\.com|parkingcrew|above\.com|"
    r"this domain (has )?expired|domain has expired|renew (this|your) domain|account (has been )?suspended|"
    r"website is (currently )?(suspended|unavailable)|apache2? .{0,20}default page|welcome to nginx|iis windows server|"
    r"it works!|^index of /|future home of|web hosting (by|from)|coming soon[^.]{0,40}godaddy|"
    r"site not found|no such app|there isn't a github pages site here|domain not configured|"
    r"this site can.t be reached|default web site page", re.I)
FLAGS = [
    ("adult", 1, re.compile(r"\b(porn|xxx|nsfw|onlyfans|escort|escorts|nudes|sex ?cam|hentai|camgirls?|18\+ only)\b", re.I)),
    ("gambling", 2, re.compile(r"\b(casino|online slots?|slot (gacor|online|demo|machines?)|demo slot|gacor|judi|togel|betting|"
                               r"sportsbook|poker|jackpot|bet now|free spins|situs|bandar|maxwin|toto)\b", re.I)),
    ("scam", 2, re.compile(r"\b(guaranteed (profit|returns)|double your (bitcoin|money|crypto)|investment plan|forex signals?|"
                           r"cheap (viagra|cialis)|buy followers|payday loans?|essay writing service)\b", re.I)),
]
ADULT_CJK = re.compile(r"FANZA|DMM\.R18|アダルト|エロ|無修正|AV女優|成人向け|18禁|色情|成人影片|成人视频|成人視頻|av女优|야동|성인용", re.I)
WB_ERR = re.compile(r"Wayback Machine has not archived|Hrm\.|This URL has been excluded|Got an HTTP \d+ response at crawl time"
                    r"|Redirecting to\.\.\.|Impatient\?", re.I)
TEXT_JS = """() => ({title: (document.title || '').trim(),
  text: (document.body ? document.body.innerText : '').slice(0, 6000),
  links: document.links ? document.links.length : 0})"""


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


def name(url):
    return hashlib.sha1(url.encode()).hexdigest()[:16]


PLACEHOLDER = re.compile(r"under (construction|maintenance)|maintenance mode|doing some work on (the|our) site|"
                         r"(site|website) (is )?(currently )?(down for|under) maintenance|be back (soon|shortly)|"
                         r"^\W*coming soon\W*$|launching soon|new (web)?site (is )?coming soon", re.I | re.M)


def verdict(title, text, html):
    head = f"{title} {text}"
    if PLACEHOLDER.search(head[:1500]) and len(text) < 1500:
        return "placeholder"
    if PARKED.search(head[:3000]) and len(text) < 2500:
        return "parked"
    for n, k, rx in FLAGS:
        # distinct words, so a festival held at "the Casino" is not a gambling site
        found = {(m if isinstance(m, str) else m[0]).lower() for m in rx.findall(head)}
        if len(found) >= k:
            return n
    if ADULT_CJK.search(head) or re.search(r'<meta[^>]+name=["\']?rating["\']?[^>]+content=["\']?(adult|mature|RTA)', html, re.I):
        return "adult"
    return "ok"


def launch(p):
    b = p.chromium.launch(channel="chrome", chromium_sandbox=True)
    major = b.version.split(".")[0]
    ua = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
          f"Chrome/{major}.0.0.0 Safari/537.36 {UA_SUFFIX}")
    ctx = b.new_context(viewport=VIEWPORT, user_agent=ua, accept_downloads=False, ignore_https_errors=True)
    ctx.route("**/*", lambda r: r.abort() if r.request.resource_type in BLOCK else r.continue_())
    page = ctx.new_page()
    page.set_default_timeout(20000)
    return b, page


def look(page, url, timeout=25000, settle=1500):
    resp = page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except Exception:
        pass
    page.wait_for_timeout(settle)
    info = page.evaluate(TEXT_JS)
    html = page.content()[:300000]
    png = page.screenshot(full_page=False)
    return (resp.status if resp else None), page.url, info, html, png


def blank(img):
    return max(ImageStat.Stat(img.convert("L").resize((128, 80))).stddev) < 4


def save(png, base):
    img = Image.open(io.BytesIO(png)).convert("RGB")
    if blank(img):
        return False
    img.resize((960, 600), Image.LANCZOS).save(base + "-l.webp", "WEBP", quality=70, method=6)
    img.resize((480, 300), Image.LANCZOS).save(base + ".webp", "WEBP", quality=72, method=6)
    return True


def available(url, ts=None):
    q = {"url": url}
    if ts:
        q["timestamp"] = ts
    req = urllib.request.Request("https://archive.org/wayback/available?" + urllib.parse.urlencode(q),
                                 headers={"User-Agent": UA_SUFFIX})
    for i in range(3):
        try:
            snap = json.load(urllib.request.urlopen(req, timeout=40)).get("archived_snapshots", {}).get("closest")
            return snap["timestamp"] if snap and snap.get("available") and str(snap.get("status", "200")) == "200" else None
        except Exception:
            time.sleep(5 * (i + 1))
    return None


def shoot(page, url, thumbs):
    """-> row dict"""
    base = os.path.join(thumbs, name(url))
    row = dict(url=url, src=None, ts=None, live="error", status=None, final_url=None, title=None, note=None, thumb=None)
    try:
        status, final, info, html, png = look(page, url)
        row.update(status=status, final_url=final, title=info["title"][:300])
        if status and status >= 400:
            row["live"] = f"http {status}"
        else:
            v = verdict(info["title"], info["text"], html)
            if v != "ok":
                row["live"] = v
            elif not save(png, base):
                row["live"] = "blank"
            else:
                row.update(live="ok", src="live", ts=time.strftime("%Y%m%d"), thumb=name(url))
                return row
    except Exception as e:
        row["note"] = (type(e).__name__ + ": " + (str(e).splitlines() or [""])[0])[:200]
        if "net::ERR_NAME_NOT_RESOLVED" in row["note"]:
            row["live"] = "no dns"
        elif "Timeout" in row["note"]:
            row["live"] = "timeout"
    # Fall back to the Wayback Machine: latest good capture, then step back.
    ts = None
    for _ in range(4):
        ts = available(url, ts)
        if not ts:
            break
        try:
            status, final, info, html, png = look(page, f"https://web.archive.org/web/{ts}if_/{url}", timeout=60000, settle=2500)
            if not WB_ERR.search(info["title"] + " " + info["text"][:800]) and verdict(info["title"], info["text"], html) == "ok" \
                    and save(png, base):
                row.update(src="wayback", ts=ts, thumb=name(url), title=info["title"][:300] or row["title"])
                return row
        except Exception as e:
            row["note"] = ((row["note"] or "") + " | wb " + type(e).__name__)[:300]
        ts = str(int(ts[:4]) - 2) + ts[4:]
        if int(ts[:4]) < 1996:
            break
    return row


def db(path):
    c = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=30)
    c.execute("""CREATE TABLE IF NOT EXISTS shot (url text PRIMARY KEY, prio int, done real, src text, ts text, live text,
                 status int, final_url text, title text, note text, thumb text)""")
    return c


def worker(c, lock, thumbs, stats):
    with sync_playwright() as p:
        b, page = launch(p)
        while True:
            with lock:
                r = c.execute("SELECT url FROM shot WHERE done IS NULL ORDER BY prio, url LIMIT 1").fetchone()
                if not r:
                    break
                url = r[0]
                c.execute("UPDATE shot SET done=-1 WHERE url=?", (url,))     # claimed
            if not b.is_connected():
                try:
                    b.close()
                except Exception:
                    pass
                b, page = launch(p)
                stats["relaunch"] = stats.get("relaunch", 0) + 1
            # A crashed tab stays crashed while the browser stays connected: every later site on this worker
            # then failed with "Page crashed" (1,758 sites on 2026-11-19). Relaunch the browser and try once more.
            for attempt in (1, 2):
                row = shoot(page, url, thumbs)
                if not re.search(r"crashed|TargetClosed", row["note"] or ""):
                    break
                try:
                    b.close()
                except Exception:
                    pass
                b, page = launch(p)
                stats["relaunch"] = stats.get("relaunch", 0) + 1
            with lock:
                c.execute("UPDATE shot SET done=?, src=?, ts=?, live=?, status=?, final_url=?, title=?, note=?, thumb=? WHERE url=?",
                          (time.time(), row["src"], row["ts"], row["live"], row["status"], row["final_url"], row["title"],
                           row["note"], row["thumb"], url))
                k = row["src"] or "none"
                stats[k] = stats.get(k, 0) + 1


def main():
    fest_path, state, thumbs, cmd = sys.argv[1:5]
    os.makedirs(thumbs, exist_ok=True)
    if cmd == "one":
        with sync_playwright() as p:
            b, page = launch(p)
            print(json.dumps(shoot(page, sys.argv[5], thumbs), indent=1))
            b.close()
        return
    c = db(state)
    if cmd == "stats":
        for r in c.execute("SELECT coalesce(src,'-'), live, count(*) FROM shot WHERE done > 0 GROUP BY 1, 2 ORDER BY 3 DESC"):
            print(*r)
        print("left", c.execute("SELECT count(*) FROM shot WHERE done IS NULL OR done < 0").fetchone()[0])
        return
    if cmd == "export":
        with open(sys.argv[5], "w") as fh:
            for r in c.execute("SELECT url, src, ts, live, status, final_url, title, thumb FROM shot WHERE done > 0"):
                fh.write(json.dumps(dict(zip(["url", "src", "ts", "live", "status", "final_url", "title", "thumb"], r)),
                                    ensure_ascii=False) + "\n")
        return
    fest = json.load(open(fest_path))["festivals"]
    for f in fest.values():
        if f["site"] and not f["parent"]:
            c.execute("INSERT OR IGNORE INTO shot (url, prio) VALUES (?, ?)", (f["site"], -min(f["sitelinks"], 50)))
    c.execute("UPDATE shot SET done=NULL WHERE done < 0")    # claims left by a killed run
    n = int(os.environ.get("FF_SHOT_WORKERS", 6))
    lock, stats, t = threading.Lock(), {}, time.time()
    ths = [threading.Thread(target=worker, args=(c, lock, thumbs, stats), daemon=True) for _ in range(n)]
    for th in ths:
        th.start()
    spn = os.environ.get("FF_SPN_DB", os.path.join(os.path.dirname(os.path.abspath(state)), "spn.sqlite"))
    written, last, said = {}, 0, False
    while True:
        time.sleep(30)
        if time.time() - last > 120:
            publish(c, lock, spn, thumbs, written)
            last = time.time()
        alive = any(th.is_alive() for th in ths)
        if alive and round(time.time() - t) % 600 < 30:
            log(stats, "left", c.execute("SELECT count(*) FROM shot WHERE done IS NULL").fetchone()[0],
                f"{round((time.time() - t) / 60)} min")
        if not alive and not said:
            log("all done", stats); said = True


def publish(c, lock, spn_path, thumbs, written):
    """THUMBS/index.json (every site: [picture source, its date, live state, SPN capture]) and a small
    THUMBS/<hash>.json per site, read by the finder and the festival pages. Rewrites only what changed."""
    spn = {}
    if os.path.exists(spn_path):
        try:
            s = sqlite3.connect(spn_path, timeout=30)
            spn = {u: ts for u, ts in s.execute("SELECT url, timestamp FROM job WHERE status='success' AND timestamp IS NOT NULL")}
            s.close()
        except sqlite3.Error:
            pass
    with lock:
        rows = c.execute("SELECT url, src, ts, live, final_url, title, done FROM shot WHERE done > 0").fetchall()
    idx = {}
    for url, src, ts, live, final, title, done in rows:
        rec = [{"live": "l", "wayback": "w"}.get(src, ""), ts or "", live or "", spn.get(url, "")]
        h = name(url)
        idx[h] = rec
        if written.get(h) != rec:
            side = dict(src=src, ts=ts, live=live, spn=spn.get(url), checked=time.strftime("%Y%m%d", time.gmtime(done)),
                        title=title if src else None, final=final if (final != url and live == "ok") else None)
            tmp = os.path.join(thumbs, h + ".json.tmp")
            with open(tmp, "w") as fh:
                json.dump(side, fh, ensure_ascii=False)
            os.replace(tmp, os.path.join(thumbs, h + ".json"))
            written[h] = rec
    tmp = os.path.join(thumbs, "index.json.tmp")
    with open(tmp, "w") as fh:
        json.dump({"updated": time.strftime("%Y-%m-%dT%H:%M:%S"), "n": len(idx), "spn": len(spn), "s": idx},
                  fh, separators=(",", ":"))
    os.replace(tmp, os.path.join(thumbs, "index.json"))

if __name__ == "__main__":
    main()
