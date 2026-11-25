
// Explore regions: Leaflet map + Nominatim search + Open-Meteo conditions + Wikipedia summary.
(function () {
  var pins = JSON.parse(document.getElementById("pins").textContent);

  var map = L.map("map", { zoomControl: true }).setView([22.5, 79], 5);

  L.tileLayer(
    "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=cb1_5fn2_1_5c8e2e45d40b9314704318a3",
    {
      maxZoom: 20,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attribution/">CARTO</a>'
    }
  ).addTo(map);

  var info = document.getElementById("info");
  var list = document.getElementById("results");
  var marker = null;
  var current = { area: null };

  var CROPS = {
    Millet: [24, 36, 400],
    Tomato: [30, 42, 400],
    Groundnut: [24, 36, 500],
    Wheat: [28, 40, 600],
    Maize: [28, 40, 600],
    Rice: [40, 55, 200],
    Cotton: [26, 38, 700],
    Sugarcane: [30, 42, 700],
    Other: [28, 40, 400]
  };

  function h(tag, attrs, text) {
    var e = document.createElement(tag);

    for (var k in (attrs || {})) {
      e.setAttribute(k, attrs[k]);
    }

    if (text !== undefined) e.textContent = text;

    return e;
  }

  function getJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(r.status);
      return r.json();
    });
  }

  function sum(a) {
    return a.reduce(function (x, y) {
      return x + (y || 0);
    }, 0);
  }

  // Your fields
  var chips = document.getElementById("chips");

  pins.forEach(function (p) {
    if (p.boundary) {
      L.polygon(p.boundary, {
        color: "#0C3B40",
        weight: 2,
        fillColor: "#D8B77A",
        fillOpacity: 0.4
      }).addTo(map);
    }

    L.circleMarker([p.lat, p.lng], {
      radius: 9,
      color: "#0C3B40",
      weight: 2,
      fillColor: "#D8B77A",
      fillOpacity: 1
    })
      .addTo(map)
      .bindPopup("<strong></strong><br>" + "<a href='" + p.url + "'>Open field</a>")
      .on("popupopen", function (e) {
        e.popup.getElement().querySelector("strong").textContent =
          p.name + " (" + p.crop + ")";
      });

    var b = h("button", { type: "button", "class": "chip" }, p.name);

    b.addEventListener("click", function () {
      select(p.lat, p.lng, p.location, p.name);
    });

    chips.appendChild(b);
  });

  // Search
  document.getElementById("search").addEventListener("submit", function (ev) {
    ev.preventDefault();

    var q = document.getElementById("q").value.trim();

    if (!q) return;

    list.hidden = false;
    list.replaceChildren(h("li", { "class": "note" }, "Searching..."));

    getJSON(
      "https://nominatim.openstreetmap.org/search?format=jsonv2&addressdetails=1&limit=6&q=" +
      encodeURIComponent(q)
    )
      .then(function (rows) {
        list.replaceChildren();

        if (!rows.length) {
          list.appendChild(
            h(
              "li",
              { "class": "note" },
              "No match. Try a nearby city, or add the state or country."
            )
          );
          return;
        }

        rows.forEach(function (r) {
          var li = h("li");
          var btn = h("button", { type: "button" });

          btn.appendChild(
            h("strong", {}, r.name || r.display_name.split(",")[0])
          );

          btn.appendChild(h("span", {}, r.display_name));

          btn.addEventListener("click", function () {
            list.hidden = true;

            select(
              +r.lat,
              +r.lon,
              r.display_name,
              r.name,
              r.boundingbox
            );
          });

          li.appendChild(btn);
          list.appendChild(li);
        });

        if (rows.length === 1) {
          list.firstChild.firstChild.click();
        }
      })
      .catch(function () {
        list.replaceChildren(
          h(
            "li",
            { "class": "note" },
            "Search is unavailable right now. Check your connection and try again."
          )
        );
      });
  });

  // Click the map to inspect
  map.on("click", function (e) {
    if (drawing) return;

    getJSON(
      "https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=10&lat=" +
      e.latlng.lat +
      "&lon=" +
      e.latlng.lng
    )
      .then(function (r) {
        select(
          e.latlng.lat,
          e.latlng.lng,
          r.display_name || "Selected point",
          r.name
        );
      })
      .catch(function () {
        select(
          e.latlng.lat,
          e.latlng.lng,
          "Selected point",
          "Selected point"
        );
      });
  });

  function select(lat, lon, fullName, shortName, bbox, noMove) {
    current.area = null;

    if (marker) map.removeLayer(marker);

    marker = L.circleMarker([lat, lon], {
      radius: 8,
      color: "#fff",
      weight: 2,
      fillColor: "#B5472E",
      fillOpacity: 1
    }).addTo(map);

    if (noMove) {
      // Keep the user's view while outlining land.
    } else if (bbox) {
      map.fitBounds(
        [
          [+bbox[0], +bbox[2]],
          [+bbox[1], +bbox[3]]
        ],
        { maxZoom: 11 }
      );
    } else {
      map.setView([lat, lon], Math.max(map.getZoom(), 9));
    }

    var title = shortName || (fullName || "").split(",")[0];

    info.replaceChildren(
      h("h3", {}, title),
      h("p", { "class": "note" }, fullName || ""),
      h("p", { "class": "note" }, "Loading local conditions...")
    );

    load(lat, lon, title, fullName);
  }

  function load(lat, lon, title, fullName) {
    var wx =
      "https://api.open-meteo.com/v1/forecast?latitude=" +
      lat +
      "&longitude=" +
      lon +
      "&current=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation" +
      "&hourly=soil_moisture_3_to_9cm&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration" +
      "&timezone=auto&forecast_days=7";

    var wiki =
      "https://en.wikipedia.org/api/rest_v1/page/summary/" +
      encodeURIComponent(title.replace(/ /g, "_"));

    Promise.all([
      getJSON(wx),
      getJSON(wiki).catch(function () {
        return null;
      })
    ])
      .then(function (res) {
        render(lat, lon, title, fullName, res[0], res[1]);
      })
      .catch(function () {
        info.replaceChildren(
          h("h3", {}, title),
          h("p", { "class": "note" }, fullName || ""),
          h(
            "p",
            { "class": "alert warning" },
            "Local conditions could not be loaded. Check your connection and try again."
          )
        );
      });
  }

  function render(lat, lon, title, fullName, w, wk) {
    var c = w.current;
    var d = w.daily;

    var rain = sum(d.precipitation_sum);
    var et = sum(d.et0_fao_evapotranspiration);
    var bal = rain - et;

    var hourIdx = Math.min(
      new Date().getHours(),
      (w.hourly.soil_moisture_3_to_9cm || []).length - 1
    );

    var sm = (w.hourly.soil_moisture_3_to_9cm || [])[hourIdx];

    var out = [
      h("h3", {}, title),
      h("p", { "class": "note" }, fullName || "")
    ];

    if (wk && wk.extract) {
      out.push(
        h(
          "p",
          { "class": "wiki" },
          wk.extract.length > 330
            ? wk.extract.slice(0, 330).replace(/\s+\S*$/, "") + "..."
            : wk.extract
        )
      );
    }

    var dl = h("dl", { "class": "facts two" });

    [
      ["Temperature", c.temperature_2m + "°C"],
      ["Humidity", c.relative_humidity_2m + "%"],
      ["Wind", c.wind_speed_10m + " km/h"],
      ["Elevation", Math.round(w.elevation) + " m"],
      [
        "Soil moisture (topsoil)",
        sm != null ? (sm * 100).toFixed(0) + "%" : "n/a"
      ],
      ["Coordinates", lat.toFixed(3) + ", " + lon.toFixed(3)]
    ].forEach(function (r) {
      var box = h("div");

      box.appendChild(h("dt", {}, r[0]));
      box.appendChild(h("dd", {}, r[1]));

      dl.appendChild(box);
    });

    out.push(dl);

    // 7-day water outlook: rain vs crop water demand
    out.push(h("h4", {}, "Next 7 days: rain vs. water demand"));

    var maxV = Math.max(
      5,
      Math.max.apply(
        null,
        d.precipitation_sum.concat(d.et0_fao_evapotranspiration)
      )
    );

    var chart = h("div", { "class": "bars" });

    d.time.forEach(function (t, i) {
      var col = h("div", {
        "class": "bar",
        title:
          t +
          ": rain " +
          d.precipitation_sum[i] +
          " mm, demand " +
          d.et0_fao_evapotranspiration[i] +
          " mm"
      });

      var r = h("i", { "class": "rain" });
      var e = h("i", { "class": "et" });

      r.style.height = (d.precipitation_sum[i] / maxV * 100) + "%";
      e.style.height =
        (d.et0_fao_evapotranspiration[i] / maxV * 100) + "%";

      col.appendChild(r);
      col.appendChild(e);

      col.appendChild(
        h(
          "span",
          {},
          new Date(t).toLocaleDateString(undefined, { weekday: "short" })
        )
      );

      chart.appendChild(col);
    });

    out.push(chart);

    var key = h("p", { "class": "key" });

    key.appendChild(h("span", { "class": "k rain" }));
    key.appendChild(document.createTextNode(" Rain   "));

    key.appendChild(h("span", { "class": "k et" }));
    key.appendChild(
      document.createTextNode(" Crop water demand (ET₀)")
    );

    out.push(key);

    var msg =
      bal >= 0
        ? "Rain (" +
          rain.toFixed(0) +
          " mm) should cover crop demand (" +
          et.toFixed(0) +
          " mm) this week. Irrigation can wait."
        : "Expect a shortfall of about " +
          Math.abs(bal).toFixed(0) +
          " mm this week (rain " +
          rain.toFixed(0) +
          " mm, demand " +
          et.toFixed(0) +
          " mm). Plan to irrigate.";

    out.push(
      h("p", { "class": "alert " + (bal >= 0 ? "info" : "warning") }, msg)
    );

    if (current.area) {
      out.splice(
        2,
        0,
        areaSummary(current.area),
        buildForm(current.area, title, fullName)
      );
    }

    info.replaceChildren.apply(info, out);
  }

  // ---- Select an area on the map and add it as a field
  var drawing = false;
  var pts = [];
  var layer = L.layerGroup().addTo(map);
  var shape = null;

  var $ = function (id) {
    return document.getElementById(id);
  };

  var bStart = $("d-start");
  var bUndo = $("d-undo");
  var bFinish = $("d-finish");
  var bClear = $("d-clear");
  var hint = $("d-hint");

  function geodesicArea(p) {
    // m2, spherical polygon
    var d2r = Math.PI / 180;
    var R = 6378137;
    var a = 0;
    var n = p.length;

    if (n < 3) return 0;

    for (var i = 0; i < n; i++) {
      var p1 = p[i];
      var p2 = p[(i + 1) % n];

      a +=
        (p2.lng - p1.lng) *
        d2r *
        (2 + Math.sin(p1.lat * d2r) + Math.sin(p2.lat * d2r));
    }

    return Math.abs(a * R * R / 2);
  }

  function ui() {
    bStart.hidden = drawing;
    bUndo.hidden = bFinish.hidden = bClear.hidden = !drawing;
    map.getContainer().style.cursor = drawing ? "crosshair" : "";
  }

  function redraw() {
    layer.clearLayers();

    pts.forEach(function (p) {
      L.circleMarker(p, {
        radius: 4,
        color: "#0C3B40",
        fillColor: "#fff",
        fillOpacity: 1,
        weight: 2
      }).addTo(layer);
    });

    if (pts.length > 1) {
      shape = (pts.length > 2 ? L.polygon : L.polyline)(pts, {
        color: "#0C3B40",
        weight: 2,
        dashArray: "5 4",
        fillColor: "#D8B77A",
        fillOpacity: 0.4
      }).addTo(layer);
    }

    if (pts.length >= 3) {
      hint.textContent =
        "About " +
        (
          geodesicArea(
            pts.map(function (p) {
              return L.latLng(p);
            })
          ) / 10000
        ).toFixed(2) +
        " ha so far. Press Finish area when done.";
    } else {
      hint.textContent =
        "Click each corner of your land (" +
        pts.length +
        " placed, 3 needed).";
    }
  }

  function reset() {
    drawing = false;
    pts = [];
    layer.clearLayers();
    hint.textContent =
      "Zoom to your land first, then outline it point by point.";
    ui();
  }

  bStart.addEventListener("click", function () {
    current.area = null;
    reset();
    drawing = true;
    ui();
    redraw();
  });

  bUndo.addEventListener("click", function () {
    pts.pop();
    redraw();
  });

  bClear.addEventListener("click", reset);
  bFinish.addEventListener("click", finish);

  document.addEventListener("keydown", function (e) {
    if (drawing && e.key === "Escape") reset();
  });

  map.on("click", function (e) {
    if (drawing) {
      pts.push([e.latlng.lat, e.latlng.lng]);
      redraw();
    }
  });

  function finish() {
    if (pts.length < 3) {
      hint.textContent = "Place at least 3 points to outline an area.";
      return;
    }

    var ll = pts.map(function (p) {
      return L.latLng(p);
    });

    var ha = geodesicArea(ll) / 10000;
    var c = L.latLngBounds(ll).getCenter();

    var area = {
      pts: pts.slice(),
      ha: ha,
      lat: c.lat,
      lng: c.lng
    };

    drawing = false;
    ui();

    hint.textContent =
      "Area selected. Fill in the field details on the right.";

    if (shape) layer.removeLayer(shape);

    L.polygon(pts, {
      color: "#B5472E",
      weight: 2,
      fillColor: "#D8B77A",
      fillOpacity: 0.45
    }).addTo(layer);

    getJSON(
      "https://nominatim.openstreetmap.org/reverse?format=jsonv2&zoom=10&lat=" +
      c.lat +
      "&lon=" +
      c.lng
    )
      .catch(function () {
        return {};
      })
      .then(function (r) {
        select(
          c.lat,
          c.lng,
          r.display_name || "Selected area",
          r.name ||
            (r.display_name || "Selected area").split(",")[0],
          null,
          true
        );

        current.area = area;
      });
  }

  function areaSummary(a) {
    var box = h(
      "p",
      { "class": "alert info" },
      "Selected area: " +
        a.ha.toFixed(2) +
        " ha (" +
        Math.round(a.ha * 10000).toLocaleString() +
        " m²), " +
        a.pts.length +
        " corners."
    );

    return box;
  }

  function buildForm(a, title, fullName) {
    var wrap = h("div", { "class": "addfield" });

    wrap.appendChild(h("h4", {}, "Add this area as a field"));

    var f = h("form", {
      method: "post",
      action: $("csrf").dataset.url,
      "class": "fieldform"
    });

    var tok = $("csrf").querySelector(
      "input[name=csrfmiddlewaretoken]"
    );

    if (tok) f.appendChild(tok.cloneNode());

    function hid(n, v) {
      var i = h("input", { type: "hidden", name: n });
      i.value = v;
      f.appendChild(i);
    }

    hid("latitude", a.lat.toFixed(6));
    hid("longitude", a.lng.toFixed(6));

    hid(
      "boundary",
      JSON.stringify(
        a.pts.map(function (p) {
          return [+p[0].toFixed(6), +p[1].toFixed(6)];
        })
      )
    );

    hid(
      "location",
      (fullName || title).split(",").slice(0, 3).join(",").trim()
    );

    function lab(text, input) {
      var l = h("label", {}, text);
      l.appendChild(input);
      f.appendChild(l);
      return input;
    }

    function num(n, v, min, max, step) {
      var i = h("input", {
        type: "number",
        name: n,
        min: min,
        step: step || "any",
        required: ""
      });

      if (max) i.max = max;
      i.value = v;

      return i;
    }

    var name = lab(
      "Field name",
      h("input", {
        type: "text",
        name: "name",
        maxlength: 80,
        required: ""
      })
    );

    name.value = title + " field";

    var crop = h("select", { name: "crop" });

    Object.keys(CROPS).forEach(function (k) {
      crop.appendChild(h("option", { value: k }, k));
    });

    lab("Crop", crop);

    lab(
      "Area (hectares)",
      num("area_ha", a.ha.toFixed(2), 0.01, 9999, 0.01)
    );

    var low = lab("Water below (%)", num("moisture_low", 24, 0, 99));
    var high = lab("Refill to (%)", num("moisture_high", 36, 1, 100));

    lab("Root depth (mm)", num("root_depth_mm", 400, 50, 3000, 10));

    lab(
      "Drip flow (litres per hour)",
      num("flow_lph", 20000, 100, null, 100)
    );

    var planted = lab(
      "Planting date",
      h("input", { type: "date", name: "planted_on" })
    );

    planted.value = $("csrf").dataset.today || "";

    lab(
      "Alert phone (optional)",
      h("input", {
        type: "tel",
        name: "contact_phone",
        placeholder: "+919876543210",
        pattern: "\\+?[0-9]{8,15}"
      })
    );

    var lang = h("select", { name: "language" });

    [
      ["en", "English"],
      ["hi", "हिन्दी"],
      ["te", "తెలుగు"]
    ].forEach(function (l) {
      lang.appendChild(h("option", { value: l[0] }, l[1]));
    });

    lab("Alert language", lang);

    function preset() {
      var c = CROPS[crop.value];
      low.value = c[0];
      high.value = c[1];
    }

    crop.addEventListener("change", preset);
    crop.value = "Millet";
    preset();

    f.addEventListener("submit", function (ev) {
      if (+low.value >= +high.value) {
        ev.preventDefault();
        low.setCustomValidity("Must be lower than the refill level");
        low.reportValidity();
      } else {
        low.setCustomValidity("");
      }
    });

    f.appendChild(h("button", { "class": "btn" }, "Add field"));

    wrap.appendChild(f);

    return wrap;
  }
})();
