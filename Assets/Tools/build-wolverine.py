# Ann Arbor's Wolverine stops from Amtrak's GTFS feed (https://content.amtrak.com/content/gtfs/GTFS.zip, unzipped)
# -> Web/data/wolverine.json, read by railways.js. Each stop: [train, 'west'|'east', headsign, arrival s, departure s,
# days Mon..Sun, first date, last date]. Usage: python3 -I build-wolverine.py <feed folder> Web/data/wolverine.json
import csv, sys, json, os
feed, out_path = sys.argv[1], sys.argv[2]
def rows(n): return list(csv.DictReader(open(os.path.join(feed, n), encoding='utf-8-sig')))
info = rows('feed_info.txt')[0]
route = next(r['route_id'] for r in rows('routes.txt') if r['route_long_name'] == 'Wolverine')
trips = {t['trip_id']: t for t in rows('trips.txt') if t['route_id'] == route}
cal = {c['service_id']: c for c in rows('calendar.txt')}
st = {}
for r in rows('stop_times.txt'):
    if r['trip_id'] in trips: st.setdefault(r['trip_id'], []).append(r)
days = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday']
sec = lambda s: (lambda h, m, x: int(h) * 3600 + int(m) * 60 + int(x))(*s.split(':'))
out = []
for tid, times in st.items():
    times.sort(key=lambda r: int(r['stop_sequence']))
    ids = [r['stop_id'] for r in times]
    if 'ARB' not in ids: continue
    i = ids.index('ARB')
    t = trips[tid]; c = cal[t['service_id']]
    # coming from Dearborn it's heading west, toward Chicago
    out.append([t['trip_short_name'], 'west' if i > 0 and ids[i - 1] == 'DER' else 'east', t['trip_headsign'],
      sec(times[i]['arrival_time']), sec(times[i]['departure_time']),
      ''.join('1' if c[d] == '1' else '0' for d in days), c['start_date'], c['end_date']])
out.sort(key=lambda o: (o[3], o[6]))
json.dump({'source': 'Amtrak GTFS', 'version': info['feed_version'], 'station': 'ARB',
  'trips': out}, open(out_path, 'w'), separators=(',', ':'))
print(len(out), 'stops at Ann Arbor')
