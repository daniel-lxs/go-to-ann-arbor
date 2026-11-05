# Ann Arbor's outdoor seating: restaurant and cafe patios and the tables out front of the places that have them, in the
# game's frame (metres east and south of Main St & Liberty St), written to Web/data/outdoor-seating.json for
# outdoor-seating.js:
#   patios  [[style, x0, z0, x1, z1, ...], ...]   OpenStreetMap's leisure=outdoor_seating areas (ODbL), wound either way
#   fronts  flat [x, z, heading, width, style]    a place with outdoor_seating=yes (amenity: cafe, restaurant, bar...)
#                                                 and no patio mapped within 30 m: a row of tables on the sidewalk out
#                                                 front of its storefront, where its sign is (GEO.signs, build-annarbor.py):
#                                                 heading the wall's outward normal (radians, atan2(nx, nz)), width
#                                                 along the wall, at most 12 m
# style: 0 a cafe's (small round tables, two chairs, a few umbrellas), 1 a restaurant's (square tables for four, an
# umbrella over most), 2 a bar's or beer garden's (long picnic tables), 3 a patio that's no food or drink place's (at
# apartments, offices, a campus building: a few picnic tables)
# Inputs in .lamp/reference/aa: osm.json (way[leisure] with geometry), poi/osm_pois.json (nwr[amenity][name], `out
# center tags`), and Web/js/city-geodata.js for the storefronts.
# Run: python -I Assets/Tools/build-outdoor-seating.py <app folder>
import json, math, os, sys

ROOT = sys.argv[1]
REF = os.path.join(ROOT, '.lamp/reference/aa')
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
xz = lambda lon, lat: ((lon - LON0) * KX, -(lat - LAT0) * KY)
STYLE = {'cafe': 0, 'ice_cream': 0, 'fast_food': 0, 'restaurant': 1, 'bar': 2, 'pub': 2, 'biergarten': 2}

# the places that say they have seats outside, and every food or drink place (to give a mapped patio its style)
places = []
for e in json.load(open(os.path.join(REF, 'poi/osm_pois.json')))['elements']:
    t = e.get('tags', {})
    if t.get('amenity') not in STYLE:
        continue
    lat, lon = (e['lat'], e['lon']) if 'lat' in e else (e['center']['lat'], e['center']['lon'])
    x, z = xz(lon, lat)
    places.append({'x': x, 'z': z, 'name': t.get('name', ''), 'style': STYLE[t['amenity']], 'out': t.get('outdoor_seating') == 'yes'})

patios = []
for e in json.load(open(os.path.join(REF, 'osm.json')))['elements']:
    t = e.get('tags', {})
    if e['type'] != 'way' or t.get('leisure') != 'outdoor_seating' or len(e.get('geometry') or []) < 4:
        continue
    pts = [xz(q['lon'], q['lat']) for q in e['geometry']]
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    cx, cz = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
    near = min(places, key=lambda p: math.hypot(p['x'] - cx, p['z'] - cz), default=None)
    style = near['style'] if near and math.hypot(near['x'] - cx, near['z'] - cz) < 40 else 3
    if 'biergarten' in t.get('name', '').lower() or t.get('amenity') == 'biergarten':
        style = 2
    flat = [style]
    for x, z in pts:
        flat += [round(x, 2), round(z, 2)]
    patios.append(flat)
centres = [(sum(p[1::2]) / ((len(p) - 1) / 2), sum(p[2::2]) / ((len(p) - 1) / 2)) for p in patios]

src = open(os.path.join(ROOT, 'Web/js/city-geodata.js')).read()
geo = json.loads(src[src.index('{'):src.rindex('}') + 1])
names, signs = geo['signs']['names'], geo['signs']['list']
by_name = {}
for i in range(0, len(signs), 7):
    by_name.setdefault(names[signs[i + 5]], []).append(signs[i:i + 7])

fronts, missed = [], 0
for p in places:
    if not p['out'] or any(math.hypot(cx - p['x'], cz - p['z']) < 30 for cx, cz in centres):
        continue
    cands = [s for s in by_name.get(p['name'], []) if math.hypot(s[0] - p['x'], s[1] - p['z']) < 40]
    if not cands:
        missed += 1
        continue
    s = min(cands, key=lambda s: math.hypot(s[0] - p['x'], s[1] - p['z']))
    fronts += [round(s[0], 2), round(s[1], 2), round(math.radians(s[2]), 3), round(min(12, max(4, s[3] * 1.4)), 1), p['style']]

out = os.path.join(ROOT, 'Web/data/outdoor-seating.json')
json.dump({'patios': patios, 'fronts': fronts}, open(out, 'w'), separators=(',', ':'))
print(f'{len(patios)} patios, {len(fronts) // 5} storefront rows ({missed} places without a sign to go by), '
      f'{os.path.getsize(out) // 1024} KB')
