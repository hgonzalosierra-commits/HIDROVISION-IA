# HIDRO-VISION: arquitectura local

Campañas ZIP > comparación geoespacial > revisión humana > informe ejecutivo > copia del último PDF a OneDrive sincronizado > aviso HTTPS a Make > enlace de OneDrive > correo Outlook.

## Componentes

- processor.py: validación y comparación geográfica, sin cambios en esta actualización.
- platform_store.py: campañas, hallazgos, revisión histórica, informes y snapshots para detectar cambios posteriores al PDF.
- executive_report.py: portada ejecutiva con tres estados por color y fichas de evidencia, según la plantilla suministrada.
- report_delivery.py: configuración local privada, copia atómica del PDF, verificación de integridad, registro de entrega y aviso a Make.
- server.py: API local, restringida a Host localhost o 127.0.0.1 y al puerto real del servidor.
- docs/platform.js e index.html: seis etapas, evaluación manual y envío del último informe. El bloque anterior de preguntas y entrenamiento se retiró de la interfaz.


## Datos y conservación

Se conservan los ZIP, campañas, resultados y registros existentes. Se añaden las tablas report_snapshots y report_deliveries a SQLite al usarlas. Los informes previos se conservan; para enviar se requiere un informe generado con la plantilla ejecutiva actual.

El nivel de atención corresponde al revisor. No existe un modelo entrenado que diagnostique daños. La nueva interfaz no solicita ni muestra un conjunto de entrenamiento; los registros y funciones históricos se conservan para no perder datos previos.

## Entrega

La subida a la nube la realiza el cliente de OneDrive de Windows. La aplicación solo certifica la copia local; el usuario comprueba que el archivo ya aparece en OneDrive web antes de avisar a Make. El aviso contiene la ruta en la nube y datos del informe, sin videos ni ortofotos.

Make debe usar file_path en Get a Share Link y email_subject / email_intro en Outlook. Una respuesta JSON al final del escenario permite distinguir recepción de confirmación de envío. No confirma lectura ni entrega final al buzón. No hay reintentos automáticos; las respuestas inciertas bloquean el reenvío local del mismo informe.

La configuración del webhook permanece en integration_config.json fuera de docs/ y local_data/. Los respaldos se guardan fuera de los directorios públicos.

## Verificación

python -m unittest test_comparison test_platform test_delivery test_server test_finding_archive -v

La guía GUIA_ONEDRIVE_MAKE.md detalla la configuración y la prueba final en la cuenta del usuario.

## Retiro de hallazgos

Eliminar mueve el registro activo a deleted_findings y añade un evento al historial de reviews. Restaurar devuelve el mismo identificador y evidencia al listado activo. Los informes previos conservan sus bytes, pero quedan desactualizados para nuevos envíos. Una vista antigua no puede sobrescribir una corrección posterior ni reactivar un hallazgo eliminado.
