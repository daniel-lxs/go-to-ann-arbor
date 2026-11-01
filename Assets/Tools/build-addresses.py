# Ann Arbor's house numbers: the City of Ann Arbor's Address Points (ckan.a2gov.org "address-points", no license
# stated), downloaded once into .lamp/reference/aa/addr/aa_address.geojson, written to Web/data/addresses.json as flat
# [x, z, number] in the game's frame (whole metres east and south of Main St & Liberty St). houses.js puts each number
# on a plate beside the front door of the house it falls in (or the nearest one).
# Run: python -I Assets/Tools/build-addresses.py <app folder>
import json, math, os, sys

ROOT = sys.argv[1]
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5

out, seen = [], set()
for f in json.load(open(os.path.join(ROOT, '.lamp/reference/aa/addr/aa_address.geojson')))['features']:
    g, p = f.get('geometry'), f['properties']
    num = (p.get('STREETNUMBER') or '').strip()
    if not g or g['type'] != 'Point' or not num.isdigit() or not 0 < int(num) < 100000:
        continue
    lon, lat = g['coordinates'][:2]
    x, z = round((lon - LON0) * KX), round(-(lat - LAT0) * KY)
    if (x, z, int(num)) in seen:
        continue  # units of one building share its number
    seen.add((x, z, int(num)))
    out += [x, z, int(num)]
json.dump(out, open(os.path.join(ROOT, 'Web/data/addresses.json'), 'w'), separators=(',', ':'))
print(f'{len(out) // 3} addresses')
