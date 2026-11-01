# The roof shapes OpenStreetMap's mappers have tagged on Ann Arbor's buildings (roof:shape, ODbL), in the game's frame
# (metres east and south of Main St & Liberty St), written to Web/data/roof-shapes.json for houses.js: flat
# [x, z, shape] at each building's centre, the shape 1 gabled, 2 hipped (and pyramidal), 3 flat, 4 gambrel,
# 5 half-hipped, 6 skillion. houses.js gives the house whose footprint holds that point the tagged roof.
# Input: .lamp/reference/aa/roofs/roofs.json (Overpass: way[building][roof:shape] in Ann Arbor, out tags center).
# Run: python -I Assets/Tools/build-roof-shapes.py <app folder>
import json, math, os, sys

ROOT = sys.argv[1]
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5

SHAPE = {'gabled': 1, 'hipped': 2, 'pyramidal': 2, 'flat': 3, 'gambrel': 4, 'half-hipped': 5, 'skillion': 6}

out, n = [], {}
for e in json.load(open(os.path.join(ROOT, '.lamp/reference/aa/roofs/roofs.json')))['elements']:
    s = SHAPE.get(e.get('tags', {}).get('roof:shape'))
    c = e.get('center')
    if not s or not c:
        continue
    out += [round((c['lon'] - LON0) * KX, 1), round(-(c['lat'] - LAT0) * KY, 1), s]
    n[s] = n.get(s, 0) + 1

json.dump(out, open(os.path.join(ROOT, 'Web/data/roof-shapes.json'), 'w'), separators=(',', ':'))
print(len(out) // 3, 'roofs', sorted(n.items()))
