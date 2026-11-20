"""Archive every festival homepage with Save Page Now (SPN2), with a Wayback screenshot.

    python3 ff/spn.py data/festivals.json STATE.sqlite queue
    python3 ff/spn.py data/festivals.json STATE.sqlite run       resumable; survives restarts (launchd KeepAlive)
    python3 ff/spn.py data/festivals.json STATE.sqlite stats
    python3 ff/spn.py data/festivals.json STATE.sqlite retry     put temporary failures back once
    python3 ff/spn.py data/festivals.json STATE.sqlite export OUT.jsonl

One capture per website (the homepage only, no outlinks). capture_all=1 keeps error pages too, so a dead
festival's last answer is on record; capture_screenshot=1 stores a screenshot in the Wayback Machine.
Uses the archive.org keys in ~/.config/internetarchive/ia.ini (shared with other studio jobs), so it keeps few
captures in flight (FF_SPN_INFLIGHT) and backs off on limits.
"""
import configparser
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

INFLIGHT = int(os.environ.get("FF_SPN_INFLIGHT", 6))
H = {"Accept": "application/json", "User-Agent": "WaybackMachineLabs-FilmFestivalFinder/0.2"}
RETRYABLE = ("service unavailable", "internal server", "bad gateway", "respond in time", "job failed", "http 5")


def log(*a):
    print(time.strftime("%Y-%m-%d %H:%M:%S"), *a, flush=True)


def load_keys():
    cfg = configparser.ConfigParser()
    cfg.read(os.path.expanduser("~/.config/internetarchive/ia.ini"))
    H["Authorization"] = f"LOW {cfg['s3']['access']}:{cfg['s3']['secret']}"


def call(url, data=None):
    body = urllib.parse.urlencode(data).encode() if data else None
    return json.load(urllib.request.urlopen(urllib.request.Request(url, body, H), timeout=60))


def db(path):
    c = sqlite3.connect(path, isolation_level=None)
    c.execute("""CREATE TABLE IF NOT EXISTS job (
        url text PRIMARY KEY, prio int, job_id text, submitted real, finished real, status text,
        timestamp text, message text, tries int DEFAULT 0)""")
    return c


def queue(c, fest):
    n = 0
    for f in fest.values():
        if f["site"] and not f["parent"]:
            # best-known festivals first
            n += c.execute("INSERT OR IGNORE INTO job (url, prio) VALUES (?, ?)",
                           (f["site"], -min(f["sitelinks"], 50))).rowcount
    log("queued", n, "total", c.execute("SELECT count(*) FROM job").fetchone()[0])


def stats(c):
    for r in c.execute("SELECT coalesce(status,'queued'), count(*) FROM job GROUP BY 1 ORDER BY 2 DESC"):
        print(*r)


def retry(c):
    n = 0
    for url, st, msg in c.execute("SELECT url, status, coalesce(message,'') FROM job WHERE tries < 2").fetchall():
        if st == "timeout" or (st == "error" and any(k in msg.lower() for k in RETRYABLE)):
            c.execute("UPDATE job SET status=NULL, job_id=NULL, prio=100 WHERE url=?", (url,)); n += 1
    log("requeued", n)


def export(c, out):
    with open(out, "w") as fh:
        for url, st, ts, msg, fin in c.execute("SELECT url, status, timestamp, message, finished FROM job WHERE status IS NOT NULL AND status != 'pending'"):
            fh.write(json.dumps({"url": url, "status": st, "timestamp": ts, "message": msg, "finished": fin}) + "\n")


def run(c):
    load_keys()
    inflight = {u: (j, s) for u, j, s in c.execute("SELECT url, job_id, submitted FROM job WHERE status='pending'")}
    sent = done = ok = 0
    backoff = last = 0
    while True:
        if time.time() >= backoff and len(inflight) < INFLIGHT:
            todo = c.execute("SELECT url FROM job WHERE status IS NULL ORDER BY prio, url LIMIT ?",
                             (INFLIGHT - len(inflight),)).fetchall()
            if not todo and not inflight:
                log("all done"); stats(c)
                time.sleep(3600); continue      # stay up quietly under launchd KeepAlive
            for (url,) in todo:
                try:
                    r = call("https://web.archive.org/save", {
                        "url": url, "capture_all": 1, "capture_screenshot": 1, "skip_first_archive": 1,
                        "delay_wb_availability": 0})
                except urllib.error.HTTPError as e:
                    log("submit HTTP", e.code, url)
                    if e.code in (401, 429, 502, 503, 504):
                        backoff = time.time() + (900 if e.code == 401 else 120); break
                    c.execute("UPDATE job SET status='error', message=?, finished=?, tries=tries+1 WHERE url=?",
                              (f"HTTP {e.code}", time.time(), url))
                    continue
                except Exception as e:
                    log("submit error", repr(e)); backoff = time.time() + 60; break
                if r.get("job_id"):
                    sent += 1
                    inflight[url] = (r["job_id"], time.time())
                    c.execute("UPDATE job SET status='pending', job_id=?, submitted=?, tries=tries+1 WHERE url=?",
                              (r["job_id"], time.time(), url))
                else:
                    msg = (r.get("message") or json.dumps(r))[:300]
                    # account limits only: a bare "limit" also matches site names (www.nolimitsfilmfestival.com)
                    if r.get("status_ext") in ("error:user-session-limit", "error:too-many-daily-captures") \
                            or re.search(r"session limit|daily (capture )?limit|too many (daily )?captures|concurrent", msg, re.I):
                        log("limit:", msg); backoff = time.time() + 300; break
                    st = "recent" if ("already" in msg or r.get("timestamp")) else "refused"
                    c.execute("UPDATE job SET status=?, message=?, timestamp=?, finished=? WHERE url=?",
                              (st, msg, r.get("timestamp"), time.time(), url))
        time.sleep(10)
        for url, (job, sub) in list(inflight.items()):
            try:
                st = call("https://web.archive.org/save/status/" + job)
            except Exception as e:
                log("status error", repr(e)); time.sleep(30); break
            if st.get("status") == "pending" and time.time() - sub < 1800:
                continue
            status = st.get("status") if st.get("status") != "pending" else "timeout"
            c.execute("UPDATE job SET status=?, finished=?, timestamp=?, message=? WHERE url=?",
                      (status, time.time(), st.get("timestamp"),
                       (st.get("message") or st.get("status_ext") or "")[:300], url))
            del inflight[url]
            done += 1; ok += status == "success"
        if time.time() - last > 300:
            left = c.execute("SELECT count(*) FROM job WHERE status IS NULL").fetchone()[0]
            log(f"sent {sent}, finished {done}, success {ok}, in flight {len(inflight)}, queued {left}")
            last = time.time()


if __name__ == "__main__":
    fest = json.load(open(sys.argv[1]))["festivals"]
    c = db(sys.argv[2])
    cmd = sys.argv[3]
    {"queue": lambda: queue(c, fest), "stats": lambda: stats(c), "retry": lambda: retry(c),
     "export": lambda: export(c, sys.argv[4]), "run": lambda: run(c)}[cmd]()
