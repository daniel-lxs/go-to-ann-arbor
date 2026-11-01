# Ann Arbor's land use and historic districts, in the game's frame (metres east and south of Main St & Liberty St),
# written to Web/data/districts.json for city-config.js (landUseAt, historicDistrictAt):
#   historic  [{name, rings: [[x, z, x, z, ...], ...]}]   the city's Historic Districts (ckan.a2gov.org; no license)
#   landuse   {rings: [[use, x, z, x, z, ...], ...]}      the city's Land Use parcels (ckan.a2gov.org; no license):
#             1 single family, 2 two family, 3 apartments & group housing, 4 hotel, 5 shops & restaurants, 6 offices,
#             7 mixed use, 8 schools, civic & cultural, 9 religious, 10 industry & research, 11 recreation,
#             12 parking & transport, 13 vacant, 14 cemetery
# Inputs in .lamp/reference/aa: aa_landuse.geojson, aa_historic_districts.geojson (GeoJSON from ckan.a2gov.org).
# Run: python -I Assets/Tools/build-districts.py <app folder>
import json, math, os, sys
from shapely.geometry import shape
from shapely.validation import make_valid

ROOT = sys.argv[1]
REF = os.path.join(ROOT, '.lamp/reference/aa')
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5


def project(geom):
    from shapely.ops import transform
    return transform(lambda lon, lat, z=None: ((lon - LON0) * KX, -(lat - LAT0) * KY), geom)


def rings_of(geom, tol):
    geom = make_valid(project(geom)).simplify(tol, preserve_topology=True)
    polys = [geom] if geom.geom_type == 'Polygon' else [g for g in getattr(geom, 'geoms', []) if g.geom_type == 'Polygon']
    out = []
    for p in polys:
        if p.area < 20:
            continue
        flat = []
        for x, z in list(p.exterior.coords)[:-1]:
            flat += [round(x * 2) / 2, round(z * 2) / 2]
        out.append(flat)
    return out


USE = {
    'Single Family': 1, 'Two Family': 2, 'Multiple Family': 3, 'Group Housing': 3, 'Assisted Living': 3,
    'Mobile Home Park': 3, 'Bed and Breakfast': 2, 'Hotel-Motel': 4,
    'General and Mixed Retail': 5, 'Restaurant': 5, 'Personal Services': 5, 'Entertainment': 5, 'Trade Retail': 5,
    'Wholesale': 10, 'Auto Sales or Service': 5,
    'Financial Serv and Banks': 6, 'Medical Office': 6, 'Prof-General-Mixed Office': 6,
    'NonRes Mixed Use': 7, 'Res-NonRes Mixed Use': 7,
    'Education': 8, 'Government': 8, 'Cultural': 8, 'Assembly': 8, 'Organizations': 8, 'Institution': 8, 'Hospital': 8,
    'Religious': 9,
    'Heavy Manufacturing': 10, 'Light Assembly': 10, 'Non-Manufacturing': 10, 'Research': 10, 'Warehousing': 10,
    'Agricultural': 10, 'Communication Facility': 10, 'Utility Facilities': 10,
    'Indoor Recreation': 11, 'Mixed Use Recreation': 11, 'Outdoor Recreation': 11,
    'Parking': 12, 'Railroad': 12, 'Road Transportation': 12, 'Local Trans Depots and Facil': 12,
    'Vacant': 13, 'Cemetery': 14,
}

historic = []
for f in json.load(open(os.path.join(REF, 'aa_historic_districts.geojson')))['features']:
    if not f.get('geometry'):
        continue
    rings = rings_of(shape(f['geometry']), 1.0)
    if rings:
        historic.append({'name': f['properties']['FullName'].strip(), 'rings': rings})

landuse, counts = [], {}
for f in json.load(open(os.path.join(REF, 'aa_landuse.geojson')))['features']:
    use = USE.get((f['properties'].get('LANDUSE') or '').strip())
    if not use or not f.get('geometry'):
        continue
    for r in rings_of(shape(f['geometry']), 1.5):
        landuse.append([use] + r)
        counts[use] = counts.get(use, 0) + 1

out = {'historic': historic, 'landuse': landuse}
path = os.path.join(ROOT, 'Web/data/districts.json')
json.dump(out, open(path, 'w'), separators=(',', ':'))
print(f'{len(historic)} historic districts, {len(landuse)} land use parcels {sorted(counts.items())}, '
      f'{os.path.getsize(path) // 1024} KB')
