// Soil column: water level, watering thresholds, and the 6-hour forecast marker.
(function () {
  var svg = document.getElementById("soil");
  if (!svg) return;
  var now = +svg.dataset.now, low = +svg.dataset.low, high = +svg.dataset.high;
  var pred = svg.dataset.pred === "" ? null : +svg.dataset.pred;
  var X = 70, W = 80, TOP = 20, H = 300, MAX = 60;
  var y = function (v) { return TOP + H - Math.max(0, Math.min(MAX, v)) / MAX * H; };
  var NS = "http://www.w3.org/2000/svg";
  function el(n, a, t) { var e = document.createElementNS(NS, n); for (var k in a) e.setAttribute(k, a[k]); if (t) e.textContent = t; svg.appendChild(e); return e; }

  var defs = el("defs", {});
  defs.innerHTML = '<linearGradient id="soilg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#C9A56B"/><stop offset="1" stop-color="#7A5A3A"/></linearGradient>' +
    '<linearGradient id="waterg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2E8FA3" stop-opacity=".92"/><stop offset="1" stop-color="#0C3B40" stop-opacity=".95"/></linearGradient>' +
    '<clipPath id="clip"><rect x="' + X + '" y="' + TOP + '" width="' + W + '" height="' + H + '" rx="6"/></clipPath>';
  el("rect", { x: X, y: TOP, width: W, height: H, rx: 6, fill: "url(#soilg)" });
  var water = el("rect", { x: X, y: TOP + H, width: W, height: 0, fill: "url(#waterg)", "clip-path": "url(#clip)" });
  el("rect", { x: X, y: TOP, width: W, height: H, rx: 6, fill: "none", stroke: "#12262A", "stroke-opacity": .35 });

  // comfort band between watering threshold and target
  el("rect", { x: X - 6, y: y(high), width: W + 12, height: y(low) - y(high), fill: "#D8B77A", "fill-opacity": .28 });
  el("line", { x1: X - 6, x2: X + W + 6, y1: y(low), y2: y(low), stroke: "#B5472E", "stroke-width": 1.6, "stroke-dasharray": "4 3" });
  el("text", { x: X - 12, y: y(low) + 4, "text-anchor": "end", class: "g-lab" }, "water at " + low + "%");
  el("text", { x: X - 12, y: y(high) + 4, "text-anchor": "end", class: "g-lab" }, "target " + high + "%");

  if (pred !== null) {
    var py = y(pred);
    el("path", { d: "M" + (X + W + 6) + " " + py + " l12 -7 v14 z", fill: pred < low ? "#B5472E" : "#4F8A5B" });
    el("text", { x: X + W + 22, y: py + 4, class: "g-lab" }, pred + "% in 6h");
  }
  // animate water rising once on load
  var target = y(now), start = TOP + H, t0 = null;
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function frame(t) {
    if (t0 === null) t0 = t;
    var p = reduce ? 1 : Math.min(1, (t - t0) / 900), e = 1 - Math.pow(1 - p, 3);
    var yy = start + (target - start) * e;
    water.setAttribute("y", yy); water.setAttribute("height", TOP + H - yy);
    if (p < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();

// Trend chart
(function () {
  var c = document.getElementById("trend");
  if (!c || !window.Chart) return;
  fetch(c.dataset.url).then(function (r) { return r.json(); }).then(function (d) {
    var low = +c.dataset.low, high = +c.dataset.high;
    new Chart(c, {
      type: "line",
      data: { labels: d.labels, datasets: [
        { label: "Soil moisture %", data: d.moisture, borderColor: "#0C3B40", backgroundColor: "rgba(46,143,163,.15)", fill: true, tension: .35, pointRadius: 0, borderWidth: 2 },
        { label: "Forecast for +6h", data: d.predicted, borderColor: "#B88B3E", borderDash: [5, 4], tension: .35, pointRadius: 0, borderWidth: 1.6 },
        { label: "Water below", data: d.labels.map(function () { return low; }), borderColor: "#B5472E", borderWidth: 1, pointRadius: 0 },
        { label: "Target", data: d.labels.map(function () { return high; }), borderColor: "#4F8A5B", borderWidth: 1, pointRadius: 0 }
      ]},
      options: { responsive: true, interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "bottom", labels: { boxWidth: 14, font: { family: "Figtree" } } } },
        scales: { x: { ticks: { maxTicksLimit: 6, font: { family: "Figtree" } }, grid: { display: false } },
                  y: { suggestedMin: 10, suggestedMax: 50, ticks: { callback: function (v) { return v + "%"; } } } } }
    });
  });
})();
