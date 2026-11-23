// Exportar capas para el visor web de cobertura (INGEI El Salvador).
// Exporta a Google Drive, en EPSG:4326 y en las 11 clases INGEI:
//   1) Mapa oficial MARN 2016 (nacional)          -> visor_marn2016.tif
//   2) Piloto 5d Sentinel 2016 (Usulután)         -> visor_p5d2016.tif
// Uso: pegar en el editor de GEE, dar Run y luego RUN a cada tarea en la pestaña Tasks.
// Después: subir los .tif a los archivos del proyecto (ingei/09_scripts/visor/entrada/)
// y correr preparar_datos_visor.py (ver LEEME_visor.md).

var RUTA = 'projects/ingei-marn/assets/';
var ESCALA = 20;   // metros. 20 m es suficiente para el visor y deja archivos livianos; 10 m si se quiere más detalle.
var CARPETA = 'INGEI_visor';

var A11_16 = [1,2,3,4,9,11,10,7,7,6,8,5,7,9,10,6,6,10,11,10];   // clase 2016 (20) -> 11 clases INGEI
var pais = ee.FeatureCollection('FAO/GAUL/2015/level0').filter(ee.Filter.eq('ADM0_NAME', 'El Salvador')).geometry();
var usulutan = ee.FeatureCollection('FAO/GAUL/2015/level1')
  .filter(ee.Filter.inList('ADM1_NAME', ['Usulutan', 'Usulután'])).geometry();

// 1) MARN 2016 a 11 clases
var marn = ee.Image(RUTA + 'Cobertura_2016_MARN').select(0)
  .remap(ee.List.sequence(1, 20), A11_16, 0).rename('c11').toByte();
marn = marn.updateMask(marn.gt(0)).unmask(0);   // 0 = sin dato

// 2) Piloto 5d (banda c11)
var p5d = ee.Image(RUTA + 'clasif_2016_Usulutan_v4_bal_u16_rb3_r40_ca1450').select('c11').toByte().unmask(0);

var PAL11 = ['1a7a1a','6b8e23','8b0000','4f4782','00e6a9','ffebaf','e6e600','c2b800','c29ed7','005ce6','ff0000'];
Map.centerObject(pais, 8);
Map.addLayer(marn.selfMask(), {min: 1, max: 11, palette: PAL11}, 'MARN 2016 (11 clases)');
Map.addLayer(p5d.selfMask(), {min: 1, max: 11, palette: PAL11}, 'Piloto 5d (11 clases)');

Export.image.toDrive({
  image: marn.clip(pais), description: 'visor_marn2016', folder: CARPETA, fileNamePrefix: 'visor_marn2016',
  region: pais.bounds(), scale: ESCALA, crs: 'EPSG:4326', maxPixels: 1e13,
  fileFormat: 'GeoTIFF', formatOptions: {cloudOptimized: true}
});
Export.image.toDrive({
  image: p5d.clip(usulutan), description: 'visor_p5d2016', folder: CARPETA, fileNamePrefix: 'visor_p5d2016',
  region: usulutan.bounds(), scale: ESCALA, crs: 'EPSG:4326', maxPixels: 1e13,
  fileFormat: 'GeoTIFF', formatOptions: {cloudOptimized: true}
});
print('Listo: dar RUN a las tareas visor_marn2016 y visor_p5d2016 en la pestaña Tasks.');
