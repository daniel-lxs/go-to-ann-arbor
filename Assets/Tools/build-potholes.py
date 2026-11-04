# Builds Web/data/potholes.json: Ann Arbor's open pothole reports from the City's SeeClickFix 311 system (the same
# reports a2potholes.com maps), as [x, z, days open] in the world frame (1 unit = 1 m, x east, z south, origin at
# Main St & Liberty St). The game snaps each to the street beside it (potholes.js).
# Run: .lamp/reference/venv/bin/python -I Assets/Tools/build-potholes.py <app folder>
import datetime, json, os, sys, time, urllib.request

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.'
LAT0, LON0, KX, KY = 42.27965, -83.74838, 82487.0165, 111078.7167
URL = ('https://seeclickfix.com/api/v2/issues?place_url=ann-arbor&search=pothole&status=open,acknowledged'
       '&per_page=100&details=false&page={}')

issues, page = [], 1
while True:
    req = urllib.request.Request(URL.format(page), headers={'User-Agent': 'GoToAnnArbor/1.0'})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    issues += d['issues']
    if not d['metadata']['pagination'].get('next_page'):
        break
    page += 1
    time.sleep(1.5)

now = datetime.datetime.now(datetime.timezone.utc)
out, seen = [], set()
for i in issues:
    title = ((i.get('request_type') or {}).get('title') or i.get('summary') or '').lower()
    if 'pothole' not in title or i.get('lat') is None:
        continue
    x, z = (i['lng'] - LON0) * KX, (LAT0 - i['lat']) * KY
    key = (round(x / 2), round(z / 2))
    if key in seen:
        continue
    seen.add(key)
    days = (now - datetime.datetime.fromisoformat(i['created_at'])).days
    out += [round(x, 1), round(z, 1), max(0, days)]
json.dump({'fetched': now.strftime('%Y-%m-%d'), 'potholes': out}, open(os.path.join(ROOT, 'Web/data/potholes.json'), 'w'),
          separators=(',', ':'))
print(f'{len(issues)} reports, {len(out) // 3} potholes')
