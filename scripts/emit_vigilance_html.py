"""Emit vigilance map HTML fragment with real Morocco outline."""
from pathlib import Path

# Full Morocco incl. Sahara (johan world.geo.json projected)
PATH = Path("data/morocco_outline.path.txt").read_text(encoding="utf-8").strip()

# Prefer full-country path: regenerate quickly inline
import json
import urllib.request

with urllib.request.urlopen(
    "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/MAR.geo.json"
) as r:
    gj = json.load(r)

geom = gj["features"][0]["geometry"]
ring = geom["coordinates"][0]
xs = [p[0] for p in ring]
ys = [p[1] for p in ring]
minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
pad, W, H = 16, 420, 560


def px(lon, lat):
    x = pad + (lon - minx) / (maxx - minx) * (W - 2 * pad)
    y = pad + (maxy - lat) / (maxy - miny) * (H - 2 * pad)
    return x, y


step = max(1, len(ring) // 70)
pts = [px(lon, lat) for lon, lat in ring[::step]]
if pts[0] != pts[-1]:
    pts.append(pts[0])
path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"

cities = [
    ("Tanger", -5.83, 35.76),
    ("Tetouan", -5.37, 35.58),
    ("Larache", -6.15, 35.19),
    ("Chefchaouen", -5.27, 35.17),
    ("Al Hoceima", -3.93, 35.25),
    ("Ouazzane", -5.58, 34.80),
    ("Kenitra", -6.58, 34.26),
    ("Rabat", -6.84, 34.02),
    ("Temara", -6.90, 33.93),
    ("Sidi Slimane", -5.93, 34.26),
    ("Sidi Kacem", -5.71, 34.22),
    ("Khemisset", -6.07, 33.82),
]

labels = {
    "Tanger": "Tanger",
    "Tetouan": "Tétouan",
    "Larache": "Larache",
    "Chefchaouen": "Chefchaouen",
    "Al Hoceima": "Al Hoceima",
    "Ouazzane": "Ouazzane",
    "Kenitra": "Kénitra",
    "Rabat": "Rabat",
    "Temara": "Témara",
    "Sidi Slimane": "S. Slimane",
    "Sidi Kacem": "S. Kacem",
    "Khemisset": "Khémisset",
}

pins = []
for name, lon, lat in cities:
    x, y = px(lon, lat)
    hub = " map-pin--hub" if name == "Rabat" else ""
    pins.append(
        f'            <button type="button" class="map-pin{hub}" style="left:{x/W*100:.1f}%;top:{y/H*100:.1f}%" data-place="{name}">{labels[name]}</button>'
    )

html = f'''        <div class="vigilance__board" id="vigilance-map">
          <svg viewBox="0 0 {W} {H}" role="img" aria-label="Carte du Maroc — provinces DRMNO">
            <defs>
              <linearGradient id="ocean" x1="0" y1="0" x2="0.8" y2="1">
                <stop offset="0%" stop-color="#9ec9dc" />
                <stop offset="55%" stop-color="#7eb4cd" />
                <stop offset="100%" stop-color="#5a96b4" />
              </linearGradient>
              <linearGradient id="land" x1="0.2" y1="0" x2="0.9" y2="1">
                <stop offset="0%" stop-color="#eef6e8" />
                <stop offset="40%" stop-color="#d8e8c8" />
                <stop offset="100%" stop-color="#c5d6a6" />
              </linearGradient>
              <linearGradient id="drmnoFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#0c6b84" stop-opacity="0.38" />
                <stop offset="100%" stop-color="#0c6b84" stop-opacity="0.05" />
              </linearGradient>
              <filter id="softShadow" x="-12%" y="-8%" width="130%" height="130%">
                <feDropShadow dx="0" dy="5" stdDeviation="7" flood-color="#12304a" flood-opacity="0.2" />
              </filter>
              <clipPath id="moroccoClip">
                <path d="{path}" />
              </clipPath>
            </defs>

            <rect class="map-ocean" width="{W}" height="{H}" />

            <path class="map-neighbor" d="M270,2 C290,-1 312,5 328,14 L318,28 C300,18 282,12 270,16 Z" />

            <path class="map-land" filter="url(#softShadow)" d="{path}" />

            <ellipse class="map-drmno" clip-path="url(#moroccoClip)" cx="300" cy="55" rx="95" ry="55" />

            <text class="map-zone-label" x="300" y="78">DRMNO</text>
            <text class="map-country-label" x="250" y="230">MAROC</text>
            <text class="map-sahara-label" x="70" y="480">Sahara</text>
          </svg>

          <div class="map-pins">
{chr(10).join(pins)}
          </div>
        </div>
'''

Path("data/vigilance_map_fragment.html").write_text(html, encoding="utf-8")
print(html[:400])
print("...")
print("pins", len(pins), "path len", len(path))
