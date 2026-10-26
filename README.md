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
