# Builds TheRide's (Ann Arbor Area Transportation Authority) bus timetable for the game, in the world frame the city is
# drawn in (build-annarbor.py: 1 unit = 1 m, x east, z south, origin at Main St & Liberty St):
#   Web/data/theride.json.gz   routes, the stops in the map, each route's path, and every trip's times at those stops
# Source: TheRide's GTFS feed, https://www.theride.org/sites/default/files/google/google_transit.zip, unzipped to
#   .lamp/reference/gtfs/
# Run: python3 -I Assets/Tools/build-theride.py <app folder>
import csv, gzip, json, math, os, sys

app = sys.argv[1]
src = os.path.join(app, '.lamp/reference/gtfs')

# The frame (as build-annarbor.py)
A, E2 = 6378137.0, 0.00669437999014
LAT0, LON0 = 42.27965, -83.74838
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
def xz(lon, lat):
    return ((lon - LON0) * KX, -(lat - LAT0) * KY)
BBOX = (42.252, -83.782, 42.308, -83.693)  # S, W, N, E: the map
X0, Z1 = xz(BBOX[1], BBOX[0])
X1, Z0 = xz(BBOX[3], BBOX[2])
def inside(x, z, m=0):
    return X0 - m <= x <= X1 + m and Z0 - m <= z <= Z1 + m

def rows(name):
    with open(os.path.join(src, name), newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def secs(t):
    h, m, s = map(int, t.split(':'))
    return h * 3600 + m * 60 + s

def rdp(pts, eps):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, az), (bx, bz) = pts[a], pts[b]
        L = math.hypot(bx - ax, bz - az) or 1e-9
        best, bi = 0, -1
        for i in range(a + 1, b):
            px, pz = pts[i]
            d = abs((bx - ax) * (az - pz) - (ax - px) * (bz - az)) / L
            if d > best:
                best, bi = d, i
        if best > eps:
            keep[bi] = True
            stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]

# Routes
routes, route_ix = [], {}
for r in rows('routes.txt'):
    route_ix[r['route_id']] = len(routes)
    routes.append([r['route_short_name'], r['route_long_name'].title().replace('U-M', 'U-M'), '#' + (r['route_color'] or '1a5fb4')])

# Stops in the map
stop_rows = {s['stop_id']: s for s in rows('stops.txt')}
stops, stop_ix = [], {}
def stop_of(sid):
    if sid in stop_ix:
        return stop_ix[sid]
    s = stop_rows[sid]
    x, z = xz(float(s['stop_lon']), float(s['stop_lat']))
    if not inside(x, z):
        stop_ix[sid] = None
        return None
    stop_ix[sid] = len(stops)
    stops.append([s['stop_name'], round(x, 1), round(z, 1)])
    return stop_ix[sid]

# Trips' times at the stops in the map
times = {}
for st in rows('stop_times.txt'):
    times.setdefault(st['trip_id'], []).append((int(st['stop_sequence']), st['stop_id'], st['arrival_time'], st['departure_time']))

shape_pts = {}
for p in rows('shapes.txt'):
    shape_pts.setdefault(p['shape_id'], []).append((int(p['shape_pt_sequence']), float(p['shape_pt_lon']), float(p['shape_pt_lat'])))

shapes, shape_ix = [], {}
def shape_of(sid):
    if sid in shape_ix:
        return shape_ix[sid]
    pts = [xz(lon, lat) for _, lon, lat in sorted(shape_pts.get(sid, []))]
    ins = [i for i, (x, z) in enumerate(pts) if inside(x, z, 400)]
    if not ins:
        shape_ix[sid] = None
        return None
    pts = rdp(pts[ins[0]:ins[-1] + 1], 1.0)
    shape_ix[sid] = len(shapes)
    shapes.append([round(v, 1) for p in pts for v in p])
    return shape_ix[sid]

headsigns, head_ix = [], {}
services, service_ix = [], {}
trips = []
for t in rows('trips.txt'):
    st = sorted(times.get(t['trip_id'], []))
    seq = []
    for _, sid, arr, dep in st:
        k = stop_of(sid)
        if k is not None:
            seq += [k, secs(arr), secs(dep)]
    if len(seq) < 6:
        continue
    sh = shape_of(t['shape_id'])
    if sh is None:
        continue
    h = t['trip_headsign'] or routes[route_ix[t['route_id']]][1]
    if h not in head_ix:
        head_ix[h] = len(headsigns)
        headsigns.append(h)
    if t['service_id'] not in service_ix:
        service_ix[t['service_id']] = len(services)
        services.append(t['service_id'])
    # [route, shape, headsign, service, block, stop, arrive, depart, stop, arrive, depart, ...]
    trips.append([route_ix[t['route_id']], sh, head_ix[h], service_ix[t['service_id']], t['block_id'], *seq])
trips.sort(key=lambda r: r[6])

# Which days each service runs: weekdays (Monday first), the dates it runs between, and the dates added or taken off
calendar = []
for c in rows('calendar.txt'):
    if c['service_id'] in service_ix:
        days = ''.join(c[d] for d in ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'))
        calendar.append([service_ix[c['service_id']], days, c['start_date'], c['end_date']])
exceptions = [[service_ix[c['service_id']], c['date'], int(c['exception_type'])]
              for c in rows('calendar_dates.txt') if c['service_id'] in service_ix]
feed = rows('feed_info.txt')[0]

out = {'feed': [feed.get('feed_version', ''), feed.get('feed_start_date', ''), feed.get('feed_end_date', '')],
       'routes': routes, 'stops': stops, 'shapes': shapes, 'headsigns': headsigns,
       'calendar': calendar, 'exceptions': exceptions, 'trips': trips}
path = os.path.join(app, 'Web/data/theride.json.gz')
with gzip.open(path, 'wt', encoding='utf-8', compresslevel=9) as f:
    json.dump(out, f, separators=(',', ':'))
print(f'{len(routes)} routes, {len(stops)} stops in the map, {len(shapes)} paths, {len(trips)} trips; '
      f'{os.path.getsize(path) // 1024} KB')
