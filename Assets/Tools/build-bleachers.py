# Ann Arbor's bleachers, in the game's frame (metres east and south of Main St & Liberty St), written to
# Web/data/bleachers.json for bleachers.js:
#   bleachers  flat [cx, cz, heading, length, depth]   heading the way the seated face (radians, atan2(dx, dz)),
#              length along the rows, depth from the front row to the back
# From OpenStreetMap's leisure=bleachers (ODbL), each outline's smallest box, facing the nearest pitch or track; and a
# small set of three rows by each ball diamond (Web/data/ball-diamonds.json) that has none mapped within 60 m of home,
# out on the first-base side behind its low fence. The stadiums' own stands are the landmarks', left out here.
# Input: .lamp/reference/aa/osm.json (as fetch-annarbor.py fetched it: way[leisure] with geometry).
# Run: .lamp/reference/venv/bin/python -I Assets/Tools/build-bleachers.py <app folder>
import json, math, os, sys
from shapely.geometry import Polygon
from shapely.validation import make_valid

ROOT = sys.argv[1]
REF = os.path.join(ROOT, '.lamp/reference/aa')
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
xz = lambda lon, lat: ((lon - LON0) * KX, -(lat - LAT0) * KY)

ways = [e for e in json.load(open(os.path.join(REF, 'osm.json')))['elements'] if e['type'] == 'way' and len(e.get('geometry') or []) >= 4]
area = lambda e: make_valid(Polygon([xz(q['lon'], q['lat']) for q in e['geometry']]))
fields = [area(e).centroid for e in ways if e['tags'].get('leisure') in ('pitch', 'track')]
stadiums = [area(e) for e in ways if e['tags'].get('leisure') == 'stadium']

out, skipped = [], 0
for e in ways:
    if e['tags'].get('leisure') != 'bleachers':
        continue
    p = area(e)
    if p.is_empty or p.area < 4 or any(s.contains(p.centroid) for s in stadiums):
        skipped += 1
        continue
    box = list(p.minimum_rotated_rectangle.exterior.coords)[:4]
    e0 = (box[1][0] - box[0][0], box[1][1] - box[0][1])
    e1 = (box[2][0] - box[1][0], box[2][1] - box[1][1])
    L0, L1 = math.hypot(*e0), math.hypot(*e1)
    length, depth, ax = (L0, L1, e0) if L0 >= L1 else (L1, L0, e1)
    c = p.minimum_rotated_rectangle.centroid
    # facing: across the rows, toward the nearest field
    nx, nz = -ax[1] / (math.hypot(*ax) or 1), ax[0] / (math.hypot(*ax) or 1)
    near = min(fields, key=lambda f: f.distance(c), default=None)
    if near is not None and (near.x - c.x) * nx + (near.y - c.y) * nz < 0:
        nx, nz = -nx, -nz
    out += [round(c.x, 2), round(c.y, 2), round(math.atan2(nx, nz), 3), round(min(40, length), 1), round(min(8, max(1.8, depth)), 1)]
mapped = len(out) // 5

D = json.load(open(os.path.join(ROOT, 'Web/data/ball-diamonds.json')))['diamonds']
for i in range(0, len(D), 6):
    hx, hz, h, depth, base, lit = D[i:i + 6]
    if any(math.hypot(out[k] - hx, out[k + 1] - hz) < 60 for k in range(0, mapped * 5, 5)):
        continue
    # down the first-base line past the bench, behind the line fence, facing across toward the line
    s = 1 if (i // 6) % 2 == 0 else -1  # some on the third-base side
    fx, fz, rx, rz = math.sin(h), math.cos(h), -math.cos(h), math.sin(h)
    off = 8.95  # the middle of its rows, a metre behind the line fence
    a, b = (base * 0.95 - off) * 0.7071, s * (base * 0.95 + off) * 0.7071
    cx, cz = hx + fx * a + rx * b, hz + fz * a + rz * b
    # facing the line: back toward the field's middle, across the line
    na, nb = 0.7071, -s * 0.7071
    out += [round(cx, 2), round(cz, 2), round(math.atan2(fx * na + rx * nb, fz * na + rz * nb), 3), 4.6 if base < 20 else 7.0, 1.9]

path = os.path.join(ROOT, 'Web/data/bleachers.json')
json.dump({'bleachers': out}, open(path, 'w'), separators=(',', ':'))
print(f'{mapped} mapped bleachers, {len(out) // 5 - mapped} by ball diamonds, skipped {skipped}, {os.path.getsize(path)} bytes')
