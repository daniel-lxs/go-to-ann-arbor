# Fetches every source the city's builders read that's asked for by area, over the whole City of Ann Arbor: the city's
# official limits (data.a2gov.org "City Boundary", limits/aa_city_boundary.geojson) and a margin round them, into
# .lamp/reference/aa/ (the files build-annarbor.py and the other builders read). The city's other layers (buildings,
# street trees, paving, hydrants, land use, parcels, addresses, streetlights, speed limits) are whole-city downloads
# already. Each file is fetched once; delete it to fetch it again.
#   osm.json                 Overpass: streets, buildings, water, woods, parks, land use, parking, rail, golf, mapped trees
#   poi/osm_pois.json        Overpass: named shops, amenities, tourism and leisure (out center)
#   sig/osm_signals.json     Overpass: traffic lights, stop and yield signs, crossings
#   rail/level_crossings.json, roofs/roofs.json, fuel/fuel.json, ../osm-bookcases.json
#   canopy/p*.json           the city's Urban Tree Canopy (NaturalFeatures/MapServer/10), 1000 at a time
# Run: .lamp/reference/venv/bin/python -I Assets/Tools/fetch-annarbor.py <app folder>
import json, os, sys, time, urllib.parse, urllib.request
from shapely.geometry import shape
from shapely.ops import unary_union

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.'
REF = os.path.join(ROOT, '.lamp/reference/aa')
UA = {'User-Agent': 'GoToAnnArbor/1.0'}
BOUNDARY = os.path.join(REF, 'limits/aa_city_boundary.geojson')
BOUNDARY_URL = ('https://ckan.a2gov.org/dataset/c5d51794-60bb-478e-8cef-da420869d98d/resource/'
                '515b29a3-14e1-467e-9c9b-42f53b676fd8/download/aa_city_boundary.geojson')


def get(url, data=None, timeout=900):
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, data=data, headers=UA)
            return urllib.request.urlopen(req, timeout=timeout).read()
        except Exception as err:
            print('  retry', err, flush=True)
            time.sleep(20 * (attempt + 1))
    raise SystemExit(f'failed: {url[:120]}')


if not os.path.exists(BOUNDARY):
    os.makedirs(os.path.dirname(BOUNDARY), exist_ok=True)
    open(BOUNDARY, 'wb').write(get(BOUNDARY_URL))
limits = unary_union([shape(f['geometry']) for f in json.load(open(BOUNDARY))['features']])
W, S, E, N = limits.bounds
# about 600 m round the limits: the streets that leave town, and what the edge's lawn border meets
S, W, N, E = S - 0.0055, W - 0.0075, N + 0.0055, E + 0.0075
# and south far enough for all of Ann Arbor Municipal Airport and the town's squared-off south end (build-annarbor.py)
S = min(S, 42.2125)
BB = f'{S:.5f},{W:.5f},{N:.5f},{E:.5f}'
print('box', BB)

OVERPASS = 'https://overpass-api.de/api/interpreter'
QUERIES = {
    'osm.json': '''(way[highway]; way[building]; relation[building];
  way[natural~"^(water|wood)$"]; relation[natural]; node[natural=tree];
  way[landuse]; relation[landuse]; way[leisure]; relation[leisure];
  way[amenity=parking]; way[railway=rail]; way[waterway=river]; way[golf];); out geom;''',
    'poi/osm_pois.json': '(nwr[shop][name]; nwr[amenity][name]; nwr[tourism][name]; nwr[leisure][name];); out center tags;',
    'sig/osm_signals.json': 'node[highway~"^(traffic_signals|stop|give_way|crossing)$"]; out;',
    'rail/level_crossings.json': 'node[railway~"^(level_crossing|crossing)$"]; out;',
    'roofs/roofs.json': 'way[building]["roof:shape"]; out tags center;',
    'fuel/fuel.json': '(nwr[amenity=fuel]; way[building=roof];); out geom;',
    '../osm-bookcases.json': 'nwr[amenity=public_bookcase]; out center tags;',
}
for name, q in QUERIES.items():
    path = os.path.join(REF, name)
    if os.path.exists(path) and json.load(open(path)).get('bbox') == BB:
        continue
    print('overpass', name, flush=True)
    body = get(OVERPASS, urllib.parse.urlencode({'data': f'[out:json][timeout:800][bbox:{BB}];{q}'}).encode())
    d = json.loads(body)
    if d.get('remark'):
        print('  ', d['remark'])
    d['bbox'] = BB
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(d, open(path + '.part', 'w'))
    os.replace(path + '.part', path)
    print('  ', len(d['elements']), 'elements', flush=True)
    time.sleep(10)

# the tree canopy over the whole box, in pages
CAN = os.path.join(REF, 'canopy')
mark = os.path.join(CAN, 'box.txt')
if not os.path.exists(mark) or open(mark).read() != BB:
    for f in os.listdir(CAN):
        os.remove(os.path.join(CAN, f))
    o = 0
    while True:
        url = ('https://a2maps.a2gov.org/a2arcgis/rest/services/NaturalFeatures/MapServer/10/query?where=1%3D1'
               f'&geometry={W:.5f},{S:.5f},{E:.5f},{N:.5f}&geometryType=esriGeometryEnvelope&inSR=4326'
               '&spatialRel=esriSpatialRelIntersects&outFields=OBJECTID_1&outSR=4326&orderByFields=OBJECTID_1'
               f'&resultOffset={o}&resultRecordCount=1000&f=geojson')
        d = json.loads(get(url, timeout=180))
        n = len(d.get('features', []))
        json.dump(d, open(os.path.join(CAN, f'p{o}.json'), 'w'))
        print('canopy', o, n, flush=True)
        if n < 1000:
            break
        o += 1000
    open(mark, 'w').write(BB)
print('done')
