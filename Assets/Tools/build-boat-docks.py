# Ann Arbor's docks and boat launches on the Huron and its ponds, in the game's frame (metres east and south of
# Main St & Liberty St), written to Web/data/boat-docks.json for boat-docks.js:
#   docks  flat [ax, az, bx, bz, width]   each straight run of an OpenStreetMap man_made=pier (ODbL): a mapped line
#          broken into its runs at the mapped width (2 m where none is given), and a mapped outline as the run down the
#          middle of its smallest box, as wide as the box
#   slips  flat [x, z]                    each leisure=slipway (a node, or the middle of a mapped way)
# Left out: the piers that are footbridges, paths or steps (the river's own bridges and paths draw those), and the ones
# at the Gallup Park canoe livery, whose docks gallup-livery.js draws.
# Input: .lamp/reference/aa/ovp/boats.json (Overpass: man_made=pier, leisure=slipway, amenity=boat_rental, out geom).
# Run: .lamp/reference/venv/bin/python -I Assets/Tools/build-boat-docks.py <app folder>
import json, math, os, sys
from shapely.geometry import Polygon

ROOT = sys.argv[1]
REF = os.path.join(ROOT, '.lamp/reference/aa/ovp')
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
xz = lambda lon, lat: ((lon - LON0) * KX, -(lat - LAT0) * KY)
LIVERY = (3986, 306)
r2 = lambda v: round(v, 2)

docks, slips, skipped = [], [], 0
for e in json.load(open(os.path.join(REF, 'boats.json')))['elements']:
    t = e.get('tags', {})
    if e['type'] == 'node' and t.get('leisure') == 'slipway':
        slips += [r2(v) for v in xz(e['lon'], e['lat'])]
        continue
    if e['type'] != 'way' or len(e.get('geometry') or []) < 2:
        continue
    pts = [xz(q['lon'], q['lat']) for q in e['geometry']]
    if t.get('leisure') == 'slipway':
        xs, zs = zip(*pts)
        slips += [r2(sum(xs) / len(xs)), r2(sum(zs) / len(zs))]
        continue
    if t.get('man_made') != 'pier':
        continue
    if t.get('bridge') or t.get('highway') or any(math.hypot(x - LIVERY[0], z - LIVERY[1]) < 90 for x, z in pts):
        skipped += 1
        continue
    closed = len(pts) >= 4 and math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 0.5
    if closed or t.get('area') == 'yes':
        box = list(Polygon(pts).minimum_rotated_rectangle.exterior.coords)[:4]
        e0, e1 = (box[1][0] - box[0][0], box[1][1] - box[0][1]), (box[2][0] - box[1][0], box[2][1] - box[1][1])
        # the run down the middle, along the long side
        if math.hypot(*e0) >= math.hypot(*e1):
            a = ((box[0][0] + box[3][0]) / 2, (box[0][1] + box[3][1]) / 2); b = (a[0] + e0[0], a[1] + e0[1]); w = math.hypot(*e1)
        else:
            a = ((box[0][0] + box[1][0]) / 2, (box[0][1] + box[1][1]) / 2); b = (a[0] + e1[0], a[1] + e1[1]); w = math.hypot(*e0)
        if math.hypot(b[0] - a[0], b[1] - a[1]) > 1:
            docks += [r2(a[0]), r2(a[1]), r2(b[0]), r2(b[1]), round(min(8, max(1.2, w)), 1)]
        continue
    try:
        w = float(t.get('width', '2'))
    except ValueError:
        w = 2
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        if math.hypot(bx - ax, bz - az) > 0.8:
            docks += [r2(ax), r2(az), r2(bx), r2(bz), round(min(6, max(1.2, w)), 1)]

path = os.path.join(ROOT, 'Web/data/boat-docks.json')
json.dump({'docks': docks, 'slips': slips}, open(path, 'w'), separators=(',', ':'))
print(f'{len(docks) // 5} dock runs, {len(slips) // 2} launches, skipped {skipped}, {os.path.getsize(path)} bytes')
