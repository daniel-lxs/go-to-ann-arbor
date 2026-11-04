# Golf holes the city's map data leaves out, in the game's frame (metres east and south of Main St & Liberty St),
# written to Web/js/golf-holes.js (a module, so the course and the map have them at once) for golf.js layOutHoles:
#   holes  [{ ref, par, line: flat [x, z, ...] }]   OpenStreetMap's golf=hole ways (ODbL): each from its tee to its green
# Input: .lamp/reference/huronhills/osm-map.xml (the OSM API's /map for the box around Huron Hills Golf Course:
# -83.705,42.260,-83.685,42.277).
# Run: python -I Assets/Tools/build-golf-holes.py <app folder>
import json, math, os, sys
import xml.etree.ElementTree as ET

ROOT = sys.argv[1]
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
xz = lambda lon, lat: ((lon - LON0) * KX, -(lat - LAT0) * KY)

root = ET.parse(os.path.join(ROOT, '.lamp/reference/huronhills/osm-map.xml')).getroot()
nodes = {n.get('id'): (float(n.get('lon')), float(n.get('lat'))) for n in root.iter('node')}
holes = []
for w in root.iter('way'):
    t = {k.get('k'): k.get('v') for k in w.iter('tag')}
    if t.get('golf') != 'hole':
        continue
    line = []
    for nd in w.iter('nd'):
        if nd.get('ref') in nodes:
            x, z = xz(*nodes[nd.get('ref')])
            line += [round(x, 1), round(z, 1)]
    if len(line) >= 4:
        holes.append({'ref': t.get('ref'), 'par': int(t['par']) if t.get('par', '').isdigit() else None, 'line': line})
holes.sort(key=lambda h: int(h['ref']) if (h['ref'] or '').isdigit() else 99)
out = os.path.join(ROOT, 'Web/js/golf-holes.js')
with open(out, 'w') as f:
    f.write('// Lamp: written by Assets/Tools/build-golf-holes.py from OpenStreetMap (ODbL): Huron Hills Golf Course\'s 18 holes,\n')
    f.write('// each a line from its tee to its green in the game\'s frame (metres east and south of Main & Liberty)\n')
    f.write('export const GOLF_HOLES = ' + json.dumps(holes, separators=(',', ':')) + ';\n')
for h in holes:
    L = h['line']
    length = sum(math.hypot(L[i + 2] - L[i], L[i + 3] - L[i + 1]) for i in range(0, len(L) - 2, 2))
    print(h['ref'], h['par'], f'{length * 1.0936:.0f} yd', L[:2], L[-2:])
print(len(holes), 'holes ->', out)
