# Ann Arbor's baseball and softball diamonds, in the game's frame (metres east and south of Main St & Liberty St),
# written to Web/data/ball-diamonds.json for ball-diamonds.js:
#   diamonds  flat [hx, hz, heading, depth, base, lit]   one per OpenStreetMap leisure=pitch sport=baseball/softball
#             (ODbL): home plate, the heading from it toward second base (radians, atan2(dx, dz)), how far the field
#             runs out from home along it (to the outfield's edge), the distance between bases (27.43 m for a full-size
#             field, 18.29 m for Little League and softball), and 1 where the field has lights
# Home plate is found from the field's outline: the point (a corner of it, or of its smallest box) from which a
# quarter-circle wedge holds the most of the field, as a diamond's fair ground is the quarter circle off home.
# Input: .lamp/reference/aa/osm.json (as fetch-annarbor.py fetched it: way[leisure] with geometry).
# Run: .lamp/reference/venv/bin/python -I Assets/Tools/build-ball-diamonds.py <app folder>
import json, math, os, sys
from shapely.geometry import Polygon, Point
from shapely.validation import make_valid

ROOT = sys.argv[1]
REF = os.path.join(ROOT, '.lamp/reference/aa')
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
xz = lambda lon, lat: ((lon - LON0) * KX, -(lat - LAT0) * KY)
BBOX = (42.21716, -83.80706, 42.32916, -83.66934)


def wedge(hx, hz, h, r, half=math.pi / 4, n=12):
    pts = [(hx, hz)]
    for k in range(n + 1):
        a = h - half + 2 * half * k / n
        pts.append((hx + math.sin(a) * r, hz + math.cos(a) * r))
    return Polygon(pts)


diamonds, skipped = [], 0
for e in json.load(open(os.path.join(REF, 'osm.json')))['elements']:
    t = e.get('tags', {})
    if e['type'] != 'way' or t.get('leisure') != 'pitch' or t.get('sport') not in ('baseball', 'softball'):
        continue
    if t.get('indoor') == 'yes' or t.get('covered') == 'yes' or len(e.get('geometry') or []) < 4:
        skipped += 1
        continue
    g = e['geometry']
    if not (BBOX[0] <= g[0]['lat'] <= BBOX[2] and BBOX[1] <= g[0]['lon'] <= BBOX[3]):
        continue
    poly = make_valid(Polygon([xz(q['lon'], q['lat']) for q in g]))
    if poly.is_empty or poly.area < 400:
        skipped += 1
        continue
    c = poly.centroid
    cands = list(poly.exterior.coords)[:-1] if poly.geom_type == 'Polygon' else []
    cands += list(poly.minimum_rotated_rectangle.exterior.coords)[:-1]
    best = None
    for hx, hz in cands:
        far = max(math.hypot(x - hx, z - hz) for x, z in (poly.exterior.coords if poly.geom_type == 'Polygon' else poly.convex_hull.exterior.coords))
        if far < 25:
            continue
        # the wedge's heading: through the field's middle, then turned to hold the most of it
        h0 = math.atan2(c.x - hx, c.y - hz)
        for dh in (-0.3, -0.15, 0, 0.15, 0.3):
            w = wedge(hx, hz, h0 + dh, far)
            inside = w.intersection(poly).area
            score = inside / poly.area * (inside / w.area) ** 0.5
            if not best or score > best[0]:
                best = (score, hx, hz, h0 + dh, far)
    if not best:
        skipped += 1
        continue
    _, hx, hz, h, far = best
    # the field's depth along the heading: where a ray from home leaves it
    depth = 0
    for k in range(1, 400):
        if not poly.contains(Point(hx + math.sin(h) * k * 0.5, hz + math.cos(h) * k * 0.5)):
            if k * 0.5 > 20:
                break
        else:
            depth = k * 0.5
    depth = max(30, min(125, depth or far * 0.8))
    base = 27.43 if depth > 85 else 18.29
    # home a step in from the outline, where the backstop's fence is
    hx += math.sin(h) * 3
    hz += math.cos(h) * 3
    diamonds += [round(hx, 2), round(hz, 2), round(h, 3), round(depth - 3, 1), base, 1 if t.get('lit') == 'yes' else 0]

out = os.path.join(ROOT, 'Web/data/ball-diamonds.json')
json.dump({'diamonds': diamonds}, open(out, 'w'), separators=(',', ':'))
n = len(diamonds) // 6
print(f'{n} diamonds ({sum(1 for i in range(0, len(diamonds), 6) if diamonds[i + 4] > 20)} full size, '
      f'{sum(diamonds[i + 5] for i in range(0, len(diamonds), 6))} lit), skipped {skipped}, {os.path.getsize(out)} bytes')
