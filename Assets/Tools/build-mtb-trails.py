# Ann Arbor's mountain bike trails, in the game's frame (metres east and south of Main St & Liberty St), written to
# Web/data/mtb-trails.json for mtb-trails.js:
#   trails  [[scale, x, z, x, z, ...], ...]   each OpenStreetMap (ODbL) dirt path tagged for mountain bikes
#           (mtb:scale, mtb=yes, or a bicycle=designated path on dirt), scale its mtb:scale (0 easy to 3 hard; 1 where
#           it's only designated), its points thinned to one every 2 m or more
# The trails themselves are drawn already, as dirt (GEO.trails, golf.js buildTrails); this adds what's on them.
# Input: .lamp/reference/aa/ovp/mtb.json (Overpass: way["mtb:scale"], way[highway=path][mtb=yes],
#        way[highway=path][bicycle=designated][surface~dirt|ground|earth|unpaved], route=mtb; out geom).
# Run: python3 -I Assets/Tools/build-mtb-trails.py <app folder>
import json, math, os, sys

ROOT = sys.argv[1]
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
xz = lambda lon, lat: ((lon - LON0) * KX, -(lat - LAT0) * KY)
PAVED = ('asphalt', 'concrete', 'paved', 'paving_stones', 'wood', 'metal')

trails, seen, total = [], set(), 0
for e in json.load(open(os.path.join(ROOT, '.lamp/reference/aa/ovp/mtb.json')))['elements']:
    t = e.get('tags', {})
    if e['type'] != 'way' or e['id'] in seen or len(e.get('geometry') or []) < 2 or t.get('surface') in PAVED:
        continue
    seen.add(e['id'])
    try:
        scale = max(0, min(3, int(t.get('mtb:scale', '1')[0])))
    except ValueError:
        scale = 1
    pts = [xz(q['lon'], q['lat']) for q in e['geometry']]
    keep = [pts[0]]
    for p in pts[1:-1]:
        if math.hypot(p[0] - keep[-1][0], p[1] - keep[-1][1]) >= 2:
            keep.append(p)
    keep.append(pts[-1])
    total += sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(keep, keep[1:]))
    trails.append([scale] + [round(v, 2) for p in keep for v in p])

path = os.path.join(ROOT, 'Web/data/mtb-trails.json')
json.dump({'trails': trails}, open(path, 'w'), separators=(',', ':'))
print(f'{len(trails)} trails, {total / 1000:.1f} km, {os.path.getsize(path)} bytes')
