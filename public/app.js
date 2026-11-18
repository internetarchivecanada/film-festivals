(function () {
  var $ = function (id) { return document.getElementById(id); };
  var KINDS = [], ROWS = [], shown = 0, hits = [];
  var PAGE = 50;
  function norm(s) { return (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function params() {
    var p = new URLSearchParams(location.search);
    ["q", "country", "kind", "decade", "arch", "sort"].forEach(function (k) { if (p.get(k)) $(k).value = p.get(k); });
  }
  function save() {
    var p = new URLSearchParams();
    ["q", "country", "kind", "decade", "arch", "sort"].forEach(function (k) { if ($(k).value && !(k === "sort" && $(k).value === "known")) p.set(k, $(k).value); });
    var s = p.toString();
    history.replaceState(null, "", s ? "?" + s : location.pathname);
  }
  function run() {
    var q = norm($("q").value.trim()), terms = q ? q.split(/\s+/) : [];
    var c = $("country").value, k = $("kind").value, d = $("decade").value, a = $("arch").value, so = $("sort").value;
    var ki = k ? KINDS.indexOf(k) : -1;
    hits = [];
    for (var i = 0; i < ROWS.length; i++) {
      var r = ROWS[i];
      if (c && r[3] !== c) continue;
      if (ki >= 0 && r[7].indexOf(ki) < 0) continue;
      if (d) { var y = r[5], dd = +d; if (!y) continue; if (dd === 1900 ? y >= 1930 : (y < dd || y >= dd + 10)) continue; }
      if (a === "yes" && !(r[10] > 0)) continue;
      if (a === "no" && r[10] !== 0) continue;
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
      return 0;   // rows arrive best-known first
    });
    shown = 0; $("results").innerHTML = "";
    $("count").textContent = hits.length.toLocaleString() + (hits.length === 1 ? " festival" : " festivals");
    more(); save();
  }
  function more() {
    var out = [];
    for (var i = shown; i < Math.min(shown + PAGE, hits.length); i++) {
      var r = hits[i][1];
      var where = [r[4], r[3]].filter(Boolean).join(", ");
      var meta = [where, r[5] ? "since " + r[5] + (r[6] ? " (ended " + r[6] + ")" : "") : ""].filter(Boolean).map(esc).join(" · ");
      var kinds = r[7].map(function (x) { return '<span class="k">' + esc(KINDS[x]) + "</span>"; }).join("");
      var wb = "";
      if (r[8]) {
        wb = '<a href="https://' + esc(r[8]) + '" rel="nofollow">' + esc(r[8].length > 32 ? r[8].slice(0, 30) + "…" : r[8]) + "</a>";
        if (r[10] > 0) wb += '<span>archived since ' + r[10] + "</span>";
        else if (r[10] === 0) wb += '<span class="no">not yet archived</span>';
      }
      out.push('<li><a class="n" href="f/' + r[0] + '.html">' + esc(r[1]) + '</a><div class="w">' + wb + '</div><div class="m">' + meta + (kinds ? "<br>" + kinds : "") + "</div></li>");
    }
    $("results").insertAdjacentHTML("beforeend", out.join(""));
    shown = Math.min(shown + PAGE, hits.length);
    $("more").hidden = shown >= hits.length;
  }
  fetch("data.json").then(function (r) { return r.json(); }).then(function (d) {
    KINDS = d.kinds; ROWS = d.rows;
    ROWS.forEach(function (r) { r._n = norm(r[1]); r._h = norm(r[1] + " " + r[2] + " " + r[3] + " " + r[4] + " " + r[8]); });
    params(); run();
    var t;
    $("q").addEventListener("input", function () { clearTimeout(t); t = setTimeout(run, 120); });
    ["country", "kind", "decade", "arch", "sort"].forEach(function (k) { $(k).addEventListener("change", run); });
    $("more").addEventListener("click", more);
  });
})();
