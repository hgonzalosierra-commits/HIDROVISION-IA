# HIDRO-VISION AI · distribución ligera

Aplicativo local para comparar dos campañas de inspección de diques. No requiere ChatGPT ni Codex. GitHub distribuye el código; el procesamiento se ejecuta en la computadora del usuario.

## Instalar y ejecutar en Windows

1. Descarga el repositorio con **Code → Download ZIP** y descomprímelo en una carpeta con espacio para tus campañas.
2. Instala **Python 3.12 de 64 bits** desde https://www.python.org/downloads/windows/ incluyendo el lanzador `py`.
3. Ejecuta **INSTALAR_WINDOWS.cmd** una vez. Necesita internet para descargar dependencias y espacio adicional para instalarlas en `.venv`.
4. Ejecuta **INICIAR_HIDRO_VISION.cmd**.
5. Abre http://127.0.0.1:8765/ y mantén la ventana del servidor abierta. Detén el servidor con Ctrl+C.

Si el puerto está ocupado por otra instancia de HIDRO-VISION, usa la instancia abierta o ciérrala antes de iniciar otra. Abre el enlace HTTP, no el archivo HTML mediante doble clic.

## Instalación manual

```sh
python -m venv .venv
# Windows:
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python server.py
# Linux/macOS, después de crear el entorno:
# .venv/bin/python -m pip install -r requirements.txt
# .venv/bin/python server.py
```

## Datos de entrada

Registra un ZIP por mes y año; selecciona dos campañas para comparar. Cada ZIP contiene:

- `VIDEO/`: video y SRT con el mismo nombre base.
- `ORTOFOTO/`: GeoTIFF RGB georreferenciado; 8 bits o 16 bits con colores entre 0 y 255.
- `PLANO_OTROS/`: planos referenciales de planta/perfil.
- `XML/`: alineamiento LandXML con progresivas en metros.

El eje y progresivas deben ser compatibles entre campañas. Se admiten rectas y arcos circulares con centro. El SRT debe incluir coordenadas GPS y tiempos. Los videos deben ser decodificables por OpenCV y compatibles con el navegador; MP4 H.264 es la opción habitual.

Se mantienen la comparación en planta, zoom, ortofotos y fotogramas por progresiva, videos simultáneos, historial y registro manual de hallazgos. La actualización incorpora un informe ejecutivo para jefatura y preparación del último PDF en OneDrive para avisar a Make. Los datos se guardan en `local_data/`, que se crea al iniciar.

## Qué significa «ligera»

Se distribuye el código, sin videos, ortofotos, campañas privadas, bases de datos, resultados de ejemplo ni bibliotecas preinstaladas. Los archivos originales permanecen en la computadora de su propietario. El tamaño de descarga no incluye Python, las dependencias ni los ZIP que cada usuario cargará. La carga y procesamiento de ortofotos grandes siguen necesitando memoria y disco suficientes; no se ha reducido su resolución original ni eliminado el procesador.

El visor conserva las observaciones registradas por personas y no inventa hallazgos. Se retiró de la interfaz el bloque de preguntas y entrenamiento. No hay un detector automático ni un LLM conectado. El PDF ejecutivo se genera mediante una plantilla. Para configurar la carpeta sincronizada de OneDrive, el webhook y el correo dinámico de Outlook, consulta [GUIA_ONEDRIVE_MAKE.md](GUIA_ONEDRIVE_MAKE.md). Los envíos se realizan mediante un botón y requieren configurar el escenario de Make; no hay envíos automáticos al generar informes.

## Eliminar y restaurar hallazgos

Cada hallazgo incluye Eliminar. Tras confirmar, se retira de la lista activa y de los nuevos informes, y puede recuperarse desde Hallazgos eliminados > Restaurar. Se conserva el historial de revisión. Los PDF anteriores mantienen su contenido; genera un nuevo informe después de eliminar o restaurar registros. Los informes anteriores quedan desactualizados para el envío.

## SENAMHI

`docs/evidencias/` contiene un catálogo de estaciones y las tablas horarias públicas consultadas el 25/10/2026 para Cañete (113249), enero y julio de 2026. Las sumas excluyen datos faltantes, no completan el mes con ceros y no constituyen diagnóstico de avenida. Para otras estaciones o meses se indica que el dato no ha sido consultado. No es una conexión en tiempo real.

Fuentes: https://www.senamhi.gob.pe/?p=estaciones y https://www.senamhi.gob.pe/mapas/mapa-estaciones-ms/map_red_graf.php?cod=113249 . Los registros horarios publicados por SENAMHI no tienen control de calidad. El enlace al boletín hidrológico es una referencia adicional, no una medición en el dique.

## Publicar el código en GitHub

Crea un repositorio vacío y sube **el contenido de esta carpeta**, conservando `docs/` y `docs/evidencias/`. No subas el ZIP dentro de otro ZIP ni incluyas `.venv/`, `local_data/`, `integration_config.json`, `respaldos_actualizacion/` o tus campañas. `.gitignore` excluye esos datos para cargas mediante Git.

GitHub Pages solo sirve contenido estático: no ejecuta `server.py` ni procesa ZIP. Para usar todas las funciones, descarga el proyecto y ejecútalo localmente. Un servicio web público requeriría un alojamiento Python y trabajo adicional de autenticación, almacenamiento y despliegue.

## Validación

```sh
python -m pip install -r requirements-test.txt
python -m unittest test_comparison test_platform test_delivery test_server test_finding_archive -v
```

`DISTRIBUCION.json` enumera los archivos del paquete y sus sumas SHA-256. No contiene rutas personales ni campañas del usuario.
