import json
import urllib.request
from pathlib import Path

with urllib.request.urlopen(
    "https://raw.githubusercontent.com/georgique/world-geojson/master/countries/morocco.json"
) as r:
    gj = json.load(r)

geom = gj["features"][0]["geometry"]
ring = geom["coordinates"][0]
xs = [p[0] for p in ring]
ys = [p[1] for p in ring]
# Slight pad so Tangier tip isn't clipped
minx, maxx = min(xs) - 0.3, max(xs) + 0.3
miny, maxy = min(ys) - 0.2, max(ys) + 0.15
print("bounds", minx, maxx, miny, maxy, "pts", len(ring))

pad = 16
W, H = 480, 560


def px(lon: float, lat: float) -> tuple[float, float]:
    x = pad + (lon - minx) / (maxx - minx) * (W - 2 * pad)
    y = pad + (maxy - lat) / (maxy - miny) * (H - 2 * pad)
    return x, y


step = max(1, len(ring) // 110)
pts = [px(lon, lat) for lon, lat in ring[::step]]
if pts[0] != pts[-1]:
    pts.append(pts[0])
path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + " Z"
print("PATH")
print(path)
print("CITIES")
cities = {
    "Tanger": (-5.83, 35.76),
    "Tetouan": (-5.37, 35.58),
    "Larache": (-6.15, 35.19),
    "Chefchaouen": (-5.27, 35.17),
    "Al Hoceima": (-3.93, 35.25),
    "Ouazzane": (-5.58, 34.80),
    "Kenitra": (-6.58, 34.26),
    "Rabat": (-6.84, 34.02),
    "Temara": (-6.90, 33.93),
    "Sidi Slimane": (-5.93, 34.26),
    "Sidi Kacem": (-5.71, 34.22),
    "Khemisset": (-6.07, 33.82),
}
for name, (lon, lat) in cities.items():
    x, y = px(lon, lat)
    print(f"{name}|{x/W*100:.1f}|{y/H*100:.1f}")

Path("data/morocco_outline.path.txt").write_text(path, encoding="utf-8")
Path("data/morocco_pins.txt").write_text(
    "\n".join(
        f"{n}|{px(lon, lat)[0]/W*100:.1f}|{px(lon, lat)[1]/H*100:.1f}"
        for n, (lon, lat) in cities.items()
    ),
    encoding="utf-8",
)
print("viewBox", f"0 0 {W} {H}")
