"""
Prepara los datos del visor web de cobertura (INGEI El Salvador).

Genera en <salida>/datos/:
  - departamentos.json     limites aproximados de departamentos (derivados de la malla de 1 km)
  - malla_puntos.json      parcelas de la malla 2001/2011/2018 (categoria IPCC y clase detallada)
  - superficies.json       superficie por categoria IPCC, por anio y por departamento
  - capa_<id>.png          raster de cobertura listo para la web (proyeccion Web Mercator)
  - capas.json             catalogo de capas raster (limites, leyenda, fuente)

Uso:
  python3 preparar_datos_visor.py <malla_parcelas_GEE.csv> <salida> [--lc2023 LC_SENTINEL_20231.tif]
  python3 preparar_datos_visor.py --capa <id> <geotiff> <salida> --leyenda <leyenda.json>
    (agrega un mapa nuevo exportado desde GEE, p. ej. MARN 2016 o Piloto 5d)
"""
import argparse, json, math, os
import numpy as np
import rasterio
from rasterio import features
from rasterio.enums import Resampling
from rasterio.transform import Affine
from scipy.spatial import cKDTree
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from PIL import Image

IPCC = {1: 'F', 2: 'C', 3: 'G', 4: 'W', 5: 'S', 6: 'O'}
DEPTOS_NOMBRE = {
    'Ahuachapan': 'Ahuachapán', 'Cabanas': 'Cabañas', 'Chalatenango': 'Chalatenango',
    'Cuscatlan': 'Cuscatlán', 'La Libertad': 'La Libertad', 'La Paz': 'La Paz',
    'La Union': 'La Unión', 'Morazan': 'Morazán', 'San Miguel': 'San Miguel',
    'San Salvador': 'San Salvador', 'San Vicente': 'San Vicente', 'Santa Ana': 'Santa Ana',
    'Sonsonate': 'Sonsonate', 'Usulutan': 'Usulután'}

# LC_SENTINEL_2023 (clases tipo Esri/IO LULC) -> categoria IPCC
LC2023 = {
    'id': 'lc2023', 'anio': 2023, 'nombre': 'Mapa LC Sentinel 2023',
    'fuente': 'LC_SENTINEL_20231.tif (clases tipo Esri/IO LULC, 10 m), usado en el INGEI 2023',
    'clases': [
        {'v': 1, 'nombre': 'Agua', 'color': '#2f7fc1', 'ipcc': 'W'},
        {'v': 2, 'nombre': 'Árboles', 'color': '#2e7d32', 'ipcc': 'F'},
        {'v': 4, 'nombre': 'Vegetación inundada', 'color': '#5fa8a0', 'ipcc': 'W'},
        {'v': 5, 'nombre': 'Cultivos', 'color': '#e2b53a', 'ipcc': 'C'},
        {'v': 7, 'nombre': 'Construido', 'color': '#c8312b', 'ipcc': 'S'},
        {'v': 8, 'nombre': 'Suelo desnudo', 'color': '#a8957c', 'ipcc': 'O'},
        {'v': 10, 'nombre': 'Nubes (sin dato)', 'color': '#d9dde3', 'ipcc': None},
        {'v': 11, 'nombre': 'Pastizal / arbustal', 'color': '#a9c46a', 'ipcc': 'G'},
    ]}


def hex2rgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def leer_malla(csv):
    import csv as _csv
    filas = list(_csv.DictReader(open(csv, encoding='utf-8-sig')))
    return filas


def departamentos(filas, lc_tif, salida):
    """Limites aproximados: cada pixel del pais (~90 m) toma el departamento de la parcela de malla mas cercana."""
    pts = np.array([[float(f['lon']), float(f['lat'])] for f in filas])
    nombres = sorted(set(f['depto'] for f in filas))
    idx = np.array([nombres.index(f['depto']) + 1 for f in filas])
    tree = cKDTree(pts * [math.cos(math.radians(13.8)), 1])
    with rasterio.open(lc_tif) as d:
        f = 8
        h, w = d.height // f, d.width // f
        a = d.read(1, out_shape=(h, w), resampling=Resampling.nearest)
        tr = d.transform * Affine.scale(d.width / w, d.height / h)
        valido = a != d.nodata
    jj, ii = np.meshgrid(np.arange(w), np.arange(h))
    xs = tr.c + (jj + 0.5) * tr.a; ys = tr.f + (ii + 0.5) * tr.e
    q = np.c_[xs[valido], ys[valido]] * [math.cos(math.radians(13.8)), 1]
    dist, k = tree.query(q, distance_upper_bound=0.02)
    cod = np.zeros((h, w), np.uint8)
    lab = np.where(np.isfinite(dist), idx[np.minimum(k, len(idx) - 1)], 0)
    cod[valido] = lab
    feats = []
    for n_i, n in enumerate(nombres, start=1):
        geoms = [shape(g) for g, v in features.shapes(cod, mask=cod == n_i, transform=tr) if v == n_i]
        u = unary_union(geoms).buffer(0.0006).buffer(-0.0006).simplify(0.002, preserve_topology=True)
        # quitar islotes minimos
        if u.geom_type == 'MultiPolygon':
            from shapely.geometry import MultiPolygon
            u = MultiPolygon([p for p in u.geoms if p.area > 2e-5])
        g = mapping(u)
        g = json.loads(json.dumps(g), parse_float=lambda s: round(float(s), 4))
        feats.append({'type': 'Feature', 'properties': {'id': n, 'nombre': DEPTOS_NOMBRE.get(n, n)}, 'geometry': g})
    fc = {'type': 'FeatureCollection', 'nota': 'Límites aproximados derivados de la malla de 1 km; reemplazar por los oficiales del CNR.', 'features': feats}
    json.dump(fc, open(os.path.join(salida, 'departamentos.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
    return nombres


def malla(filas, salida, sup):
    cols = ['parcela_id', 'lat', 'lon', 'depto']
    out = {'campos': ['id', 'lat', 'lon', 'depto', 'ipcc01', 'cl01', 'copa01', 'ipcc11', 'cl11', 'copa11', 'ipcc18', 'cl18', 'copa18'], 'filas': []}
    for f in filas:
        out['filas'].append([int(f['parcela_id']), round(float(f['lat']), 5), round(float(f['lon']), 5), f['depto']] +
                            sum([[int(f['ipcc' + a] or 0), int(f['cl' + a] or 0), int(f['copa' + a] or 0)] for a in ('01', '11', '18')], []))
    json.dump(out, open(os.path.join(salida, 'malla_puntos.json'), 'w'), separators=(',', ':'), ensure_ascii=False)
    # superficie: cada parcela representa 1 km2 (malla sistematica de 1 km) = 100 ha
    for a, anio in (('01', 2001), ('11', 2011), ('18', 2018)):
        key = 'malla%d' % anio
        sup[key] = {'anio': anio, 'fuente': 'Malla de puntos %d (21,103 parcelas, 1 parcela = 100 ha)' % anio, 'unidad': 'ha', 'deptos': {}}
        for f in filas:
            c = IPCC.get(int(f['ipcc' + a] or 0), 'SD')
            d = sup[key]['deptos'].setdefault(f['depto'], {})
            d[c] = d.get(c, 0) + 100


def capa_raster(cid, tif, leyenda, salida, sup, deptos_json, ancho=6000):
    """Convierte un GeoTIFF de clases a PNG Web Mercator y calcula superficie por departamento y categoria IPCC."""
    with rasterio.open(tif) as d:
        b = d.bounds
        crs_geo = d.crs.is_geographic
        if not crs_geo:
            raise SystemExit('El GeoTIFF debe venir en EPSG:4326 (en GEE: crs "EPSG:4326").')
        nod = d.nodata
        # ---- PNG Web Mercator (muestreo por vecino mas cercano)
        def merc(lat): return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
        y0, y1 = merc(b.top), merc(b.bottom)
        alto = int(round(ancho * (y0 - y1) / math.radians(b.right - b.left)))
        lats = np.degrees(2 * np.arctan(np.exp(y0 - (np.arange(alto) + 0.5) / alto * (y0 - y1))) - math.pi / 2)
        f = max(1, d.width // ancho)
        ov = d.read(1, out_shape=(d.height // f, d.width // f), resampling=Resampling.nearest)
        rows = np.clip(((b.top - lats) / (b.top - b.bottom) * ov.shape[0]).astype(int), 0, ov.shape[0] - 1)
        cols = np.clip(((np.arange(ancho) + 0.5) / ancho * ov.shape[1]).astype(int), 0, ov.shape[1] - 1)
        img = ov[rows][:, cols]
        pal = [0] * 768
        lut = np.zeros(256, np.uint8)
        for i, c in enumerate(leyenda['clases'], start=1):
            lut[c['v']] = i
            pal[i * 3:i * 3 + 3] = hex2rgb(c['color'])
        if nod is not None: lut[int(nod)] = 0
        p = Image.fromarray(lut[img], 'P'); p.putpalette(pal)
        trans = bytes([0] + [255] * 255)
        p.save(os.path.join(salida, 'capa_%s.png' % cid), optimize=True, transparency=trans)
        # ---- superficie a resolucion completa, por bloques de filas
        dep = json.load(open(deptos_json))
        shapes = [(feat['geometry'], i + 1) for i, feat in enumerate(dep['features'])]
        ids = [feat['properties']['id'] for feat in dep['features']]
        ipcc_de = {c['v']: c['ipcc'] for c in leyenda['clases']}
        acc = {}
        paso = 512
        for r0 in range(0, d.height, paso):
            n = min(paso, d.height - r0)
            win = rasterio.windows.Window(0, r0, d.width, n)
            a = d.read(1, window=win)
            wt = d.window_transform(win)
            dr = features.rasterize(shapes, out_shape=a.shape, transform=wt, fill=0, dtype='uint8')
            lat_c = wt.f + (np.arange(n) + 0.5) * wt.e
            area_px = (abs(wt.a) * 111320 * np.cos(np.radians(lat_c))) * (abs(wt.e) * 110574) / 1e4  # ha por pixel
            for v in ipcc_de:
                m = a == v
                if not m.any(): continue
                dd = dr[m]; ar = np.broadcast_to(area_px[:, None], a.shape)[m]
                s = np.bincount(dd, weights=ar, minlength=len(ids) + 1)
                for k in range(1, len(ids) + 1):
                    if s[k] > 0:
                        cat = ipcc_de[v] or 'SD'
                        acc.setdefault(ids[k - 1], {}); acc[ids[k - 1]][cat] = acc[ids[k - 1]].get(cat, 0) + float(s[k])
    sup[cid] = {'anio': leyenda['anio'], 'fuente': leyenda['fuente'], 'unidad': 'ha', 'alcance': leyenda.get('alcance'),
                'deptos': {k: {c: round(v) for c, v in d_.items()} for k, d_ in acc.items()}}
    return {'id': cid, 'anio': leyenda['anio'], 'nombre': leyenda['nombre'], 'fuente': leyenda['fuente'],
            'imagen': 'datos/capa_%s.png' % cid, 'limites': [[b.bottom, b.left], [b.top, b.right]], 'clases': leyenda['clases']}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('entrada'); ap.add_argument('salida')
    ap.add_argument('--lc2023'); ap.add_argument('--capa'); ap.add_argument('--geotiff'); ap.add_argument('--leyenda')
    a = ap.parse_args()
    dsal = os.path.join(a.salida, 'datos'); os.makedirs(dsal, exist_ok=True)
    psup = os.path.join(dsal, 'superficies.json'); pcap = os.path.join(dsal, 'capas.json')
    sup = json.load(open(psup)) if os.path.exists(psup) else {}
    capas = json.load(open(pcap)) if os.path.exists(pcap) else []
    if a.capa:  # agregar un mapa nuevo: entrada = geotiff
        ley = json.load(open(a.leyenda, encoding='utf-8'))
        c = capa_raster(a.capa, a.entrada, ley, dsal, sup, os.path.join(dsal, 'departamentos.json'))
    else:
        filas = leer_malla(a.entrada)
        departamentos(filas, a.lc2023, dsal)
        malla(filas, dsal, sup)
        c = capa_raster('lc2023', a.lc2023, LC2023, dsal, sup, os.path.join(dsal, 'departamentos.json'))
    capas = [x for x in capas if x['id'] != c['id']] + [c]
    capas.sort(key=lambda x: x['anio'])
    json.dump(capas, open(pcap, 'w'), ensure_ascii=False, indent=1)
    json.dump(sup, open(psup, 'w'), ensure_ascii=False, separators=(',', ':'))
    print('Listo:', dsal)


if __name__ == '__main__':
    main()
