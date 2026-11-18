"""Render cover/cover.html (festivals as glowing dots on a world map, between film-strip edges) and screenshot it
to cover/film-festivals-cover.jpg (1200x630, like the other tiles; the landing card shows it ~300 px wide).

    python3 cover/make.py
"""
import json
import subprocess
from pathlib import Path

here = Path(__file__).parent
rows = json.loads((here.parent / "public" / "data.json").read_text())["rows"]
pts = [(r[11], r[12]) for r in rows if r[11] is not None]
W, H = 1200, 630
STRIP = 58                      # film-strip band height, top and bottom
# Equirectangular, cropped to latitudes 72N..-50S so the land fills the frame.
LAT0, LAT1 = 72, -50
mh = H - 2 * STRIP


def xy(lat, lon):
    return (lon + 180) / 360 * W, STRIP + (LAT0 - lat) / (LAT0 - LAT1) * mh


dots = "".join('<circle cx="%.1f" cy="%.1f" r="3"/>' % xy(lat, lon) for lat, lon in pts if LAT1 < lat < LAT0)
holes = "".join(f'<rect x="{x}" y="17" width="30" height="24" rx="5"/><rect x="{x}" y="{H - 41}" width="30" height="24" rx="5"/>'
                for x in range(14, W, 52))
n, countries = len(rows), len({r[3] for r in rows if r[3]})
html = f"""<!doctype html><meta charset=utf-8><style>
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#161112;font-family:Georgia,serif}}
svg{{position:absolute;inset:0}}
.dots circle{{fill:#ffcf5a;opacity:.9}}
.glow{{filter:blur(7px);opacity:.55}}
.veil{{position:absolute;left:0;top:{STRIP}px;bottom:{STRIP}px;width:760px;
  background:linear-gradient(90deg,rgba(32,22,24,.97) 0,rgba(32,22,24,.92) 62%,rgba(32,22,24,0) 100%)}}
.film rect.h{{fill:#161112}}
.reel{{position:absolute;left:64px;top:104px;width:92px;height:92px}}
h1{{position:absolute;left:60px;top:214px;margin:0;color:#fff8ea;font:700 104px/.98 Georgia,serif;letter-spacing:-1.5px}}
h1 em{{color:#ffc53d;font-weight:400}}
p{{position:absolute;left:64px;top:456px;margin:0;color:#f3e6cf;font:600 34px/1.2 -apple-system,Helvetica,sans-serif;letter-spacing:.2px}}
p b{{color:#ffc53d}}
</style>
<svg viewBox="0 0 {W} {H}"><rect width="{W}" height="{H}" fill="#201618"/>
<g class="dots glow">{dots}</g><g class="dots">{dots}</g></svg>
<div class=veil></div>
<svg viewBox="0 0 {W} {H}" class="film"><rect width="{W}" height="{STRIP}" fill="#b3122b"/><rect y="{H - STRIP}" width="{W}" height="{STRIP}" fill="#b3122b"/>{holes.replace('<rect ', '<rect class="h" ')}</svg>
<svg class=reel viewBox="0 0 32 32"><circle cx="16" cy="16" r="15" fill="#ffc53d"/><circle cx="16" cy="16" r="3" fill="#b3122b"/><g fill="#201618"><circle cx="16" cy="7.5" r="3.6"/><circle cx="16" cy="24.5" r="3.6"/><circle cx="7.5" cy="16" r="3.6"/><circle cx="24.5" cy="16" r="3.6"/></g></svg>
<h1>Film Festival<br><em>Finder</em></h1>
<p><b>{n:,}</b> festivals · <b>{countries}</b> countries</p>"""
(here / "cover.html").write_text(html)
chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
png = here / "cover.png"
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={W},{H}",
                f"--screenshot={png}", f"file://{(here / 'cover.html').resolve()}"], check=True, capture_output=True)
subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "88", str(png), "--out",
                str(here / "film-festivals-cover.jpg")], check=True, capture_output=True)
png.unlink()
print("wrote", here / "film-festivals-cover.jpg")
