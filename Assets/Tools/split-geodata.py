#!/usr/bin/env python3
# Takes the heaviest layers out of Web/js/city-geodata.js (written by build-annarbor.py, which runs this at its end) into
# compact binary files the game reads only as it needs them, so the page never parses the whole city as one script:
#   Web/data/yards/<tx>_<tz>.bin.gz  the driveways, walks and lawns over each 500 m square (YRD1), a polygon in every
#                                    square its bounds reach, so a square's file draws all of it that falls there
#   Web/data/yards/index.json        the squares there are, and a fingerprint of them all
#   Web/data/woods.bin.gz            the woods', parks' and yards' trees: x, z as Float32 and their kind (WDS1)
#   Web/data/curb-cuts.bin.gz        where each driveway meets the curb: x, z, the way to the street and its width (CUT1)
# YRD1: 'YRD1', then uint32 n, rings, points; uint32 ids[n] (a driveway's place in the city's list, a lawn's 1000000 +
# its place), kinds[n] (0 driveway, 1 lawn), rings of each[n], points of each ring[rings]; float32 x, z of every point.
# Usage: python3 Assets/Tools/split-geodata.py
import gzip, hashlib, json, math, os, struct, sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
JS = os.path.join(ROOT, 'Web', 'js', 'city-geodata.js')
DATA = os.path.join(ROOT, 'Web', 'data')
TILE = 500
PREFIX = 'export const GEO = '

text = open(JS).read()
head, body = text.split(PREFIX, 1)
GEO = json.loads(body.rstrip().rstrip(';'))
if 'driveways' not in GEO:
    print('city-geodata.js is already split'); sys.exit(0)

def write(path, data):
    with open(path, 'wb') as f: f.write(gzip.compress(data, 9, mtime=0))

# the yards, by square
tiles = {}
for kind, key, base in ((0, 'driveways', 0), (1, 'lawns', 1000000)):
    for i, rings in enumerate(GEO.pop(key)):
        xs = [v for r in rings for v in r[0::2]]; zs = [v for r in rings for v in r[1::2]]
        for tx in range(math.floor(min(xs) / TILE), math.floor(max(xs) / TILE) + 1):
            for tz in range(math.floor(min(zs) / TILE), math.floor(max(zs) / TILE) + 1):
                tiles.setdefault((tx, tz), []).append((base + i, kind, rings))
out = os.path.join(DATA, 'yards')
os.makedirs(out, exist_ok=True)
for f in os.listdir(out): os.remove(os.path.join(out, f))
index, digest = {}, hashlib.sha1()
for (tx, tz), polys in sorted(tiles.items()):
    lens = [len(r) // 2 for _, _, rings in polys for r in rings]
    data = b'YRD1' + struct.pack('<3I', len(polys), len(lens), sum(lens))
    data += struct.pack(f'<{len(polys)}I', *[p[0] for p in polys])
    data += struct.pack(f'<{len(polys)}I', *[p[1] for p in polys])
    data += struct.pack(f'<{len(polys)}I', *[len(p[2]) for p in polys])
    data += struct.pack(f'<{len(lens)}I', *lens)
    coords = [v for _, _, rings in polys for r in rings for v in r]
    data += struct.pack(f'<{len(coords)}f', *coords)
    write(os.path.join(out, f'{tx}_{tz}.bin.gz'), data)
    digest.update(data)
    index[f'{tx},{tz}'] = len(polys)
json.dump({'tile': TILE, 'version': digest.hexdigest()[:12], 'tiles': index}, open(os.path.join(out, 'index.json'), 'w'), separators=(',', ':'))

W = GEO.pop('woods')
n = len(W) // 3
write(os.path.join(DATA, 'woods.bin.gz'), b'WDS1' + struct.pack('<I', n) + struct.pack(f'<{2 * n}f', *[v for i in range(n) for v in W[i * 3:i * 3 + 2]])
      + bytes(int(W[i * 3 + 2]) for i in range(n)))
C = [v for c in GEO.pop('curbCuts') for v in c]
write(os.path.join(DATA, 'curb-cuts.bin.gz'), b'CUT1' + struct.pack('<I', len(C) // 5) + struct.pack(f'<{len(C)}f', *C))

with open(JS, 'w') as f:
    f.write(head.replace('// Polygons & polylines', '// The driveways, lawns, woods and curb cuts are in data/ (split-geodata.py), read as needed (yards.js).\n// Polygons & polylines', 1)
            + PREFIX)
    json.dump(GEO, f, separators=(',', ':'))
    f.write(';\n')
print(f'{len(tiles)} yard squares, {n} trees, {len(C) // 5} curb cuts; geodata now {os.path.getsize(JS) // 1024} KB')
