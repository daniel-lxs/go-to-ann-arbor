# Ann Arbor's parking structures, in the game's frame (metres east and south of Main St & Liberty St), written to
# Web/data/parking-structures.json for parking-structures.js:
#   structures [{ name, levels, outline, frame, strip, decks, stalls }, ...]
#     name     its name on OpenStreetMap (ODbL), or ''
#     levels   building:levels when it's mapped (the ground floor counted), else null (parking-structures.js takes the
#              survey building's height)
#     outline  flat [x, z, ...]   its outer wall, as mapped
#     frame    [cx, cz, ux, uz]   the middle of its smallest enclosing rectangle and the way its long side runs
#     strip    [uA, uB, v0, v1]   the ramp bay in that frame: along u from uA (low end) to uB (high end), across v0..v1.
#              Every ramp climbs the same way, stacked one floor apart, so a driver goes up a ramp, turns along the deck
#              beside it and back to the ramp's low end for the next floor
#     decks    [[flat outer, flat hole, ...], ...]   each floor above the ground: the outline less the ramp bay
#     stalls   flat [x, z, yaw, ...]   the stalls on a floor (the same on every one), nose to the wall or the ramp
# Structures too small for a ramp, under construction, or mapped inside a bigger building are left as the survey drew them.
# Input: .lamp/reference/aa/ovp/parking-structures.json (Overpass: amenity=parking + parking=multi-storey, and
#        building=parking; ways and relations; out geom).
# Run: .lamp/reference/venv/bin/python -I Assets/Tools/build-parking-structures.py <app folder>
import json, math, os, sys
from shapely.geometry import Polygon, box
from shapely import affinity
from shapely.ops import unary_union

ROOT = sys.argv[1]
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
xz = lambda lon, lat: ((lon - LON0) * KX, -(lat - LAT0) * KY)

STRIP_W = 6.6      # the ramp bay, a lane each way between its walls
END = 8.5          # room at each end of the ramp to turn round
MAX_RAMP = 44
MIN_RAMP = 15
STALL_W, STALL_D, AISLE = 2.6, 5.3, 6.4
# Graffiti Alley runs into the Liberty Square structure; the alley's walls stand where the survey cut it back
ALLEY = box(483.0, 1.2, 491.6, 30.0)

def ring_of(geom):
    return [xz(q['lon'], q['lat']) for q in geom]

def outline_of(e):
    if e['type'] == 'way':
        return Polygon(ring_of(e['geometry']))
    outers = [Polygon(ring_of(m['geometry'])) for m in e.get('members', []) if m.get('role') == 'outer' and len(m.get('geometry') or []) >= 4]
    return max(outers, key=lambda p: p.area) if outers else None

def flat(coords):
    pts = list(coords)[:-1]
    return [round(v, 2) for p in pts for v in p]

def frame_of(poly):
    r = poly.minimum_rotated_rectangle
    c = list(r.exterior.coords)[:4]
    e0 = (c[1][0] - c[0][0], c[1][1] - c[0][1]); e1 = (c[2][0] - c[1][0], c[2][1] - c[1][1])
    l0, l1 = math.hypot(*e0), math.hypot(*e1)
    ux, uz = (e0[0] / l0, e0[1] / l0) if l0 >= l1 else (e1[0] / l1, e1[1] / l1)
    cx, cz = r.centroid.x, r.centroid.y
    return cx, cz, ux, uz, max(l0, l1), min(l0, l1)

def to_world(cx, cz, ux, uz, u, v):
    # v runs to the left of u: (-uz, ux)
    return cx + ux * u - uz * v, cz + uz * u + ux * v

def rect(cx, cz, ux, uz, u0, u1, v0, v1):
    return Polygon([to_world(cx, cz, ux, uz, u, v) for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1))])

data = json.load(open(os.path.join(ROOT, '.lamp/reference/aa/ovp/parking-structures.json')))
out, skipped, seen = [], [], set()
for e in data['elements']:
    t = e.get('tags', {})
    if e['id'] in seen or t.get('building') == 'construction' or 'construction' in t:
        continue
    seen.add(e['id'])
    poly = outline_of(e)
    if poly is None or not poly.is_valid:
        poly = poly.buffer(0) if poly is not None else None
    if poly is None or poly.area < 600:
        skipped.append((t.get('name'), 'small'))
        continue
    poly = poly.difference(ALLEY)
    if poly.geom_type != 'Polygon':
        poly = max(poly.geoms, key=lambda p: p.area)
    poly = poly.simplify(0.3)
    cx, cz, ux, uz, L, W = frame_of(poly)
    inner = poly.buffer(-0.35)
    ramp = min(MAX_RAMP, L - 2 * END)
    best = None
    if ramp >= MIN_RAMP:
        # the ramp bay down the middle where there's room for stalls each side, else along one long wall
        hw = STRIP_W / 2
        tries = [0.0] if W >= 34 else []
        tries += [W / 2 - 0.4 - hw, -(W / 2 - 0.4 - hw), 0.0]
        for vm in tries:
            for shift in (0, 2, -2, 4, -4, 6, -6):
                for r in (ramp, ramp - 4, ramp - 8):
                    if r < MIN_RAMP:
                        continue
                    s = rect(cx, cz, ux, uz, -r / 2 + shift, r / 2 + shift, vm - hw, vm + hw)
                    if inner.buffer(0.3).contains(s):
                        best = (-r / 2 + shift, r / 2 + shift, vm - hw, vm + hw)
                        break
                if best: break
            if best: break
    if not best:
        skipped.append((t.get('name'), 'no room for a ramp'))
        continue
    uA, uB, v0, v1 = best
    strip = rect(cx, cz, ux, uz, uA, uB, v0, v1)
    deck = poly.difference(strip)
    decks = []
    for d in (deck.geoms if deck.geom_type == 'MultiPolygon' else [deck]):
        if d.area < 20:
            continue
        d = d.simplify(0.05)
        decks.append([flat(d.exterior.coords)] + [flat(h.coords) for h in d.interiors])
    # stalls: a row nose-in along each long wall, and along each side of the ramp bay where the aisle between leaves room
    room = poly.buffer(-0.3).difference(strip.buffer(0.45))
    stalls = []
    rows = []
    half = W / 2
    # (rows in from each long wall, as a surface lot's: nose to the wall, an aisle, a row nose to nose with the next
    # pair's, every 18 m; all but the wall's own row keep to the ramp's length, clear of the turning room at its ends)
    for side in (1, -1):
        edge = half * side
        sv = v1 if side > 0 else v0
        gap = abs(edge - sv)
        for m in range(6):
            a, b = m * 18 + 0.6 + STALL_D / 2, m * 18 + 0.6 + STALL_D * 1.5 + AISLE
            if a + STALL_D / 2 + AISLE <= gap:
                rows.append((edge - side * a, side, m > 0))
            if b + STALL_D / 2 + 0.45 <= gap:
                rows.append((edge - side * b, -side, True))
    for vc, face, wall in rows:
        u = -L / 2 + STALL_W / 2
        while u < L / 2:
            s = rect(cx, cz, ux, uz, u - STALL_W / 2 + 0.05, u + STALL_W / 2 - 0.05, vc - STALL_D / 2, vc + STALL_D / 2)
            # a row along the ramp bay keeps to its length, clear of the turning room at each end
            if room.contains(s) and (not wall or uA + 1 < u < uB - 1):
                x, z = to_world(cx, cz, ux, uz, u, vc)
                # nose toward v = face: the world way (-uz, ux) * face
                stalls += [round(x, 2), round(z, 2), round(math.atan2(-uz * face, ux * face), 3)]
            u += STALL_W
    levels = None
    try:
        levels = int(float(t.get('building:levels') or t.get('parking:levels') or 0)) or None
    except ValueError:
        pass
    out.append({'name': t.get('name', ''), 'levels': levels, 'outline': flat(poly.exterior.coords),
                'frame': [round(cx, 2), round(cz, 2), round(ux, 5), round(uz, 5)],
                'strip': [round(uA, 2), round(uB, 2), round(v0, 2), round(v1, 2)], 'decks': decks, 'stalls': stalls})

path = os.path.join(ROOT, 'Web/data/parking-structures.json')
json.dump({'structures': out}, open(path, 'w'), separators=(',', ':'))
print(f'{len(out)} structures, {sum(len(s["stalls"]) // 3 for s in out)} stalls a floor, {os.path.getsize(path)} bytes')
for n, why in skipped:
    print('  left as surveyed:', n, '-', why)
