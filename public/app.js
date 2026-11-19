(function () {
  var $ = function (id) { return document.getElementById(id); };
  var KINDS = [], ROWS = [], IDX = {}, shown = 0, hits = [], view = "grid";
  var PAGE = 48, KEYS = ["q", "country", "kind", "decade", "arch", "site", "sort"];
  var GONE = {"no dns": 1, "timeout": 1, "error": 1, "blank": 1, "placeholder": 1}, TAKEN = {"parked": 1, "gambling": 1, "adult": 1, "scam": 1};
  function norm(s) { return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function st(r) { return r[14] ? IDX[r[14]] : null; }   // [src l|w|"", date, live state, spn timestamp]
  function lost(s) { return s && (GONE[s[2]] || TAKEN[s[2]] || /^http /.test(s[2])); }
  function params() {
    var p = new URLSearchParams(location.search);
    KEYS.forEach(function (k) { if (p.get(k)) $(k).value = p.get(k); });
    if (p.get("view") === "list") view = "list";
  }
  function save() {
    var p = new URLSearchParams();
    KEYS.forEach(function (k) { if ($(k).value && !(k === "sort" && $(k).value === "known")) p.set(k, $(k).value); });
    if (view === "list") p.set("view", "list");
    var s = p.toString();
    history.replaceState(null, "", s ? "?" + s : location.pathname);
    // "Lost sites" in the menu is this page with a filter
    var isLost = $("site").value === "lost";
    document.querySelectorAll("header nav a").forEach(function (a) {
      var h = a.getAttribute("href");
      if (h === "index.html" ? !isLost : h === "index.html?site=lost" ? isLost : false) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    $("lostnote").hidden = !isLost;
  }
  function siteOk(r, w) {
    if (!w) return true;
    var s = st(r);
    if (w === "pic") return !!(s && s[0]);
    if (w === "live") return !!(s && s[2] === "ok");
    if (w === "lost") return !!lost(s);
    if (w === "taken") return !!(s && TAKEN[s[2]]);
    if (w === "gone") return !!(s && (GONE[s[2]] || /^http /.test(s[2])));
    return true;
  }
  function run() {
    var q = norm($("q").value.trim()), terms = q ? q.split(/\s+/) : [];
    var c = $("country").value, k = $("kind").value, d = $("decade").value, a = $("arch").value, w = $("site").value, so = $("sort").value;
    var ki = k ? KINDS.indexOf(k) : -1;
    hits = [];
    for (var i = 0; i < ROWS.length; i++) {
      var r = ROWS[i];
      if (c && r[3] !== c) continue;
      if (ki >= 0 && r[7].indexOf(ki) < 0) continue;
      if (d) { var y = r[5], dd = +d; if (!y) continue; if (dd === 1900 ? y >= 1930 : (y < dd || y >= dd + 10)) continue; }
      if (a === "yes" && !(r[10] > 0)) continue;
      if (a === "no" && r[10] !== 0) continue;
      if (!siteOk(r, w)) continue;
      var score = 0;
      if (terms.length) {
        var nm = r._n, hay = r._h, ok = true;
        for (var t = 0; t < terms.length; t++) { if (hay.indexOf(terms[t]) < 0) { ok = false; break; } }
        if (!ok) continue;
        if (nm === q) score = 3; else if (nm.indexOf(q) === 0) score = 2; else if (nm.indexOf(q) >= 0) score = 1;
      }
      hits.push([score, r]);
    }
    hits.sort(function (x, y) {
      if (x[0] !== y[0]) return y[0] - x[0];
      var a1 = x[1], b1 = y[1];
      if (so === "name") return a1._n < b1._n ? -1 : 1;
      if (so === "new") return (b1[5] || 0) - (a1[5] || 0);
      if (so === "old") return (a1[5] || 9999) - (b1[5] || 9999);
      if (so === "wb") return (a1[10] > 0 ? a1[10] : 9999) - (b1[10] > 0 ? b1[10] : 9999);
      // best known first, and in the picture view festivals with a picture before those still waiting for one
      if (view === "grid") { var pa = st(a1) && st(a1)[0] ? 0 : 1, pb = st(b1) && st(b1)[0] ? 0 : 1; if (pa !== pb) return pa - pb; }
      return a1._i - b1._i;
    });
    shown = 0; $("results").innerHTML = "";
    $("results").className = "results " + view;
    $("count").textContent = hits.length.toLocaleString() + (hits.length === 1 ? " festival" : " festivals");
    more(); save();
  }
  function why(s) {
    if (TAKEN[s[2]]) return s[2] === "parked" ? "Address parked" : "Address taken over";
    if (s[2] === "no dns") return "Site gone";
    if (s[2] === "placeholder") return "Placeholder page";
    if (s[2] === "http 404" || s[2] === "http 410") return "Page gone";
    return "Did not load";
  }
  function badge(s) {
    if (!s) return "";
    if (s[0] === "w") return '<span class="badge">' + why(s) + " · archived look, " + s[1].slice(0, 4) + "</span>";
    if (!s[0] && lost(s)) return '<span class="badge none">' + why(s) + "</span>";
    return "";
  }
  function more() {
    var out = [];
    for (var i = shown; i < Math.min(shown + PAGE, hits.length); i++) {
      var r = hits[i][1], s = st(r);
      var where = [r[4], r[3]].filter(Boolean).join(", ");
      var meta = [where, r[5] ? "since " + r[5] + (r[6] ? " (ended " + r[6] + ")" : "") : ""].filter(Boolean).map(esc).join(" · ");
      var kinds = r[7].map(function (x) { return '<span class="k">' + esc(KINDS[x]) + "</span>"; }).join("");
      var wb = "";
      if (r[8]) {
        wb = '<a href="https://' + esc(r[8]) + '" rel="nofollow">' + esc(r[8].length > 32 ? r[8].slice(0, 30) + "…" : r[8]) + "</a>";
        if (r[10] > 0) wb += '<span>archived since ' + r[10] + "</span>";
        else if (r[10] === 0) wb += '<span class="no">not yet archived</span>';
      }
      if (view === "grid") {
        var img = s && s[0] ? '<img src="thumbs/' + r[14] + '.webp" alt="" loading="lazy" width="480" height="300" onerror="this.remove()">' : "";
        out.push('<li class="card"><a href="f/' + r[0] + '.html"><span class="ph' + (r[8] ? "" : " nosite") + '">' + img + badge(s) + '</span><b>' + esc(r[1]) + '</b><span class="m">' + meta + "</span></a></li>");
      } else {
        out.push('<li><a class="n" href="f/' + r[0] + '.html">' + esc(r[1]) + '</a><div class="w">' + wb + '</div><div class="m">' + meta + (kinds ? "<br>" + kinds : "") + "</div></li>");
      }
    }
    $("results").insertAdjacentHTML("beforeend", out.join(""));
    shown = Math.min(shown + PAGE, hits.length);
    $("more").hidden = shown >= hits.length;
  }
  function setView(v) {
    view = v;
    $("v-grid").setAttribute("aria-pressed", v === "grid"); $("v-list").setAttribute("aria-pressed", v === "list");
    run();
  }
  var idx = fetch("thumbs/index.json", {cache: "no-cache"}).then(function (r) { return r.ok ? r.json() : {s: {}}; }).catch(function () { return {s: {}}; });
  Promise.all([fetch("data.json").then(function (r) { return r.json(); }), idx]).then(function (res) {
    var d = res[0]; IDX = res[1].s || {};
    KINDS = d.kinds; ROWS = d.rows;
    ROWS.forEach(function (r, i) { r._i = i; r._n = norm(r[1]); r._h = norm(r[1] + " " + r[2] + " " + r[3] + " " + r[4] + " " + r[8]); });
    params();
    $("v-grid").setAttribute("aria-pressed", view === "grid"); $("v-list").setAttribute("aria-pressed", view === "list");
    run();
    var t;
    $("q").addEventListener("input", function () { clearTimeout(t); t = setTimeout(run, 120); });
    ["country", "kind", "decade", "arch", "site", "sort"].forEach(function (k) { $(k).addEventListener("change", run); });
    $("more").addEventListener("click", more);
    $("v-grid").addEventListener("click", function () { setView("grid"); });
    $("v-list").addEventListener("click", function () { setView("list"); });
    // the menu's "Lost sites" link while already on this page
    document.querySelectorAll('header nav a[href="index.html?site=lost"], header nav a[href="index.html"]').forEach(function (a) {
      a.addEventListener("click", function (e) {
        e.preventDefault();
        $("site").value = a.getAttribute("href") === "index.html" ? "" : "lost";
        if (a.getAttribute("href") === "index.html") KEYS.forEach(function (k) { $(k).value = k === "sort" ? "known" : ""; });
        run();
      });
    });
  });
})();
