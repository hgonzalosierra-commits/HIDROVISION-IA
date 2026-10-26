"""Copy only the latest PDF to a OneDrive sync folder, then notify Make."""
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError
import hashlib, json, os, re, shutil, socket, uuid
import platform_store as workflow
from processor import ROOT, check

CONFIG = ROOT / 'integration_config.json'  # Outside /docs and /data: never served.
STATE_LABELS = {
    'copied_to_onedrive': 'PDF copiado; confirma la sincronización de OneDrive',
    'sending': 'Aviso en curso', 'make_received': 'Recibido por Make; envío de correo pendiente de confirmar',
    'sent': 'Envío de correo confirmado por Make',
    'uncertain': 'Sin confirmación; revisa el historial de Make antes de reenviar',
    'failed': 'Make rechazó la solicitud; revisa la configuración',
}

def init_db():
    with workflow.connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS report_deliveries(
          id TEXT PRIMARY KEY, report TEXT NOT NULL UNIQUE, comparison TEXT NOT NULL,
          file_name TEXT NOT NULL, target TEXT NOT NULL, cloud_path TEXT NOT NULL, state TEXT NOT NULL,
          detail TEXT NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL)''')

def read_config():
    if not CONFIG.is_file():return {}
    return json.loads(CONFIG.read_text(encoding='utf8'))

def settings():
    config=read_config()
    return dict(onedrive_folder=config.get('onedrive_folder',''),remote_folder=config.get('remote_folder','/HIDRO-VISION/Informes enviados'),webhook_configured=bool(config.get('webhook_url')),
                api_key_configured=bool(config.get('api_key')),ready=bool(config.get('onedrive_folder') and config.get('webhook_url')),
                onedrive_hint=os.environ.get('OneDriveCommercial') or os.environ.get('OneDrive',''))

def valid_webhook(url):
    parsed=urlparse(url)
    check(parsed.scheme=='https' and bool(re.fullmatch(r'hook(?:\.[a-z0-9-]+)?\.(?:make|integromat)\.com',parsed.hostname or ''))
          and parsed.username is None and parsed.password is None and parsed.port in (None,443)
          and len(parsed.path)>1 and not parsed.query and not parsed.fragment,
          'Pega la URL HTTPS original del webhook de Make, sin ?prueba=1 ni otros parámetros.')

def save_settings(payload):
    config=read_config()
    folder=Path(str(payload.get('onedrive_folder','')).strip()).expanduser()
    check(folder.is_absolute() and folder.is_dir(),'Selecciona una carpeta local existente de OneDrive sincronizada con la misma cuenta de Make.')
    folder=folder.resolve()
    check(not folder.is_relative_to(ROOT.resolve()),'La carpeta de OneDrive debe estar fuera de la carpeta del aplicativo.')
    webhook=str(payload.get('webhook_url','')).strip() or config.get('webhook_url','')
    valid_webhook(webhook)
    key=str(payload.get('api_key','')).strip() or config.get('api_key','')
    check(not key or (key.isascii() and all(32<=ord(c)<127 for c in key) and len(key)<=512),'La clave de Make debe ser ASCII sin saltos de línea (máximo 512 caracteres).')
    remote='/' + str(payload.get('remote_folder','/HIDRO-VISION/Informes enviados')).strip().strip('/')
    check(all(part not in ('.','..','') for part in remote[1:].split('/')) and not any(c in remote for c in ('\\',':','\n','\r')),'Indica la ruta de la carpeta dentro de OneDrive, usando / entre carpetas.')
    temporary=CONFIG.with_suffix('.tmp')
    temporary.write_text(json.dumps(dict(onedrive_folder=str(folder),remote_folder=remote,webhook_url=webhook,api_key=key),ensure_ascii=False,indent=2),encoding='utf8')
    os.replace(temporary,CONFIG)
    return settings()

def list_deliveries(comparison=None):
    init_db()
    with workflow.connect() as db:
        rows=[dict(r) for r in db.execute('SELECT id,report,comparison,file_name,state,detail,created,updated FROM report_deliveries'+
              (' WHERE comparison=?' if comparison else '')+' ORDER BY created DESC',(comparison,) if comparison else ())]
    for row in rows:row['label']=STATE_LABELS.get(row['state'],row['state'])
    return rows

def payload_for(report,snapshot,file_name,delivery_id,cloud_path):
    levels=snapshot['levels']
    intro=(f"Se comparte el informe ejecutivo de las inspecciones de {snapshot['project']}, correspondientes a "
           f"{' y '.join(snapshot['months'])}. Incluye evidencias y {snapshot['findings']} hallazgos revisados: "
           f"{levels['urgente']} urgentes, {levels['prioritaria']} prioritarios y {levels['seguimiento']} de seguimiento. "
           f"{snapshot['pending']} pendientes de verificación de campo. Se remite para revisión de jefatura y coordinación de acciones.")
    return dict(event='hidro_vision.executive_report_ready',schema_version=2,delivery_id=delivery_id,report_id=report['id'],
                comparison_id=report['comparison'],file_name=file_name,file_path=cloud_path,project=snapshot['project'],
                campaign_a=snapshot['months'][0],campaign_b=snapshot['months'][1],report_created=report['created'],
                findings=snapshot['findings'],urgent=levels['urgente'],priority=levels['prioritaria'],follow_up=levels['seguimiento'],
                pending_verification=snapshot['pending'],sha256=snapshot['pdf_sha256'],
                email_subject=f"HIDRO-VISION | Informe ejecutivo - {snapshot['project']} - {' / '.join(snapshot['months'])}",
                email_intro=intro)

def prepare(payload):
    report,snapshot,source=workflow.latest_report(payload.get('comparison'),payload.get('report_id'))
    config=read_config()
    check(config.get('onedrive_folder') and config.get('webhook_url'),'Configura primero OneDrive y Make.')
    destination=Path(config['onedrive_folder'])
    check(destination.is_dir(),'La carpeta de OneDrive ya no está disponible.')
    init_db()
    with workflow.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        prior=db.execute('SELECT * FROM report_deliveries WHERE report=?',(report['id'],)).fetchone()
        if prior:
            prior=dict(prior)
            check(prior['state']=='copied_to_onedrive','Este informe ya fue notificado o está en proceso. Revisa el seguimiento antes de repetirlo.')
            target=Path(prior['target'])
            check(target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==snapshot['pdf_sha256'],'El PDF preparado ya no coincide. Restáuralo desde el informe local antes de continuar.')
            return dict(**prior,label=STATE_LABELS[prior['state']],payload=payload_for(report,snapshot,prior['file_name'],prior['id'],prior['cloud_path']))
        ident=uuid.uuid4().hex
        file_name=f"HIDRO_VISION_{report['id']}.pdf"
        target=destination/file_name
        cloud_path=config.get('remote_folder','/HIDRO-VISION/Informes enviados')+'/'+file_name
        temporary=destination/(file_name+'.partial')
        try:
            shutil.copyfile(source,temporary)
            check(hashlib.sha256(temporary.read_bytes()).hexdigest()==snapshot['pdf_sha256'],'No se pudo verificar la copia del PDF.')
            os.replace(temporary,target)
        finally:temporary.unlink(missing_ok=True)
        stamp=workflow.now()
        db.execute('INSERT INTO report_deliveries VALUES(?,?,?,?,?,?,?,?,?,?)',
                   (ident,report['id'],report['comparison'],file_name,str(target),cloud_path,'copied_to_onedrive','Solo se copió el PDF; OneDrive debe terminar de sincronizarlo.',stamp,stamp))
    return dict(id=ident,report=report['id'],file_name=file_name,state='copied_to_onedrive',label=STATE_LABELS['copied_to_onedrive'],
                payload=payload_for(report,snapshot,file_name,ident,cloud_path))

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def notify_make(payload):
    check(payload.get('sync_confirmed') is True,'Confirma que el PDF ya aparece en OneDrive web antes de avisar a Make.')
    check(payload.get('scenario_confirmed') is True,'Confirma que Make ya busca el PDF recibido y usa el texto dinámico; no debe apuntar al archivo fijo de prueba.')
    report,snapshot,_=workflow.latest_report(payload.get('comparison'),payload.get('report_id'))
    init_db()
    with workflow.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM report_deliveries WHERE report=?',(report['id'],)).fetchone()
        check(row is not None,'Primero copia el último PDF a OneDrive.')
        row=dict(row)
        check(row['state'] in ('copied_to_onedrive','failed'),'Este informe ya fue notificado o está en curso. Revisa el historial de Make para evitar duplicados.')
        config=read_config()
        valid_webhook(config.get('webhook_url',''))
        target=Path(row['target'])
        check(target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest()==snapshot['pdf_sha256'],'El archivo de OneDrive no coincide con el informe; restaura la copia antes de enviar.')
        db.execute('UPDATE report_deliveries SET state=?,detail=?,updated=? WHERE id=?',('sending','Avisando a Make.',workflow.now(),row['id']))
    body=payload_for(report,snapshot,row['file_name'],row['id'],row['cloud_path'])
    headers={'Content-Type':'application/json','User-Agent':'HIDRO-VISION/2'}
    if config.get('api_key'):headers['x-make-apikey']=config['api_key']
    request=Request(config['webhook_url'],data=json.dumps(body,ensure_ascii=False).encode('utf8'),headers=headers,method='POST')
    state,detail='uncertain','Sin confirmación. Revisa el historial de Make antes de volver a enviar.'
    try:
        with build_opener(NoRedirect()).open(request,timeout=170) as response:
            raw=response.read(65536)
            try:answer=json.loads(raw)
            except (ValueError,UnicodeDecodeError):answer={}
            if isinstance(answer,dict) and answer.get('status')=='sent' and answer.get('report_id')==report['id']:
                state,detail='sent','Make confirmó el envío del correo. No confirma lectura ni entrega en la bandeja del destinatario.'
            elif isinstance(answer,dict) and answer.get('status')=='failed' and answer.get('report_id')==report['id']:
                state,detail='failed','Make informó un error previo al envío. Revisa el escenario antes de reintentar.'
            else:
                state,detail='make_received','Make recibió el aviso; revisa su historial para confirmar el envío del correo.'
    except HTTPError as exc:
        # Only explicit request rejection is safe to retry. Server errors can follow an email send.
        if exc.code in (400,401,403,404,405,410,413,415,422,429):
            state,detail='failed',f'Make rechazó la solicitud (HTTP {exc.code}). Revisa el webhook y el escenario.'
    except (OSError,socket.timeout):pass
    finally:
        with workflow.connect() as db:
            db.execute('UPDATE report_deliveries SET state=?,detail=?,updated=? WHERE id=?',(state,detail,workflow.now(),row['id']))
    return dict(id=row['id'],report=report['id'],state=state,label=STATE_LABELS[state],detail=detail)
