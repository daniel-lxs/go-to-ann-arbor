# Ann Arbor's gas stations, in the game's frame (metres east and south of Main St & Liberty St), written to
# Web/data/gas-stations.json for gas-stations.js: flat [cx, cz, angle, length, width, replaces] per pump canopy.
# Each station is OpenStreetMap's amenity=fuel (ODbL). Its canopy is, in order: the station's own outline when OSM
# maps it as a roof; else the city's building outline on the station's land use parcel that is a canopy's shape (a
# near-perfect rectangle of 90-700 m² within 30 m of the station; `replaces` 1, so the game draws a canopy in its
# place rather than a building); else a canopy is set in the open part of the parcel, clear of its buildings.
# Inputs in .lamp/reference/aa: fuel/fuel.json (Overpass: amenity=fuel, building=roof), aa_bldg.geojson,
# aa_landuse.geojson. Run: python -I Assets/Tools/build-gas-stations.py <app folder>
import json, math, os, sys
import shapely
from shapely.geometry import shape, Point, Polygon
from shapely.ops import polylabel, unary_union
from shapely.validation import make_valid

ROOT = sys.argv[1]
REF = os.path.join(ROOT, '.lamp/reference/aa')
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5


def proj(g):
    return make_valid(shapely.transform(g, lambda c: [[(x - LON0) * KX, -(y - LAT0) * KY] for x, y in c]))


def box_of(poly):
    r = list(poly.minimum_rotated_rectangle.exterior.coords)[:4]
    e0 = (r[1][0] - r[0][0], r[1][1] - r[0][1])
    e1 = (r[2][0] - r[1][0], r[2][1] - r[1][1])
    L0, L1 = math.hypot(*e0), math.hypot(*e1)
    L, W, ax = (L0, L1, e0) if L0 >= L1 else (L1, L0, e1)
    c = poly.minimum_rotated_rectangle.centroid
    return c.x, c.y, math.atan2(ax[1], ax[0]), L, W


osm = json.load(open(os.path.join(REF, 'fuel/fuel.json')))['elements']
buildings = [proj(shape(f['geometry'])) for f in json.load(open(os.path.join(REF, 'aa_bldg.geojson')))['features']
             if f.get('geometry')]
tree = shapely.STRtree(buildings)
parcels = [proj(shape(f['geometry'])) for f in json.load(open(os.path.join(REF, 'aa_landuse.geojson')))['features']
           if f.get('geometry') and f['properties'].get('LANDUSE') == 'Auto Sales or Service']
ptree = shapely.STRtree(parcels)

out, how = [], {}
for e in osm:
    t = e.get('tags', {})
    if t.get('amenity') != 'fuel':
        continue
    if e['type'] == 'way' and t.get('building') == 'roof':
        roof = proj(Polygon([(q['lon'], q['lat']) for q in e['geometry']]))
        cx, cz, ang, L, W = box_of(roof)
        out += [round(cx, 1), round(cz, 1), round(ang, 3), round(L, 1), round(W, 1), 1]
        how['osm roof'] = how.get('osm roof', 0) + 1
        continue
    if e['type'] != 'node':
        continue
    p = proj(Point(e['lon'], e['lat']))
    near = [buildings[i] for i in tree.query(p.buffer(30))]
    shaped = [b for b in near if 90 <= b.area <= 700 and b.area / b.minimum_rotated_rectangle.area > 0.85]
    if shaped:
        b = min(shaped, key=lambda b: b.distance(p))
        cx, cz, ang, L, W = box_of(b)
        out += [round(cx, 1), round(cz, 1), round(ang, 3), round(L, 1), round(W, 1), 1]
        how['survey outline'] = how.get('survey outline', 0) + 1
        continue
    hits = [parcels[i] for i in ptree.query(p) if parcels[i].contains(p)]
    if not hits:
        continue
    parcel = hits[0]
    open_ = parcel.buffer(-2.5).difference(unary_union([b.buffer(3) for b in near] or [Point(0, 0).buffer(0)]))
    if open_.is_empty:
        continue
    piece = max(getattr(open_, 'geoms', [open_]), key=lambda g: g.area)
    c = polylabel(piece, 0.5)
    r = piece.exterior.distance(c) if piece.geom_type == 'Polygon' else 0
    _, _, ang, _, _ = box_of(parcel)
    L, W = min(20.0, r * 1.8), min(9.0, r * 1.3)
    if L < 8 or W < 6:
        continue
    out += [round(c.x, 1), round(c.y, 1), round(ang, 3), round(L, 1), round(W, 1), 0]
    how['open lot'] = how.get('open lot', 0) + 1

json.dump({'canopies': out}, open(os.path.join(ROOT, 'Web/data/gas-stations.json'), 'w'), separators=(',', ':'))
print(len(out) // 6, 'canopies', how)
