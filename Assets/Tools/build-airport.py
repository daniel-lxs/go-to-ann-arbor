# Ann Arbor Municipal Airport (ARB), in the game's frame (metres east and south of Main St & Liberty St), written to
# Web/js/airport-data.js for airport.js:
#   bounds    flat [x, z, ...]       the aerodrome's fence line (aeroway=aerodrome), where the player may walk and drive
#   runways   [{ ref, a: [x, z], b: [x, z], width, grass }]
#   taxiways  [{ ref, line: flat [x, z, ...] }]
#   aprons    [flat [x, z, ...]]
#   buildings [{ ring: flat [x, z, ...], hangar, name }]   hangars, the FBO and every other building inside the fence
#   windsocks flat [x, z, ...]
#   helis     flat [x, z, heading, ...]   the parked helicopters, in a row on the apron by the FBO, noses to the runway
#   planes    flat [x, z, heading, ...]   the parked planes, on the FBO's apron and the Aviation Center's
#   stairs    flat [x, z, heading, ...]   rolling airstairs on the aprons, climbing toward `heading`, clear pavement behind
# OpenStreetMap (ODbL). Input: .lamp/reference/airport/osm-map.xml (the OSM API's /map for -83.760,42.215,-83.733,42.230).
# Run: python -I Assets/Tools/build-airport.py <app folder>
import json, math, os, sys
import xml.etree.ElementTree as ET

ROOT = sys.argv[1]
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
xz = lambda lon, lat: ((lon - LON0) * KX, -(lat - LAT0) * KY)

root = ET.parse(os.path.join(ROOT, '.lamp/reference/airport/osm-map.xml')).getroot()
nodes = {n.get('id'): xz(float(n.get('lon')), float(n.get('lat'))) for n in root.iter('node')}
r1 = lambda v: round(v, 1)


def ring_of(w):
    pts = [nodes[nd.get('ref')] for nd in w.iter('nd') if nd.get('ref') in nodes]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def flat(pts):
    return [r1(v) for p in pts for v in p]


def inside(pts, x, z):
    c, j = False, len(pts) - 1
    for i in range(len(pts)):
        (xi, zi), (xj, zj) = pts[i], pts[j]
        if (zi > z) != (zj > z) and x < (xj - xi) * (z - zi) / (zj - zi) + xi:
            c = not c
        j = i
    return c


ways = []
for w in root.iter('way'):
    ways.append(({k.get('k'): k.get('v') for k in w.iter('tag')}, ring_of(w)))

fence = next(p for t, p in ways if t.get('aeroway') == 'aerodrome')
out = {'bounds': flat(fence), 'runways': [], 'taxiways': [], 'aprons': [], 'buildings': [], 'windsocks': [], 'helis': []}
for t, pts in ways:
    a = t.get('aeroway')
    if a == 'runway':
        out['runways'].append({'ref': t.get('ref'), 'a': flat(pts[:1]), 'b': flat(pts[-1:]),
                               'width': float(t.get('width', '23')), 'grass': t.get('surface') == 'grass'})
    elif a == 'taxiway':
        out['taxiways'].append({'ref': t.get('ref'), 'line': flat(pts)})
    elif a == 'apron':
        out['aprons'].append(flat(pts))
    elif (a in ('hangar', 'terminal') or 'building' in t) and len(pts) >= 3:
        cx = sum(p[0] for p in pts) / len(pts); cz = sum(p[1] for p in pts) / len(pts)
        if inside(fence, cx, cz):
            out['buildings'].append({'ring': flat(pts), 'hangar': a == 'hangar' or t.get('building') == 'hangar',
                                     'name': t.get('name')})
for n in root.iter('node'):
    t = {k.get('k'): k.get('v') for k in n.iter('tag')}
    if t.get('aeroway') == 'windsock':
        out['windsocks'] += flat([nodes[n.get('id')]])

# the helicopters: three in a row on the FBO's apron, 20 m apart, clear of its edges, noses south toward the runway (heading 0 is +z)
apron = max((p for t, p in ways if t.get('aeroway') == 'apron'),
            key=lambda p: -min(math.hypot(x - 220, z - 6070) for x, z in p))
spots = []
for gx in range(-60, 61, 4):
    for gz in range(-40, 41, 4):
        x, z = 170 + gx, 6075 + gz
        if all(inside(apron, x + dx, z + dz) for dx in (-11, 0, 11) for dz in (-11, 0, 11)):
            spots.append((x, z))
spots.sort(key=lambda p: (p[1], p[0]))
row = []
for x, z in sorted(spots, key=lambda p: (abs(p[1] - 6075), p[0])):
    if all(math.hypot(x - a, z - b) >= 20 for a, b in row):
        row.append((x, z))
    if len(row) == 3:
        break
for x, z in row:
    out['helis'] += [r1(x), r1(z), 0.15]

# the planes: high-wing four-seaters tied down on the FBO's apron and the Aviation Center's, 16 m apart, nose to the
# south (heading 0) with a little play; and the airstairs: rolling stairs parked on the open apron, each with 30 m of
# clear pavement behind it to run up them (the player's jump)
aprons = [[(a[i], a[i + 1]) for i in range(0, len(a), 2)] for a in out['aprons']]
paved = lambda x, z: any(inside(ap, x, z) for ap in aprons)
taken = list(row)
planes = []
for cx, cz, n in ((240, 6075, 3), (600, 5885, 4)):
    cand = [(cx + gx, cz + gz) for gx in range(-140, 141, 4) for gz in range(-110, 111, 4)]
    cand = [(x, z) for x, z in cand if all(paved(x + dx, z + dz) for dx in (-7, 0, 7) for dz in (-6, 0, 6))]
    got = 0
    for x, z in sorted(cand, key=lambda p: math.hypot(p[0] - cx, p[1] - cz)):
        if all(math.hypot(x - a, z - b) >= 16 for a, b in taken):
            taken.append((x, z)); planes.append((x, z)); got += 1
        if got == n:
            break
out['planes'] = []
for k, (x, z) in enumerate(planes):
    out['planes'] += [r1(x), r1(z), round((k * 0.37) % 0.5 - 0.25, 2)]
stairs = []
for cx, cz in ((600, 5885), (600, 5885), (200, 6075)):
    best = None
    for gx in range(-120, 121, 6):
        for gz in range(-100, 101, 6):
            x, z = cx + gx, cz + gz
            for hd in (0, math.pi / 2, math.pi, -math.pi / 2):
                sx, sz = math.sin(hd), math.cos(hd)
                ok = all(paved(x - sx * t - sz * w, z - sz * t + sx * w) for t in range(-6, 34, 4) for w in (-3, 0, 3))
                if ok and all(math.hypot(x - a, z - b) >= 20 for a, b in taken):
                    sc = math.hypot(gx, gz)
                    if best is None or sc < best[0]:
                        best = (sc, x, z, hd)
    if best:
        _, x, z, hd = best
        taken.append((x, z)); stairs.append((x, z, hd))
out['stairs'] = [v for x, z, hd in stairs for v in (r1(x), r1(z), round(hd, 3))]

dst = os.path.join(ROOT, 'Web/js/airport-data.js')
with open(dst, 'w') as f:
    f.write('// Lamp: written by Assets/Tools/build-airport.py from OpenStreetMap (ODbL): Ann Arbor Municipal Airport\'s\n')
    f.write('// runways, taxiways, aprons and buildings in the game\'s frame (metres east and south of Main & Liberty)\n')
    f.write('export const AIRPORT = ' + json.dumps(out, separators=(',', ':')) + ';\n')
print({k: len(v) for k, v in out.items()}, row, planes, stairs, os.path.getsize(dst), 'bytes')
