# The Ann Arbor Skatepark in Veterans Memorial Park, in the game's frame (metres east and south of Main St & Liberty St),
# written to Web/data/skate-park.json for skate-park.js:
#   outline  flat [x, z, ...]   the park's concrete as OpenStreetMap maps it (ODbL): leisure=pitch sport=skateboard
# skate-park.js lays the bowl, the snake run, the quarter pipes round its lip and the street plaza inside it.
# Input: .lamp/reference/aa/osm.json (as fetch-annarbor.py fetched it: way[leisure] with geometry).
# Run: python3 -I Assets/Tools/build-skate-park.py <app folder>
import json, math, os, sys

ROOT = sys.argv[1]
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
xz = lambda lon, lat: ((lon - LON0) * KX, -(lat - LAT0) * KY)

parks = [e for e in json.load(open(os.path.join(ROOT, '.lamp/reference/aa/osm.json')))['elements']
         if e['type'] == 'way' and e.get('tags', {}).get('sport') == 'skateboard' and len(e.get('geometry') or []) >= 4]
park = max(parks, key=lambda e: len(e['geometry']))
ring = [xz(q['lon'], q['lat']) for q in park['geometry']]
if ring[0] == ring[-1]:
    ring = ring[:-1]
path = os.path.join(ROOT, 'Web/data/skate-park.json')
json.dump({'name': park['tags'].get('name', ''), 'outline': [round(v, 2) for p in ring for v in p]}, open(path, 'w'), separators=(',', ':'))
print(f"{park['tags'].get('name')}: {len(ring)} points, {os.path.getsize(path)} bytes")
