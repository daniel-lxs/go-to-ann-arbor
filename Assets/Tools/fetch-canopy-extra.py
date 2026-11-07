#!/usr/bin/env python3
# Tree cover where the city's Urban Tree Canopy doesn't reach: along the streets taken in whole past the city line
# (WHOLE_STREETS in build-annarbor.py). For each, one small aerial photo from USGS NAIP (The National Map, public
# domain, near infrared, red and green at about 1 m) over the street and 150 m round it; trees are what is green in the
# near infrared (NDVI) and rough (a crown's light and shade), smoothed into patches and written as canopy outlines in
# lon/lat to .lamp/reference/aa/canopy-extra/<street>.json, which build-annarbor.py reads beside the city's canopy
# outside the limits. Run from the app folder: python -I Assets/Tools/fetch-canopy-extra.py .
import json, math, os, re, sys, urllib.request, io
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as sw
from PIL import Image, ImageFilter
from shapely.geometry import LineString, box, mapping
from shapely.ops import unary_union

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else '.')
REF = os.path.join(ROOT, '.lamp/reference/aa')
OUT = os.path.join(REF, 'canopy-extra')
LAT0, LON0 = 42.27965, -83.74838
KX, KZ = 111320 * math.cos(math.radians(LAT0)), 110574
WHOLE_STREETS = ('Elizabeth Road',)
NAIP = 'https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer/exportImage'


def xz(lon, lat):
    return ((lon - LON0) * KX, -(lat - LAT0) * KZ)


def blur(x, r):
    return sw(np.pad(x, r, mode='edge'), (2 * r + 1, 2 * r + 1)).mean(axis=(-1, -2))


os.makedirs(OUT, exist_ok=True)
osm = json.load(open(os.path.join(REF, 'osm.json')))['elements']
for name in WHOLE_STREETS:
    lines = [LineString([xz(g['lon'], g['lat']) for g in e['geometry']]) for e in osm
             if e['type'] == 'way' and 'geometry' in e and e.get('tags', {}).get('name') == name and e.get('tags', {}).get('highway')]
    if not lines:
        print(f'{name}: not in the map')
        continue
    x0, z0, x1, z1 = unary_union(lines).buffer(150).bounds
    w, h = int(x1 - x0), int(z1 - z0)
    w0, s0, e0, n0 = LON0 + x0 / KX, LAT0 - z1 / KZ, LON0 + x1 / KX, LAT0 - z0 / KZ
    url = f'{NAIP}?bbox={w0:.6f},{s0:.6f},{e0:.6f},{n0:.6f}&bboxSR=4326&imageSR=4326&size={w},{h}&format=png&bandIds=3,0,1&f=image'
    raw = urllib.request.urlopen(url, timeout=120).read()
    a = np.asarray(Image.open(io.BytesIO(raw)).convert('RGB')).astype(float)
    nir, red = a[..., 0], a[..., 1]
    ndvi = (nir - red) / (nir + red + 1)
    rough = blur(sw(np.pad(nir, 3, mode='edge'), (7, 7)).std(axis=(-1, -2)), 4)
    tree = (blur(ndvi, 3) > 0.3) & (rough > 16)
    tree = np.asarray(Image.fromarray((tree * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(7))) > 0
    # each row's runs of tree pixels as boxes, joined; pixel (i, j) is 1 m at (x0 + j, z0 + i) near enough
    sx, sz = (x1 - x0) / w, (z1 - z0) / h
    cells = []
    for i in range(h):
        row = np.concatenate([[0], tree[i].astype(np.int8), [0]])
        d = np.diff(row)
        for j0, j1 in zip(np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]):
            cells.append(box(x0 + j0 * sx, z0 + i * sz, x0 + j1 * sx, z0 + (i + 1) * sz))
    cover = unary_union(cells).simplify(1.0)
    feats = []
    for p in getattr(cover, 'geoms', [cover]):
        if p.area < 12:
            continue
        rings = [[[round(LON0 + x / KX, 7), round(LAT0 - z / KZ, 7)] for x, z in r.coords] for r in [p.exterior, *p.interiors]]
        feats.append({'type': 'Feature', 'properties': {}, 'geometry': {'type': 'Polygon', 'coordinates': rings}})
    fn = os.path.join(OUT, re.sub(r'\W+', '-', name.lower()) + '.json')
    json.dump({'type': 'FeatureCollection', 'source': 'USGS NAIP', 'features': feats}, open(fn, 'w'))
    print(f'{name}: {len(feats)} patches, {cover.area / 1e4:.1f} ha of trees in {w} x {h} m ({tree.mean() * 100:.0f}%)')
