# Ann Arbor's railroad crossings: OpenStreetMap's railway=level_crossing nodes (where a street crosses the tracks at
# grade, ODbL), fetched once from Overpass into .lamp/reference/aa/rail/level_crossings.json:
#   [out:json];node["railway"~"^(level_crossing|crossing)$"](42.21,-83.83,42.33,-83.65);out body;
# Written to Web/data/rail-crossings.json as flat [x, z, gates (1 gates, 0 only lights and crossbucks)] in the game's
# frame (metres east and south of Main St & Liberty St). railways.js finds the street and the track at each.
# Run: python -I Assets/Tools/build-rail-crossings.py <app folder>
import json, math, os, sys

ROOT = sys.argv[1]
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5

els = json.load(open(os.path.join(ROOT, '.lamp/reference/aa/rail/level_crossings.json')))['elements']
out = []
for e in els:
    t = e.get('tags', {})
    if t.get('railway') != 'level_crossing':
        continue
    x, z = (e['lon'] - LON0) * KX, -(e['lat'] - LAT0) * KY
    # OpenStreetMap leaves out the gates at most of the town's crossings (crossing:barrier=no); the game gives every
    # crossing gates, as asked
    gates = 1
    out += [round(x, 1), round(z, 1), gates]
json.dump(out, open(os.path.join(ROOT, 'Web/data/rail-crossings.json'), 'w'), separators=(',', ':'))
print(f'{len(out) // 3} railroad crossings')
