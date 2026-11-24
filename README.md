# Visor web de cobertura y uso del suelo - El Salvador (prototipo)

Página web estática (sin servidor) para mostrar los productos de cobertura del INGEI, sector UTCUTS.

## Qué muestra
- Malla de puntos 2001, 2011 y 2018 (21,103 parcelas, categoría IPCC; clic en una parcela muestra la clase detallada y el % de copa).
- Mapa LC Sentinel 2023 (el que usó el INGEI 2023).
- Comparación con cortina entre dos capas.
- Superficie por categoría IPCC (F, C, G, W, S, O) por año, para el país o un departamento.
- Mapa oficial MARN 2016 (nacional) y Piloto 5d Sentinel 2016 (Usulután), con matriz de coincidencia MARN vs piloto.

## Carpetas
- La raíz del repositorio es el visor completo: `index.html` + `datos/`. Se abre con cualquier servidor web (GitHub Pages, ArcGIS Online como sitio, servidor del MARN).
- `herramientas/preparar_datos_visor.py` genera los archivos de `sitio/datos/`.
- `herramientas/Exportar_capas_visor_GEE.js` exporta desde Earth Engine el mapa MARN 2016 y el Piloto 5d.
- `herramientas/leyendas/` tiene las leyendas (11 clases INGEI y su categoría IPCC) de las capas nuevas.

## Agregar un mapa nuevo (2016, 2020, 2025...)
1. En Earth Engine, correr `Exportar_capas_visor_GEE.js` (o exportar el mapa en EPSG:4326, una banda con el código de clase).
2. Subir el .tif a los archivos del proyecto.
3. Correr:
   `python3 herramientas/preparar_datos_visor.py visor_marn2016.tif . --capa marn2016 --leyenda herramientas/leyendas/leyenda_marn2016.json`
   (requiere Python con rasterio, numpy, scipy, shapely y pillow; Claude puede correrlo en la nube).
4. La capa aparece sola en el visor, en la lista de capas, en la cortina y en la tabla de superficies.

## Matriz entre dos mapas
`python3 herramientas/herramienta_matriz.py marn2016 visor_marn2016.tif herramientas/leyendas/leyenda_marn2016.json p5d2016 visor_p5d2016.tif herramientas/leyendas/leyenda_p5d2016.json .`

## Regenerar todo desde cero
`python3 herramientas/preparar_datos_visor.py malla_parcelas_GEE.csv . --lc2023 LC_SENTINEL_20231.tif`

## Publicar en GitHub Pages
1. Crear un repositorio en GitHub (p. ej. `visor-cobertura-sv`).
2. Subir el contenido de `sitio/` (index.html y la carpeta datos).
3. En Settings > Pages, elegir la rama `main` y la carpeta raíz. La dirección queda como `https://<usuario>.github.io/visor-cobertura-sv/`.

## Limitaciones del prototipo
- Límites de departamentos aproximados: se derivaron de la malla de 1 km (cada píxel toma el departamento de la parcela más cercana). Reemplazar por los límites oficiales del CNR.
- El mapa se muestra a unos 45 m por píxel para que cargue rápido; las superficies sí se calcularon a resolución completa (10 m).
- El mapa 2023 usa otra leyenda y otra fuente (clases tipo Esri), por lo que no es comparable directamente con la malla.
- Superficie de la malla: cada parcela representa 100 ha (malla sistemática de 1 km).

- `herramientas/plantilla.html` es la fuente de `index.html` (se le inserta el CSS de Leaflet 1.9.4).
