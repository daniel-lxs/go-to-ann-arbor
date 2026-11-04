# Ann Arbor's street furniture and park amenities, in the game's frame (metres east and south of Main St & Liberty St),
# written to Web/data/street-furniture.json for street-details.js:
#   hydrants   flat [x, z]                      the city's Fire Hydrants (ckan.a2gov.org "fire-hydrants"; no license stated)
#   amenities  flat [x, z, kind, yaw]           the city's Park Amenities (ckan.a2gov.org "park-amenities"; no license
#                                               stated): 0 bench, 1 trash can, 2 picnic table, 3 grill, 4 drinking
#                                               fountain, 5 bike rack, 6 picnic shelter
#   courts     flat [sport, cx, cz, angle, length, width]   OpenStreetMap's leisure=pitch (ODbL), one entry per court:
#                                               0 tennis, 1 basketball, 2 pickleball, 3 volleyball, 4 soccer
#   libraries  flat [x, z]                      OpenStreetMap's amenity=public_bookcase (ODbL): Little Free Libraries
#                                               and the like (Little Free Library itself publishes no open data)
# Inputs in .lamp/reference/aa: aa_hydrants.geojson, aa_parkamenities.geojson, osm.json (as build-annarbor.py fetched),
# osm-bookcases.json (Overpass: node/way["amenity"="public_bookcase"] in the city's box, `out center tags`).
# Run: python -I Assets/Tools/build-street-furniture.py <app folder>
import json, math, os, sys
from shapely.geometry import Polygon
from shapely.validation import make_valid

ROOT = sys.argv[1]
REF = os.path.join(ROOT, '.lamp/reference/aa')
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
BBOX = (42.252, -83.782, 42.308, -83.693)  # S, W, N, E: the city the game builds


def xz(lon, lat):
    return ((lon - LON0) * KX, -(lat - LAT0) * KY)


def inside(lon, lat):
    return BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]


def r1(v):
    return round(v, 1)


def hash_yaw(x, z):
    h = math.sin(x * 12.9898 + z * 78.233) * 43758.5453
    return round((h - math.floor(h)) * math.tau, 2)


hydrants = []
for f in json.load(open(os.path.join(REF, 'aa_hydrants.geojson')))['features']:
    g = f.get('geometry')
    if not g or g['type'] != 'Point':
        continue
    lon, lat = g['coordinates'][:2]
    if inside(lon, lat):
        x, z = xz(lon, lat)
        hydrants += [r1(x), r1(z)]

KINDS = {'Bench': 0, 'Team Bench': 0, 'Sports Viewing': 0, 'Trash Can': 1, 'Picnic Table': 2, 'BBQ Grills': 3,
         'Drinking Fountain': 4, 'Bike Rack': 5, 'Picnic Shelter': 6}
amenities = []
for f in json.load(open(os.path.join(REF, 'aa_parkamenities.geojson')))['features']:
    g, kind = f.get('geometry'), KINDS.get(f['properties'].get('FeatureTyp'))
    if not g or g['type'] != 'Point' or kind is None:
        continue
    lon, lat = g['coordinates'][:2]
    if inside(lon, lat):
        x, z = xz(lon, lat)
        amenities += [r1(x), r1(z), kind, hash_yaw(x, z)]

# Courts and fields: each pitch's smallest box, split into as many courts side by side as fit its width
SPORTS = {'tennis': (0, 34.0, 16.5), 'basketball': (1, 26.0, 14.0), 'pickleball': (2, 13.4, 6.1),
          'beachvolleyball': (3, 16.0, 8.0), 'volleyball': (3, 16.0, 8.0), 'soccer': (4, 0, 0)}
courts = []
for e in json.load(open(os.path.join(REF, 'osm.json')))['elements']:
    t = e.get('tags', {})
    if e['type'] != 'way' or t.get('leisure') != 'pitch' or t.get('sport') not in SPORTS or 'geometry' not in e:
        continue
    if t.get('indoor') == 'yes' or t.get('covered') == 'yes' or t.get('level') not in (None, '0'):
        continue  # under a roof: the building stands there
    pts = [p for p in e['geometry'] if p]
    if len(pts) < 4 or not inside(pts[0]['lon'], pts[0]['lat']):
        continue
    poly = make_valid(Polygon([xz(p['lon'], p['lat']) for p in pts]))
    if poly.is_empty or poly.area < 40:
        continue
    box = list(poly.minimum_rotated_rectangle.exterior.coords)[:4]
    e0 = (box[1][0] - box[0][0], box[1][1] - box[0][1])
    e1 = (box[2][0] - box[1][0], box[2][1] - box[1][1])
    L0, L1 = math.hypot(*e0), math.hypot(*e1)
    long_, short, ax = (L0, L1, e0) if L0 >= L1 else (L1, L0, e1)
    sport, cl, cw = SPORTS[t['sport']]
    angle = math.atan2(ax[1], ax[0])
    cx, cz = poly.minimum_rotated_rectangle.centroid.coords[0]
    # courts side by side across the short side (or end to end along the long one), when the box holds several
    across = max(1, round(short / cw)) if cw else 1
    along = max(1, round(long_ / cl)) if cl else 1
    if cl and across == 1 and along == 1 and long_ > cl * 1.5:
        along = 2
    ux, uz = math.cos(angle), math.sin(angle)
    vx, vz = -uz, ux
    for i in range(across):
        for j in range(along):
            oa = (i - (across - 1) / 2) * short / across
            ob = (j - (along - 1) / 2) * long_ / along
            courts += [sport, r1(cx + vx * oa + ux * ob), r1(cz + vz * oa + uz * ob), round(angle, 3),
                       r1(long_ / along), r1(short / across)]

libraries = []
for e in json.load(open(os.path.join(REF, 'osm-bookcases.json')))['elements']:
    lat, lon = (e['lat'], e['lon']) if 'lat' in e else (e['center']['lat'], e['center']['lon'])
    if inside(lon, lat):
        x, z = xz(lon, lat)
        libraries += [r1(x), r1(z)]

out = {'hydrants': hydrants, 'amenities': amenities, 'courts': courts, 'libraries': libraries}
json.dump(out, open(os.path.join(ROOT, 'Web/data/street-furniture.json'), 'w'), separators=(',', ':'))
print(f'{len(hydrants) // 2} hydrants, {len(amenities) // 4} park amenities, {len(courts) // 6} courts and fields, {len(libraries) // 2} little libraries')
