# Fetches the USGS 3D Elevation Program's 1 m bare-earth heights (3DEP, public domain) over the game's area, in 1 km
# squares of the game's own frame (x east, z south, metres from Main & Liberty), into .lamp/reference/dem1m/, once.
# build-annarbor.py reads them. Run: python -I Assets/Tools/fetch-3dep.py <app folder>
import math, os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.'
OUT = os.path.join(ROOT, '.lamp/reference/dem1m')
os.makedirs(OUT, exist_ok=True)
LAT0, LON0 = 42.27965, -83.74838
A, E2 = 6378137.0, 6.69437999014e-3
phi = math.radians(LAT0)
KX = math.pi / 180 * A / math.sqrt(1 - E2 * math.sin(phi) ** 2) * math.cos(phi)
KY = math.pi / 180 * A * (1 - E2) / (1 - E2 * math.sin(phi) ** 2) ** 1.5
# the city's limits (about x -4220..5900, z -4890..6330) and the ground grid round them (build-ground.py), in whole kilometres
CX0, CX1, CZ0, CZ1 = -6000, 7000, -6000, 7000
SERVICE = 'https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage'


def square(x0, z0):
    path = os.path.join(OUT, f'{x0}_{z0}.tif')
    if os.path.exists(path) and os.path.getsize(path) > 4_000_000:
        return
    w, e = LON0 + x0 / KX, LON0 + (x0 + 1000) / KX
    n, s = LAT0 - z0 / KY, LAT0 - (z0 + 1000) / KY
    url = (f'{SERVICE}?bbox={w},{s},{e},{n}&bboxSR=4326&imageSR=4326&size=1000,1000&format=tiff&pixelType=F32'
           '&noDataInterpretation=esriNoDataMatchAny&interpolation=RSP_BilinearInterpolation&compression=None&f=image')
    for attempt in range(6):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'GoToAnnArbor/1.0'})
            data = urllib.request.urlopen(req, timeout=180).read()
            if len(data) > 4_000_000 and data[:2] == b'II':
                open(path + '.part', 'wb').write(data)
                os.replace(path + '.part', path)
                print('got', x0, z0, flush=True)
                return
        except Exception as err:
            print('retry', x0, z0, err, flush=True)
        time.sleep(5 * (attempt + 1))
    print('FAILED', x0, z0, flush=True)


jobs = [(x, z) for z in range(CZ0, CZ1, 1000) for x in range(CX0, CX1, 1000)]
with ThreadPoolExecutor(4) as pool:
    list(pool.map(lambda j: square(*j), jobs))
print('done', len(jobs))
