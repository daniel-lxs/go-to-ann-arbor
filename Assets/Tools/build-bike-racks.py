# Ann Arbor's bike racks, in the game's frame (metres east and south of Main St & Liberty St), written to
# Web/data/bike-racks.json for bike-racks.js:
#   racks  flat [x, z, yaw, stands, kind]   OpenStreetMap's amenity=bicycle_parking (ODbL): kind 0 a row of stands
#                                           (stands, rack, wave, loops...), 1 an e-bike dock (hand-placed by the Diag,
#                                           below); `stands` the row's length, from the rack's capacity (two bikes a
#                                           stand), at most 12; yaw along the row: a way's long side, else the
#                                           town's grid (north-south or east-west, by the spot)
# The city's park bike racks (street-furniture.json) are left out within 4 m, since street-details.js draws those.
# Input: .lamp/reference/racks/osm-racks.json (Overpass: nwr["amenity"~"bicycle_parking|bicycle_rental"] in the city's
# box, `out center tags`; ways also fetched with `out geom` into osm-racks-geom.json for their shape).
# Run: python -I Assets/Tools/build-bike-racks.py <app folder>
import json, math, os, sys

ROOT = sys.argv[1]
REF = os.path.join(ROOT, '.lamp/reference/racks')
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
xz = lambda lon, lat: ((lon - LON0) * KX, -(lat - LAT0) * KY)

# the e-bike docks by the Diag: [x, z, yaw, docks]; on the walks by the Diag's south-east corner (East University),
# its west end on State St, and the north side by the Graduate Library and North University
DOCKS = [[872, 226, 0, 10], [766, 247, math.pi / 2, 8], [840, 402, 0, 8]]

geom = {}
gpath = os.path.join(REF, 'osm-racks-geom.json')
if os.path.exists(gpath):
    for e in json.load(open(gpath))['elements']:
        if e['type'] == 'way' and e.get('geometry'):
            geom[e['id']] = [xz(p['lon'], p['lat']) for p in e['geometry']]

park = json.load(open(os.path.join(ROOT, 'Web/data/street-furniture.json')))['amenities']
park_racks = [(park[i], park[i + 1]) for i in range(0, len(park), 4) if park[i + 2] == 5]


def hash01(x, z):
    h = math.sin(x * 12.9898 + z * 78.233) * 43758.5453
    return h - math.floor(h)


racks = []
for d in DOCKS:
    racks += [round(d[0], 1), round(d[1], 1), round(d[2], 2), d[3], 1]
for e in json.load(open(os.path.join(REF, 'osm-racks.json')))['elements']:
    t = e.get('tags', {})
    if t.get('amenity') != 'bicycle_parking' or t.get('access') in ('private', 'customers', 'no'):
        continue
    if t.get('bicycle_parking') in ('shed', 'lockers', 'building', 'wall_loops', 'ground_slots'):
        continue
    if t.get('covered') == 'yes' and t.get('indoor') == 'yes':
        continue
    lat, lon = (e['lat'], e['lon']) if 'lat' in e else (e['center']['lat'], e['center']['lon'])
    x, z = xz(lon, lat)
    if any(math.hypot(x - d[0], z - d[1]) < 12 for d in DOCKS):
        continue
    if any(math.hypot(x - px, z - pz) < 4 for px, pz in park_racks):
        continue
    cap = int(t['capacity']) if t.get('capacity', '').isdigit() else 6
    stands = max(1, min(12, round(cap / 2)))
    yaw = (math.pi / 2) if hash01(x, z) < 0.5 else 0.0
    pts = geom.get(e['id'])
    if pts and len(pts) > 1:
        best = 0
        for (ax, az), (bx, bz) in zip(pts, pts[1:]):
            L = math.hypot(bx - ax, bz - az)
            if L > best:
                best, yaw = L, math.atan2(bx - ax, bz - az)
    racks += [round(x, 1), round(z, 1), round(yaw, 2), stands, 0]

out = os.path.join(ROOT, 'Web/data/bike-racks.json')
json.dump({'racks': racks}, open(out, 'w'), separators=(',', ':'))
print(f'{len(racks) // 5} racks and docks ({len(DOCKS)} docks), {os.path.getsize(out) // 1024} KB')
