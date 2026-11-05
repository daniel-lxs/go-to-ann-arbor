# Ann Arbor's outdoor swimming pools, in the game's frame (metres east and south of Main St & Liberty St), written to
# Web/data/pools.json for pools.js:
#   pools  [[kind, depth, x0, z0, x1, z1, ...], ...]   OpenStreetMap's leisure=swimming_pool (ODbL), one outline each,
#          wound either way: kind 0 a backyard or an apartment pool, 1 a big one (a park's, a club's) with lanes;
#          depth the deep end's, in metres
# Left out: pools on a roof or indoors (tagged so, or whose middle is inside a building of the city's footprints or the
# map's), and slivers under 6 m2.
# Input: .lamp/reference/aa/osm.json (as fetch-annarbor.py fetched it: way[leisure] and way[building] with geometry),
# .lamp/reference/aa/aa_bldg.geojson.
# Run: .lamp/reference/venv/bin/python -I Assets/Tools/build-pools.py <app folder>
import json, math, os, sys
from shapely.geometry import Polygon, Point, shape
from shapely.strtree import STRtree

ROOT = sys.argv[1]
REF = os.path.join(ROOT, '.lamp/reference/aa')
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
xz = lambda lon, lat: ((lon - LON0) * KX, -(lat - LAT0) * KY)

osm = json.load(open(os.path.join(REF, 'osm.json')))['elements']
buildings = []
for e in osm:
    if e['type'] == 'way' and 'building' in e.get('tags', {}) and len(e.get('geometry') or []) >= 4:
        p = Polygon([xz(q['lon'], q['lat']) for q in e['geometry']])
        if p.is_valid:
            buildings.append(p)
for f in json.load(open(os.path.join(REF, 'aa_bldg.geojson')))['features']:
    g = f.get('geometry')
    if not g:
        continue
    try:
        s = shape(g)
    except Exception:
        continue
    from shapely.ops import transform
    s = transform(lambda lon, lat, z=None: xz(lon, lat), s)
    if s.is_valid:
        buildings.append(s)
tree = STRtree(buildings)

pools, skipped = [], {'roof or indoor': 0, 'in a building': 0, 'tiny': 0}
for e in osm:
    t = e.get('tags', {})
    if e['type'] != 'way' or t.get('leisure') != 'swimming_pool' or len(e.get('geometry') or []) < 4:
        continue
    if t.get('location') in ('roof', 'indoor') or t.get('indoor') == 'yes' or t.get('covered') == 'yes':
        skipped['roof or indoor'] += 1
        continue
    pts = [xz(q['lon'], q['lat']) for q in e['geometry']]
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    poly = Polygon(pts)
    if not poly.is_valid or poly.area < 6:
        skipped['tiny'] += 1
        continue
    mid = poly.representative_point()
    if any(buildings[i].contains(mid) for i in tree.query(mid)):
        skipped['in a building'] += 1
        continue
    big = poly.area > 180 or (t.get('access') not in ('private',) and poly.area > 120)
    depth = 2.4 if big else 1.8
    flat = []
    for x, z in pts:
        flat += [round(x, 2), round(z, 2)]
    pools.append([1 if big else 0, depth] + flat)

out = os.path.join(ROOT, 'Web/data/pools.json')
json.dump({'pools': pools}, open(out, 'w'), separators=(',', ':'))
print(f'{len(pools)} pools ({sum(p[0] for p in pools)} big), skipped {skipped}, {os.path.getsize(out) // 1024} KB')
