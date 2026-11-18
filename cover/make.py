"""Render cover/cover.html (festivals as dots on a world grid) and screenshot it to cover/film-festivals-cover.jpg (1200x630).

    python3 cover/make.py
"""
import json
import subprocess
from pathlib import Path

here = Path(__file__).parent
rows = json.loads((here.parent / "public" / "data.json").read_text())["rows"]
pts = [(r[11], r[12]) for r in rows if r[11] is not None]
W, H = 1200, 630
dots = "".join(f'<circle cx="{(lon + 180) / 360 * W:.1f}" cy="{(90 - lat) / 180 * 760 - 40:.1f}" r="2.4"/>' for lat, lon in pts)
n, countries = len(rows), len({r[3] for r in rows if r[3]})
html = f"""<!doctype html><meta charset=utf-8><style>
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#1c1716;font-family:Georgia,serif}}
svg.dots{{position:absolute;inset:0}} .dots circle{{fill:#f0c35a;opacity:.85}}
.veil{{position:absolute;inset:0;background:linear-gradient(90deg,rgba(28,23,22,.97) 0,rgba(28,23,22,.85) 40%,rgba(28,23,22,.05) 75%)}}
.reel{{position:absolute;left:66px;top:74px;width:110px;height:110px}}
h1{{position:absolute;left:62px;top:205px;margin:0;color:#fbf3e4;font:700 78px/1.02 Georgia,serif}}
h1 em{{color:#e8b230;font-weight:400}}
p{{position:absolute;left:66px;top:400px;margin:0;color:#e2d8c8;font:27px/1.45 -apple-system,Helvetica,sans-serif;width:640px}}
.bar{{position:absolute;left:0;right:0;bottom:0;height:12px;background:#b3122b}}
</style><svg class=dots viewBox="0 0 {W} {H}">{dots}</svg><div class=veil></div>
<svg class=reel viewBox="0 0 32 32"><circle cx="16" cy="16" r="15" fill="#b3122b"/><circle cx="16" cy="16" r="3" fill="#f6c94a"/><g fill="#fbf6ec"><circle cx="16" cy="7.5" r="3.6"/><circle cx="16" cy="24.5" r="3.6"/><circle cx="7.5" cy="16" r="3.6"/><circle cx="24.5" cy="16" r="3.6"/></g></svg>
<h1>Film Festival<br><em>Finder</em></h1>
<p>{n:,} film festivals in {countries} countries, with their websites and their history in the Wayback Machine</p><div class=bar></div>"""
(here / "cover.html").write_text(html)
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
png = here / "cover.png"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
                f"--screenshot={png}", f"file://{(here / 'cover.html').resolve()}"], check=True, capture_output=True)
subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", str(png), "--out",
                str(here / "film-festivals-cover.jpg")], check=True, capture_output=True)
png.unlink()
print("wrote", here / "film-festivals-cover.jpg")
