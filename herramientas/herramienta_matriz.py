"""
Matriz de cambio IPCC (ha) entre dos mapas de clases, por departamento.
Uso: python3 herramienta_matriz.py <idA> <tifA> <leyendaA.json> <idB> <tifB> <leyendaB.json> <carpeta_sitio>
Agrega la matriz a <carpeta_sitio>/datos/matrices.json con clave "idA|idB".
El mapa B se lleva a la grilla de A (vecino mas cercano); solo cuenta donde ambos tienen dato.
"""
import sys, json, os
import numpy as np, rasterio
from rasterio import features
from rasterio.warp import reproject, Resampling

idA, tA, lA, idB, tB, lB, sitio = sys.argv[1:8]
legA = json.load(open(lA, encoding='utf-8')); legB = json.load(open(lB, encoding='utf-8'))
CAT = ['F', 'C', 'G', 'W', 'S', 'O']
def lut(leg):
    l = np.full(256, 255, np.uint8)
    for c in leg['clases']:
        if c.get('ipcc') in CAT: l[c['v']] = CAT.index(c['ipcc'])
    return l
la, lb = lut(legA), lut(legB)
dep = json.load(open(os.path.join(sitio, 'datos', 'departamentos.json')))
ids = [f['properties']['id'] for f in dep['features']]
with rasterio.open(tA) as A, rasterio.open(tB) as B:
    # recortar A a la extension de B si B es mas chico
    win = rasterio.windows.from_bounds(*B.bounds, transform=A.transform).round_offsets().round_lengths()
    win = win.intersection(rasterio.windows.Window(0, 0, A.width, A.height))
    a = A.read(1, window=win); tr = A.window_transform(win)
    b = np.zeros_like(a)
    reproject(B.read(1), b, src_transform=B.transform, src_crs=B.crs, dst_transform=tr, dst_crs=A.crs, resampling=Resampling.nearest)
    dr = features.rasterize([(f['geometry'], i + 1) for i, f in enumerate(dep['features'])], out_shape=a.shape, transform=tr, fill=0, dtype='uint8')
    lat = tr.f + (np.arange(a.shape[0]) + 0.5) * tr.e
    area = (abs(tr.a) * 111320 * np.cos(np.radians(lat)))[:, None] * (abs(tr.e) * 110574) / 1e4
    ca, cb = la[a], lb[b]
    ok = (ca < 6) & (cb < 6) & (dr > 0)
    key = dr[ok].astype(np.int64) * 36 + ca[ok].astype(np.int64) * 6 + cb[ok]
    s = np.bincount(key, weights=np.broadcast_to(area, a.shape)[ok], minlength=(len(ids) + 1) * 36)
out = {}
for k in range(1, len(ids) + 1):
    m = s[k * 36:(k + 1) * 36].reshape(6, 6)
    if m.sum() < 1: continue
    out[ids[k - 1]] = {CAT[i]: {CAT[j]: round(float(m[i, j])) for j in range(6) if m[i, j] >= 0.5} for i in range(6) if m[i].sum() >= 0.5}
p = os.path.join(sitio, 'datos', 'matrices.json')
mz = json.load(open(p)) if os.path.exists(p) else {}
mz[idA + '|' + idB] = {'nota': 'Comparación píxel a píxel donde los dos mapas tienen dato.', 'deptos': out}
json.dump(mz, open(p, 'w'), ensure_ascii=False, separators=(',', ':'))
print('Listo', idA, idB, {k: round(sum(sum(r.values()) for r in v.values())) for k, v in out.items()})
