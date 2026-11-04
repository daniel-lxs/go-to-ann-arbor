# Builds the ground's fine heights from the USGS 3D Elevation Program's 1 m bare-earth model (3DEP, public domain;
# fetched once by fetch-3dep.py into .lamp/reference/dem1m/), after build-annarbor.py has made the city's data:
#   Web/data/ground.bin.gz     the city's ground on a 6 m grid of 2049 x 2049 (GRD1), streets graded level across
#                              their width at their centreline's height, with a short slope to the ground each side
#   Web/data/elevation.bin.gz  the 10 m heights (ELV2) around it, made again from these where they cover it
#   Web/data/river.bin.gz      the river's levels (RIV1) made again over the new heights
# The game draws its ground as a mesh of right triangles fitted to the 4 m grid (terrain.js) and lays every street,
# sidewalk and lawn on those same triangles. The grid covers the whole of the city's limits (12.3 km a side).
# Run: .lamp/reference/venv/bin/python -I Assets/Tools/build-ground.py <app folder> [--out-suffix=-new]
import glob, gzip, json, math, os, struct, sys
import numpy as np
from PIL import Image

ROOT = sys.argv[1]
SUFFIX = next((a.split('=', 1)[1] for a in sys.argv[2:] if a.startswith('--out-suffix=')), '')
DEM = os.path.join(ROOT, '.lamp/reference/dem1m')
DATA = os.path.join(ROOT, 'Web/data')
STEP, N = 6.0, 2049
S_ = int(STEP)
# The grid's corner: the city's limits (about x -4220..5900, z -4890..6330) in the middle, each sample the middle of
# a 6 x 6 block of the 1 m squares
GX0, GZ0 = -5304.0, -5424.0
WALK = 5.0  # metres beyond a street's edge kept at its height too: its sidewalk, level across, so a bank
# behind a sidewalk rises from the sidewalk's back edge instead of tilting the sidewalk up it
SHOULDER = 6.0  # metres beyond that to where the ground is its own again

# --- The 10 m heights there are now (ELV2), for what the 1 m squares don't cover and for the base they're measured from
eb = gzip.open(os.path.join(DATA, 'elevation.bin.gz')).read()
ex0, ez0, estep, ecols, erows, LO = struct.unpack('<6f', eb[4:28])  # LO: the lowest height, from which they're stored
ecols, erows = int(ecols), int(erows)
E = np.frombuffer(eb, '<u2', ecols * erows, 28).reshape(erows, ecols).astype(np.float64) / 100.0 + LO


def bilinear(grid, x0, z0, step, x, z):
    fx = np.clip((x - x0) / step, 0, grid.shape[1] - 1.001)
    fz = np.clip((z - z0) / step, 0, grid.shape[0] - 1.001)
    c, r = np.floor(fx).astype(int), np.floor(fz).astype(int)
    ax, az = fx - c, fz - r
    return (grid[r, c] * (1 - ax) + grid[r, c + 1] * ax) * (1 - az) + (grid[r + 1, c] * (1 - ax) + grid[r + 1, c + 1] * ax) * az


# --- The 1 m squares as one picture, in the game's frame: row = z - MZ0, column = x - MX0
files = glob.glob(os.path.join(DEM, '*_*.tif'))
keys = sorted({tuple(int(v) for v in os.path.basename(f)[:-4].split('_')) for f in files if os.path.basename(f)[0] in '-0123456789'})
MX0, MZ0 = min(k[0] for k in keys), min(k[1] for k in keys)
MX1, MZ1 = max(k[0] for k in keys) + 1000, max(k[1] for k in keys) + 1000
LAT0, LON0 = 42.27965, -83.74838
A_, E2_ = 6378137.0, 6.69437999014e-3
KY = math.pi / 180 * A_ * (1 - E2_) / (1 - E2_ * math.sin(math.radians(LAT0)) ** 2) ** 1.5
M = np.full((MZ1 - MZ0, MX1 - MX0), np.nan, np.float32)
for x0, z0 in keys:
    im = Image.open(os.path.join(DEM, f'{x0}_{z0}.tif'))
    a = np.asarray(im, np.float32)
    a = np.where((a > -100) & (a < 1000), a, np.nan)
    # The service keeps its pixels square in degrees, so a square's rows are longer than its columns are wide (about
    # 1.35 m) and run past its edges: each 1 m row of the square is read between the two rows either side of it
    north, py = im.tag_v2[33922][4], im.tag_v2[33550][1]
    zr = -((north - (np.arange(a.shape[0]) + 0.5) * py) - LAT0) * KY  # each row's middle
    want = z0 + np.arange(1000) + 0.5
    f = np.clip(np.interp(want, zr, np.arange(a.shape[0])), 0, a.shape[0] - 1.001)
    r, t = np.floor(f).astype(int), (f - np.floor(f))[:, None]
    M[z0 - MZ0:z0 - MZ0 + 1000, x0 - MX0:x0 - MX0 + 1000] = a[r] * (1 - t) + a[r + 1] * t
print(f'1 m heights: {len(keys)} squares, x {MX0}..{MX1}, z {MZ0}..{MZ1}, {np.isnan(M).mean() * 100:.1f}% missing')


def at1m(x, z):
    # the 1 m model's height at (x, z), bilinear between pixel middles (NaN where it has none)
    fx, fz = x - MX0 - 0.5, z - MZ0 - 0.5
    ok = (fx >= 0) & (fz >= 0) & (fx < M.shape[1] - 1) & (fz < M.shape[0] - 1)
    c, r = np.floor(np.where(ok, fx, 0)).astype(int), np.floor(np.where(ok, fz, 0)).astype(int)
    ax, az = np.where(ok, fx, 0) - c, np.where(ok, fz, 0) - r
    h = (M[r, c] * (1 - ax) + M[r, c + 1] * ax) * (1 - az) + (M[r + 1, c] * (1 - ax) + M[r + 1, c + 1] * ax) * az
    return np.where(ok, h, np.nan)


# --- The grid: each sample the mean of the STEP x STEP metres round it
gx = GX0 + np.arange(N) * STEP
gz = GZ0 + np.arange(N) * STEP
H = np.full((N, N), np.nan)
c0, r0 = int(GX0 - S_ // 2 - MX0), int(GZ0 - S_ // 2 - MZ0)
# blocks of the picture that line up with the grid's samples
cols_in = [(i, c0 + i * S_) for i in range(N) if 0 <= c0 + i * S_ and c0 + i * S_ + S_ <= M.shape[1]]
rows_in = [(j, r0 + j * S_) for j in range(N) if 0 <= r0 + j * S_ and r0 + j * S_ + S_ <= M.shape[0]]
i0, i1 = cols_in[0][0], cols_in[-1][0] + 1
j0, j1 = rows_in[0][0], rows_in[-1][0] + 1
blk = M[rows_in[0][1]:rows_in[-1][1] + S_, cols_in[0][1]:cols_in[-1][1] + S_]
blk = blk.reshape(j1 - j0, S_, i1 - i0, S_)
with np.errstate(invalid='ignore'):
    H[j0:j1, i0:i1] = np.nanmean(blk, axis=(1, 3))
# The base the 10 m heights are measured from (their lowest half percent in town), so both agree
X, Z = np.meshgrid(gx, gz)
old = bilinear(E, ex0, ez0, estep, X, Z)
fit = ~np.isnan(H) & (old > 2)
BASE = float(np.median(H[fit] - old[fit]))
print(f'base {BASE:.2f} m (from {fit.sum()} samples); 1 m less 10 m: {np.percentile(np.abs(H[fit] - BASE - old[fit]), 99):.2f} m at the 99th percentile')
H = H - BASE
# where the 1 m model has nothing (off its squares, a gap), the 10 m heights, eased in over 40 m
miss = np.isnan(H)
H[miss] = old[miss]
if miss.any():
    # metres from the gap, up to 40 (4-neighbour steps)
    d = np.where(miss, 0.0, 40.0)
    for _ in range(11):
        p = np.pad(d, 1, mode='edge')
        d = np.minimum.reduce([d, p[:-2, 1:-1] + STEP, p[2:, 1:-1] + STEP, p[1:-1, :-2] + STEP, p[1:-1, 2:] + STEP])
    w = np.clip(d / 40, 0, 1)
    H = old + (H - old) * w
# a light blur (a sample's width), so a lawn doesn't take every hummock the survey saw
k = np.exp(-0.5 * (np.arange(-2, 3) / 0.7) ** 2)
k /= k.sum()
for axis in (0, 1):
    H = np.apply_along_axis(lambda r: np.convolve(np.pad(r, 2, mode='edge'), k, 'valid'), axis, H)

# --- Streets graded: level across their width at their centreline's height (the 1 m model's, eased along the street
# over about 20 m), its sidewalks (WALK) too, easing back to the ground over SHOULDER metres beyond them
src = open(os.path.join(ROOT, 'Web/js/city-geodata.js')).read()
GEO = json.loads(src[src.index('{', src.index('export const GEO')):src.rindex('}') + 1])
rg = GEO['roadGraph']
nodes = np.array(rg['nodes']).reshape(-1, 2)
river = gzip.open(os.path.join(DATA, 'river.bin.gz')).read()
rdx0, rdz0, rdstep, rdcols, rdrows = struct.unpack('<5f', river[4:24])
rdcols, rdrows = int(rdcols), int(rdrows)
dig = np.frombuffer(river, np.uint8, rdcols * rdrows, 44).reshape(rdrows, rdcols)


def in_water(x, z):
    c, r = int((x - rdx0) / rdstep), int((z - rdz0) / rdstep)
    return 0 <= c < rdcols and 0 <= r < rdrows and dig[r, c] > 0


# Each crossing's one height, the 1 m model's there, which every street meeting it comes to: eased on their own, two
# streets' ends would come to a corner at heights apart, and the ground between them would fold where they meet
node_h = at1m(nodes[:, 0], nodes[:, 1]) - BASE
gap = np.isnan(node_h)
node_h[gap] = bilinear(H, GX0, GZ0, STEP, nodes[gap, 0], nodes[gap, 1])
PIN = 14.0  # metres from a crossing over which a street eases to its height

tsum = np.zeros((N, N))
wsum = np.zeros((N, N))
wmax = np.zeros((N, N))
graded = 0
for link in rg['links']:
    a, b, w = link[0], link[1], link[3]
    pts = [nodes[a]] + [np.array(link[6][i:i + 2]) for i in range(0, len(link[6]), 2)] + [nodes[b]]
    # the line every 2 m
    line = [pts[0]]
    for p, q in zip(pts, pts[1:]):
        L = float(np.hypot(*(q - p)))
        n = max(1, int(math.ceil(L / 2)))
        line += [p + (q - p) * (t / n) for t in range(1, n + 1)]
    line = np.array(line)
    if len(line) < 2:
        continue
    h = at1m(line[:, 0], line[:, 1]) - BASE
    bad = np.isnan(h)
    if bad.all():
        continue
    h[bad] = bilinear(H, GX0, GZ0, STEP, line[bad, 0], line[bad, 1])
    # eased along the street (a 20 m window, its ends held), so its profile keeps the hill but not the bumps
    k = np.exp(-0.5 * (np.arange(-10, 11) / 4.0) ** 2)
    k /= k.sum()
    h = np.convolve(np.pad(h, 10, mode='reflect' if len(h) > 10 else 'edge'), k, 'valid')
    # its ends held to its crossings' heights, eased into its own profile over PIN metres (less on a short street)
    run = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(line, axis=0).T))])
    reach_pin = min(PIN, run[-1] / 2) or 1.0
    fa = np.clip(1 - run / reach_pin, 0, 1)
    fb = np.clip(1 - (run[-1] - run) / reach_pin, 0, 1)
    fa, fb = fa * fa * (3 - 2 * fa), fb * fb * (3 - 2 * fb)
    h = h + (node_h[a] - h[0]) * fa + (node_h[b] - h[-1]) * fb
    half = w / 2
    reach = half + WALK + SHOULDER
    for s in range(len(line) - 1):
        p, q = line[s], line[s + 1]
        mx, mz = (p + q) / 2
        if in_water(mx, mz):
            continue  # a bridge's deck carries it there (terrain.js)
        c0_ = max(0, int((min(p[0], q[0]) - reach - GX0) / STEP))
        c1_ = min(N - 1, int((max(p[0], q[0]) + reach - GX0) / STEP) + 1)
        r0_ = max(0, int((min(p[1], q[1]) - reach - GZ0) / STEP))
        r1_ = min(N - 1, int((max(p[1], q[1]) + reach - GZ0) / STEP) + 1)
        if c1_ < c0_ or r1_ < r0_:
            continue
        sx, sz = np.meshgrid(gx[c0_:c1_ + 1], gz[r0_:r1_ + 1])
        ex, ez = q - p
        l2 = ex * ex + ez * ez or 1e-9
        t = np.clip(((sx - p[0]) * ex + (sz - p[1]) * ez) / l2, 0, 1)
        d = np.hypot(sx - p[0] - ex * t, sz - p[1] - ez * t)
        u = np.clip((d - half - WALK) / SHOULDER, 0, 1)
        wt = np.where(d < reach, 1 - u * u * (3 - 2 * u), 0)
        target = h[s] + (h[s + 1] - h[s]) * t
        tsum[r0_:r1_ + 1, c0_:c1_ + 1] += wt * target
        wsum[r0_:r1_ + 1, c0_:c1_ + 1] += wt
        wmax[r0_:r1_ + 1, c0_:c1_ + 1] = np.maximum(wmax[r0_:r1_ + 1, c0_:c1_ + 1], wt)
    graded += 1
on = wsum > 0
before = H.copy()
H[on] = H[on] + (tsum[on] / wsum[on] - H[on]) * wmax[on]
print(f'{graded} streets graded: {on.mean() * 100:.1f}% of the grid moved, by {np.percentile(np.abs(H - before)[on], 95):.2f} m at the 95th percentile')

H = np.clip(H, LO, 600)
cm = np.round(H * 100).astype(np.int64)
# each sample less the one before it (the grid read row by row), which packs far smaller
delta = np.diff(cm.ravel(), prepend=0).astype('<i2')
hdr = b'GRD1' + struct.pack('<4f', GX0, GZ0, STEP, N)
with gzip.open(os.path.join(DATA, f'ground{SUFFIX}.bin.gz'), 'wb', 9) as f:
    f.write(hdr + delta.tobytes())
print('ground', N, 'x', N, 'at', STEP, 'm,', os.path.getsize(os.path.join(DATA, f'ground{SUFFIX}.bin.gz')) // 1024, 'KB')

# --- The 10 m heights made again from the fine grid where it covers them (so the outskirts meet it, and the shaders that
# read the heights see these)
EX, EZ = np.meshgrid(ex0 + np.arange(ecols) * estep, ez0 + np.arange(erows) * estep)
cover = (EX >= GX0) & (EX <= GX0 + (N - 1) * STEP) & (EZ >= GZ0) & (EZ <= GZ0 + (N - 1) * STEP)
inner = (EX >= GX0 + 100) & (EX <= GX0 + (N - 1) * STEP - 100) & (EZ >= GZ0 + 100) & (EZ <= GZ0 + (N - 1) * STEP - 100)
E2 = E.copy()
fine = bilinear(H, GX0, GZ0, STEP, EX, EZ)
# eased over the grid's outer 100 m, so the two meet without a step
from_edge = np.minimum.reduce([EX - GX0, GX0 + (N - 1) * STEP - EX, EZ - GZ0, GZ0 + (N - 1) * STEP - EZ])
wt = np.clip(from_edge / 100, 0, 1) * cover
E2 = E + (fine - E) * wt
with gzip.open(os.path.join(DATA, f'elevation{SUFFIX}.bin.gz'), 'wb', 9) as f:
    f.write(eb[:28] + np.round((np.clip(E2, LO, 600) - LO) * 100).astype('<u2').tobytes())
print('elevation', os.path.getsize(os.path.join(DATA, f'elevation{SUFFIX}.bin.gz')) // 1024, 'KB')

# --- The river's levels over the new heights (as build-annarbor.py makes them): the lowest ground within 40 m, a little
# under it, eased along the river
lx0, lz0, lstep, lcols, lrows = struct.unpack('<5f', river[24:44])
lcols, lrows = int(lcols), int(lrows)
lc0, lr0 = int(round((lx0 - ex0) / estep)), int(round((lz0 - ez0) / estep))
pad = 5
sub = E2[max(0, lr0 - pad):lr0 + lrows + pad, max(0, lc0 - pad):lc0 + lcols + pad]
low = sub.copy()
for _ in range(4):
    p = np.pad(low, 1, mode='edge')
    low = np.minimum.reduce([p[oy:oy + low.shape[0], ox:ox + low.shape[1]] for oy in range(3) for ox in range(3)])
lvl = low - 0.45
for _ in range(3):
    p = np.pad(lvl, 1, mode='edge')
    lvl = np.minimum(sum(p[oy:oy + lvl.shape[0], ox:ox + lvl.shape[1]] for oy in range(3) for ox in range(3)) / 9, low - 0.45)
oy, ox = lr0 - max(0, lr0 - pad), lc0 - max(0, lc0 - pad)
lvl = np.clip(lvl[oy:oy + lrows, ox:ox + lcols], LO, 300)
n = rdcols * rdrows
body = river[:44 + n + (n % 2)]
with gzip.open(os.path.join(DATA, f'river{SUFFIX}.bin.gz'), 'wb', 9) as f:
    f.write(body + np.round(lvl * 100).astype('<i2').tobytes())
print('river levels', lcols, 'x', lrows, os.path.getsize(os.path.join(DATA, f'river{SUFFIX}.bin.gz')) // 1024, 'KB')
