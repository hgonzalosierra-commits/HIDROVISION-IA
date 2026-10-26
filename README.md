# HIDRO-VISION

Aplicación local para comparar dos campañas de inspección de diques y elaborar un informe ejecutivo.

## Ejecutar en Windows

1. Instala Python 3.12 de 64 bits.
2. Entra en hidro-vision-ai-lite y ejecuta INSTALAR_WINDOWS.cmd.
3. Ejecuta INICIAR_HIDRO_VISION.cmd y abre http://127.0.0.1:8765/.

La instalación inicial descarga dependencias. La comparación de imágenes se ejecuta localmente. El especialista registra los hallazgos y niveles de atención que se incorporan al informe ejecutivo.

Las integraciones opcionales de OneDrive/Make requieren su configuración e internet. No son necesarias para comparar imágenes ni generar el informe.

Este repositorio contiene código, pruebas y datos meteorológicos públicos de referencia. No incluye campañas, videos, ortofotos privadas, bases de datos, resultados, claves ni bibliotecas instaladas. Consulta hidro-vision-ai-lite/README.md para los formatos de entrada y la documentación completa.

Los hallazgos pueden eliminarse del listado activo y recuperarse desde Hallazgos eliminados. Los informes existentes se conservan y deben regenerarse para reflejar cambios.
## Preparar los archivos de inspección

Para comparar dos fechas necesitas **dos archivos ZIP**, uno por campaña de inspección. Cada ZIP debe contener esta estructura:

```text
ENERO_2026.zip
├── VIDEO/
│   ├── vuelo.mp4
│   └── vuelo.srt
├── ORTOFOTO/
│   └── ortofoto.tif
├── PLANO_OTROS/
│   └── plano_referencial.pdf
└── XML/
    └── eje_dique.xml
```

Los nombres de los archivos son ejemplos. Las carpetas deben llamarse VIDEO, ORTOFOTO, PLANO_OTROS y XML.

### Información requerida

- **VIDEO:** exactamente un video y un archivo SRT del mismo vuelo. Ambos deben tener el mismo nombre base, por ejemplo `vuelo.mp4` y `vuelo.srt`. El SRT debe incluir tiempos y coordenadas GPS reconocibles: `latitude` / `longitude` o `GPS(longitud,latitud)`. Un SRT que solo contenga subtítulos de texto no sirve para ubicar los fotogramas.
- **ORTOFOTO:** exactamente un GeoTIFF `.tif` o `.tiff` georreferenciado, con sistema de coordenadas definido y al menos tres bandas RGB. Se admiten valores de color entre 0 y 255, almacenados en 8 o 16 bits. Una imagen JPG sin georreferenciación no reemplaza este archivo.
- **PLANO_OTROS:** al menos un plano o documento de referencia para identificar el dique, el tramo y sus progresivas.
- **XML:** exactamente un archivo LandXML con un solo alineamiento, unidades en metros y coordenadas proyectadas en metros. Se admiten rectas y arcos circulares con centro. No se admiten directamente espirales ni ecuaciones de progresiva.

Se recomienda video MP4 con códec H.264, compatible con el navegador y OpenCV.

### Compatibilidad entre campañas

Las dos campañas deben corresponder al mismo dique o tramo. Sus alineamientos deben coincidir y cubrir las mismas progresivas, y las ortofotos deben tener cobertura común en el tramo que se compara.

El video y el SRT deben corresponder entre sí. Identifica correctamente el mes y año de cada campaña al registrarla en el aplicativo.

### Límites de carga

- Máximo 30 GB por ZIP.
- Máximo 60 GB de contenido descomprimido por ZIP.
- Máximo 2000 archivos por ZIP.

Estos límites no garantizan que cualquier computador pueda procesar el conjunto: también se necesita suficiente memoria y espacio en disco.

### Uso de los datos

Cada usuario carga sus propias campañas desde el aplicativo. No es necesario subir videos, ortofotos, campañas ni resultados procesados al repositorio de GitHub.
