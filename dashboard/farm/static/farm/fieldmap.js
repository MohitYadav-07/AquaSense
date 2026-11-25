
// Mini map on the field page: outline of the field, or a pin if no outline was drawn.
(function () {
  var el = document.getElementById("fmap");
  var raw = document.getElementById("geo");

  if (!el || !raw || !window.L) return;

  var g = JSON.parse(raw.textContent);
  var m = L.map(el, { scrollWheelZoom: false });

  L.tileLayer(
    "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=cb1_5fn2_1_5c8e2e45d40b9314704318a3",
    {
      maxZoom: 20,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attribution/">CARTO</a>'
    }
  ).addTo(m);

  if (g.boundary) {
    var p = L.polygon(g.boundary, {
      color: "#0C3B40",
      weight: 2,
      fillColor: "#D8B77A",
      fillOpacity: 0.45
    }).addTo(m);

    m.fitBounds(p.getBounds(), { padding: [24, 24] });
  } else {
    m.setView([g.lat, g.lng], 14);

    L.circleMarker([g.lat, g.lng], {
      radius: 9,
      color: "#0C3B40",
      weight: 2,
      fillColor: "#D8B77A",
      fillOpacity: 1
    }).addTo(m);
  }
})();
