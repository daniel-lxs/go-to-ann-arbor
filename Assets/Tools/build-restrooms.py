# Ann Arbor's public restrooms, in the game's frame (metres east and south of Main St & Liberty St), written to
# Web/data/restrooms.json for restrooms.js:
#   buildings  flat [cx, cz, ux, uz, length, width, shelter]   a restroom building's smallest box, (ux, uz) along its
#              length; shelter 1 where the map says its roof is a shelter too (a deep overhang)
#   points     flat [x, z, portable]   a restroom mapped as a point: portable 1 where its toilets are chemical (a
#              portable toilet), else 0 (a small restroom, drawn only where it isn't inside a building: restrooms.js)
# From OpenStreetMap's amenity=toilets (ODbL). Rooms inside buildings (indoor=*, level=*) are left out; points within
# 10 m of each other (the men's and the women's side mapped apart) are one.
# Input: .lamp/reference/aa/ovp/stage-toilets.json (Overpass: amenity=toilets and amenity=stage, with geometry).
# Run: .lamp/reference/venv/bin/python -I Assets/Tools/build-restrooms.py <app folder>
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

els = json.load(open(os.path.join(REF, 'ovp/stage-toilets.json')))['elements']
buildings, points = [], []
for e in els:
    t = e.get('tags', {})
    if t.get('amenity') != 'toilets' or 'indoor' in t or 'level' in t:
        continue
    if e['type'] == 'way':
        if 'building' not in t or len(e.get('geometry') or []) < 4:
            continue
        p = make_valid(Polygon([xz(q['lon'], q['lat']) for q in e['geometry']]))
        if p.is_empty or p.area < 4:
            continue
        box = list(p.minimum_rotated_rectangle.exterior.coords)[:4]
        e0 = (box[1][0] - box[0][0], box[1][1] - box[0][1])
        e1 = (box[2][0] - box[1][0], box[2][1] - box[1][1])
        L0, L1 = math.hypot(*e0), math.hypot(*e1)
        length, width, ax = (L0, L1, e0) if L0 >= L1 else (L1, L0, e1)
        c = p.minimum_rotated_rectangle.centroid
        n = math.hypot(*ax)
        buildings += [round(c.x, 2), round(c.y, 2), round(ax[0] / n, 4), round(ax[1] / n, 4), round(length, 2), round(width, 2), 1 if t.get('shelter') == 'yes' else 0]
    elif e['type'] == 'node':
        x, z = xz(e['lon'], e['lat'])
        portable = 1 if t.get('toilets:disposal') == 'chemical' else 0
        near = next((k for k in range(0, len(points), 3) if math.hypot(points[k] - x, points[k + 1] - z) < 10), None)
        if near is not None:
            continue
        points += [round(x, 2), round(z, 2), portable]

out = os.path.join(ROOT, 'Web/data/restrooms.json')
json.dump({'buildings': buildings, 'points': points}, open(out, 'w'), separators=(',', ':'))
print(f'{len(buildings) // 7} restroom buildings, {len(points) // 3} points ({sum(points[2::3])} portable) -> {out}')
