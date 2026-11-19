(function () {
  var fig = document.getElementById("shot");
  if (!fig) return;
  var h = fig.dataset.h, site = fig.dataset.site, nm = fig.dataset.name;
  var M = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  function day(ts) { return ts ? (+ts.slice(6, 8)) + " " + M[+ts.slice(4, 6) - 1] + " " + ts.slice(0, 4) : ""; }
  function esc(s) { return String(s || "").replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  var STATE = {
    "no dns": "This festival’s website is gone: its address no longer works.",
    "timeout": "This festival’s website did not load when we checked.",
    "error": "This festival’s website did not load when we checked.",
    "blank": "This festival’s website showed a blank page when we checked.",
    "placeholder": "This festival’s website showed only a placeholder (“under construction”, “coming soon”) when we checked.",
    "parked": "This festival’s web address is now parked, for sale, or shows a server’s default page.",
    "gambling": "This festival’s web address now belongs to an unrelated site.",
    "adult": "This festival’s web address now belongs to an unrelated site.",
    "scam": "This festival’s web address now belongs to an unrelated site."
  };
  function state(live) {
    if (!live || live === "ok") return "";
    var code = /^http /.test(live) ? +live.slice(5) : 0;
    if (code === 404 || code === 410) return "This festival’s web page is gone (the site answers “not found”).";
    if (code === 401 || code === 403 || code === 429) return "This festival’s website would not show itself to us (HTTP " + code + "); it may only turn away automated visitors.";
    if (code) return "This festival’s website answered with an error (HTTP " + code + ") when we checked.";
    return STATE[live] || "";
  }
  fetch("../thumbs/" + h + ".json").then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
    if (!d) return;
    var cap = fig.querySelector("figcaption"), a = fig.querySelector("a"), img = fig.querySelector("img");
    var spn = document.getElementById("spn");
    if (d.spn && spn) {
      spn.innerHTML = 'Saved again on <b>' + day(d.spn) + '</b> with Save Page Now. <a href="https://web.archive.org/web/' + d.spn + "/" + esc(site) + '">See that capture</a>';
      spn.hidden = false;
    }
    if (d.src === "live") {
      a.href = site; a.rel = "nofollow";
      img.alt = "The homepage of " + nm + " on " + day(d.ts);
      cap.innerHTML = "The homepage on " + day(d.ts) + "." + (d.spn ? ' <a href="https://web.archive.org/web/' + d.spn + "/" + esc(site) + '">Archived the same day</a>.' : "");
    } else if (d.src === "wayback") {
      fig.classList.add("was");
      a.href = "https://web.archive.org/web/" + d.ts + "/" + site;
      img.alt = "The homepage of " + nm + " as archived on " + day(d.ts);
      cap.innerHTML = "<b>" + esc(state(d.live)) + "</b> This is how it looked on " + day(d.ts) + ', in the <a href="' + esc(a.href) + '">Wayback Machine</a>.';
    } else {
      var s = state(d.live);
      if (!s) return;
      fig.classList.add("none");
      a.remove();
      cap.innerHTML = "<b>" + esc(s) + "</b> The Wayback Machine has no earlier copy we could show. Checked " + day(d.checked) + ".";
      fig.hidden = false;
      return;
    }
    img.src = "../thumbs/" + h + "-l.webp";
    img.onload = function () { fig.hidden = false; };
  }).catch(function () {});
})();
