(function () {
  var map = L.map("map", {worldCopyJump: true}).setView([30, 10], 2);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  }).addTo(map);
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  fetch("data.json").then(function (r) { return r.json(); }).then(function (d) {
    var g = L.markerClusterGroup({chunkedLoading: true, maxClusterRadius: 50});
    d.rows.forEach(function (r) {
      if (r[11] == null) return;
      var m = L.marker([r[11], r[12]], {title: r[1]});
      m.bindPopup(function () {
        var img = r[14] ? '<a href="f/' + r[0] + '.html" class="pop-ph" tabindex="-1"><img src="thumbs/' + r[14] + '.webp" alt="" width="240" height="150" onerror="this.parentNode.remove()"></a>' : "";
        return img + '<a href="f/' + r[0] + '.html"><b>' + esc(r[1]) + "</b></a><br>" + esc([r[4], r[3]].filter(Boolean).join(", ")) + (r[5] ? "<br>since " + r[5] : "");
      }, {minWidth: 240});
      g.addLayer(m);
    });
    map.addLayer(g);
  });
})();
