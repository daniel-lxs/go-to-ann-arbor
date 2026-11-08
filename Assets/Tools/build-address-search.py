# Street addresses for the map's search ("918 hutchins"): the City of Ann Arbor's Address Points (the same download as
# build-addresses.py, .lamp/reference/aa/addr/aa_address.geojson), written to Web/data/address-search.json.gz as
# { streets: ["Hutchins Ave", ...], a: [x, z, number, streetIndex, ...] } in the game's frame. Loaded only the first
# time someone searches for a number and a street.
# Run: python -I Assets/Tools/build-address-search.py <app folder>
import gzip, json, math, os, sys

ROOT = sys.argv[1]
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5

def title(w):
    return w if len(w) <= 2 and w in ('N', 'S', 'E', 'W', 'NE', 'NW', 'SE', 'SW') else w[:1] + w[1:].lower()

streets, index, rows, seen = [], {}, [], set()
for f in json.load(open(os.path.join(ROOT, '.lamp/reference/aa/addr/aa_address.geojson')))['features']:
    g, p = f.get('geometry'), f['properties']
    num = (p.get('STREETNUMBER') or '').strip()
    street = (p.get('STREET') or '').strip()
    if not g or g['type'] != 'Point' or not num.isdigit() or not street:
        continue
    words = [(p.get('DIRECTION') or '').strip(), street, (p.get('TYPE') or '').strip()]
    name = ' '.join(title(w) for part in words if part for w in part.split())
    if name not in index:
        index[name] = len(streets)
        streets.append(name)
    lon, lat = g['coordinates'][:2]
    x, z = round((lon - LON0) * KX), round(-(lat - LAT0) * KY)
    key = (int(num), index[name])
    if key in seen:
        continue  # units of one building share its address
    seen.add(key)
    rows += [x, z, int(num), index[name]]
quads = sorted((rows[i:i + 4] for i in range(0, len(rows), 4)), key=lambda r: (r[3], r[2]))
rows = [v for r in quads for v in r]  # by street and number, which packs smaller
data = json.dumps({'streets': streets, 'a': rows}, separators=(',', ':')).encode()
with open(os.path.join(ROOT, 'Web/data/address-search.json.gz'), 'wb') as out:
    out.write(gzip.compress(data, 9, mtime=0))
print(f'{len(rows) // 4} addresses on {len(streets)} streets, {len(data) // 1024} KB, '
      f'{os.path.getsize(os.path.join(ROOT, "Web/data/address-search.json.gz")) // 1024} KB packed')
