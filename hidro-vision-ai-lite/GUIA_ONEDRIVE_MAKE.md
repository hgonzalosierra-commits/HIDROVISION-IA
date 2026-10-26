# HIDRO-VISION: informe ejecutivo, OneDrive y Outlook

## Qué cambió

- Se retiró el bloque de preguntas y entrenamiento. El registro manual de hallazgos se conserva y las etapas se renumeran del 1 al 6.
- El PDF tiene una portada ejecutiva para jefatura, resumen por niveles de atención y una ficha por hallazgo con evidencias de ambas campañas. Las fichas comienzan por los hallazgos urgentes.
- Los colores corresponden a la clasificación del revisor: verde = seguimiento, amarillo = inspección prioritaria y rojo = alerta urgente. No representan un diagnóstico automático.
- Solo se puede preparar el último informe de la comparación abierta. Si hay correcciones posteriores, se exige generar un PDF actualizado.
- Se copia únicamente ese PDF a una carpeta sincronizada de OneDrive. Make recibe la ruta en la nube, el asunto y el resumen del correo.

## 1. Ver los cambios

1. Detén la ventana del servidor con Ctrl+C, si sigue abierta.
2. Abre otra vez INICIAR_HIDRO_VISION.cmd.
3. En http://127.0.0.1:8765/ pulsa Ctrl+F5 para recargar los archivos del visor.
4. Abre la comparación guardada: no necesitas volver a cargar ni procesar los ZIP.
5. En Informe para jefatura, escribe el dique o tramo y genera un nuevo PDF. Los PDF históricos siguen disponibles con su formato anterior.

## 2. OneDrive en el computador

Esta versión utiliza el cliente de sincronización de OneDrive de Windows. No realiza una subida directa mediante Microsoft Graph ni necesita registrar otra aplicación en Azure.

1. Comprueba que OneDrive de Windows tenga iniciada la misma cuenta que utiliza la conexión de OneDrive en Make.
2. La carpeta HIDRO-VISION / Informes enviados debe estar sincronizada y visible en el Explorador de archivos. Crear una carpeta únicamente en la web no basta.
3. Copia la ruta local de Informes enviados desde la barra del Explorador.
4. En la etapa 06, abre Configurar OneDrive y Make. Pega esa ruta local y la URL original de tu webhook (sin ?prueba=1).
5. En Ruta de esa carpeta dentro de OneDrive indica /HIDRO-VISION/Informes enviados, o la ruta real si creaste otras carpetas.
6. La clave del webhook es opcional: solo se completa si ya activaste API Key authentication en Make.
7. Guarda la configuración.

Las credenciales de Microsoft permanecen en OneDrive/Make. La URL del webhook y su clave se guardan en integration_config.json, fuera de los directorios públicos del servidor, y se excluyen de Git. No publiques ese archivo ni lo compartas en capturas.

## 3. Adaptar el escenario ya probado en Make

El escenario actual utiliza un PDF fijo y texto escrito a mano. Antes de enviar desde HIDRO-VISION, reemplaza esos valores por los campos dinámicos.

Mantén el flujo:

Webhook > OneDrive: Get a Share Link > Microsoft 365 Email (Outlook): Send an Email > Webhooks: Webhook response

### Estructura del webhook

En la configuración del webhook, usa Advanced settings > Data structure > Add. Genera la estructura con el JSON de MAKE_ESTRUCTURA_EJEMPLO.json (Generator > JSON > Sample data). Guarda la estructura y selecciónala en el webhook. Es una muestra de formato, no corresponde a un PDF real y no debe ejecutarse para enviar correo.

Si el editor muestra nombres distintos, usa la sección Datos para configurar Make de HIDRO-VISION después de copiar el PDF; ofrece el mismo contrato con valores reales. No uses la antigua solicitud ?prueba=1 para el escenario definitivo.

### OneDrive: Get a Share Link

- Conserva la conexión y el mismo OneDrive donde se sincroniza la carpeta.
- Cambia Enter (File ID & File Path) de File ID a File Path.
- En el campo de ruta inserta file_path del webhook. Ya no selecciones el PDF de prueba del listado.
- Mantén Only Read.
- Si los destinatarios son de la misma institución, utiliza el alcance de organización que probaste. Ese alcance no habilita el acceso a destinatarios externos. La política y permisos de Microsoft determinan quién puede abrir el vínculo.

### Outlook: Send an Email

- To Recipients: revisa y conserva los destinatarios reales en Make; la aplicación no los cambia.
- Subject: reemplaza el texto fijo por email_subject del webhook.
- Body Content: escribe Hola, deja una línea, inserta email_intro del webhook, deja otra línea y escribe Consultar informe: seguido de Link: Web Url de OneDrive. Termina con Saludos, Equipo HIDRO-VISION.
- Deja Attachments vacío: se envía el enlace al PDF.
- Si utilizas contenido HTML, genera el texto con escape HTML antes de insertarlo; el campo email_intro es texto plano.

### Confirmación del envío

Añade al final Webhooks > Webhook response, después de Outlook:

- Status: 200.
- Content-Type: application/json.
- Body: {"status":"sent","report_id":"VALOR_DINAMICO_DEL_WEBHOOK"}.

En report_id inserta la variable report_id del webhook, no copies literalmente VALOR_DINAMICO_DEL_WEBHOOK.

Colocar esta respuesta después de Outlook permite registrar Envío confirmado por Make. La respuesta automática Accepted solo confirma recepción por Make. La confirmación no certifica lectura ni entrega final al buzón.

No configures respuestas status=failed después de que Outlook haya enviado un correo: esa respuesta indica un fallo anterior al envío y habilita un reintento. Los errores sin certeza deben revisarse en el historial de Make.

## 4. Primera prueba con el último informe real

1. Limita To Recipients a tu propio correo durante la prueba.
2. Guarda y activa el escenario definitivo. Debe procesar solicitudes del webhook cuando lleguen.
3. En HIDRO-VISION genera el informe y revísalo.
4. Pulsa 1. Copiar último PDF a OneDrive. El archivo tiene el nombre HIDRO_VISION_<id_del_informe>.pdf; es único por versión.
5. Espera hasta que ese nombre exacto aparezca en OneDrive web. La aplicación comprueba la copia local; no puede certificar que el cliente de OneDrive haya terminado de subirla.
6. Marca las confirmaciones de sincronización y de mapeo dinámico del escenario.
7. Pulsa 2. Enviar aviso a Make. Esta acción puede enviar el correo a los destinatarios configurados en Make.
8. Revisa Seguimiento, el historial del escenario y el correo. Comprueba también que el enlace corresponda al último PDF.

## Seguimiento y duplicados

- PDF copiado: no se ha avisado a Make.
- Recibido por Make: falta confirmar que Outlook haya enviado el correo.
- Envío confirmado: Make devolvió la confirmación posterior a Outlook.
- Sin confirmación: revisa el historial de Make antes de reintentar. La aplicación bloquea el reenvío del mismo informe para evitar duplicados.
- Solicitud rechazada: corrige la configuración antes de un reintento manual.

No hay reenvíos automáticos. Si Make aceptó el aviso pero falló después, corrige y reanuda la ejecución desde su historial, comprobando primero si Outlook ya envió el mensaje.

La protección de duplicados de la aplicación evita avisar dos veces por el mismo informe. Los reintentos o reproducciones que se ejecuten manualmente en Make requieren revisar su historial.

## Fuentes de configuración

- https://apps.make.com/onedrive
- https://apps.make.com/gateway
- https://help.make.com/data-structures

## Validación del cambio

Se ejecutaron 19 pruebas de comparación, persistencia, PDF, entrega y API local. Incluyen selección del último informe, rechazo de informes desactualizados, integridad del archivo, bloqueo de envíos simultáneos/duplicados, protección de la configuración y distinción entre recepción y confirmación. Se revisaron visualmente las cuatro páginas del PDF con los hallazgos existentes y se probó la pantalla en una copia local. Los ensayos de entrega usan respuestas simuladas: la configuración de tu cuenta y el escenario real deben completarse para realizar la prueba final.
