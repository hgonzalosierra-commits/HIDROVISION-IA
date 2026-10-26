"""Persistent workflow: campaigns, reviewed findings, reports and alert outbox.

No external service is called by this module. Criticality is assigned by a
named reviewer, never inferred from the RGB difference threshold.
"""
from pathlib import Path
import sqlite3, json, re, uuid, hashlib
from datetime import datetime, timezone
from contextlib import contextmanager
from processor import STORE, read_campaign, check, public

DB = STORE / 'platform.sqlite3'
TYPES = {
    'enrocado': 'Posible desplazamiento del enrocado',
    'erosion': 'Posible erosión del talud',
    'colmatacion': 'Posible colmatación',
    'deformacion': 'Posible asentamiento o deformación',
    'grietas': 'Posibles grietas',
    'agua': 'Menor superficie de agua visible',
    'vegetacion': 'Mayor cobertura vegetal visible',
    'dragado': 'Indicios de intervención / posible dragado',
    'pie': 'Revisar el pie del dique',
    'sin_cambio': 'Sin cambio relevante',
}
LEVELS = {'seguimiento':'Seguimiento', 'prioritaria':'Inspección prioritaria', 'urgente':'Alerta urgente'}

def now():
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def connect():
    db=sqlite3.connect(DB, timeout=30)
    db.row_factory=sqlite3.Row
    db.executescript('''
    CREATE TABLE IF NOT EXISTS campaigns(id TEXT PRIMARY KEY, month INTEGER, year INTEGER, name TEXT NOT NULL, created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS findings(id TEXT PRIMARY KEY, comparison TEXT NOT NULL, station REAL NOT NULL, category TEXT NOT NULL, level TEXT NOT NULL, evidence TEXT NOT NULL, rationale TEXT NOT NULL, reviewer TEXT NOT NULL, verified INTEGER NOT NULL, created TEXT NOT NULL, updated TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS deleted_findings(id TEXT PRIMARY KEY, comparison TEXT NOT NULL, record TEXT NOT NULL, deleted TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS reviews(id TEXT PRIMARY KEY, finding TEXT NOT NULL, record TEXT NOT NULL, created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, comparison TEXT NOT NULL, url TEXT NOT NULL, created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS report_snapshots(report TEXT PRIMARY KEY, snapshot TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS alerts(id TEXT PRIMARY KEY, finding TEXT NOT NULL, payload TEXT NOT NULL, state TEXT NOT NULL, created TEXT NOT NULL);
    ''')
    try:
        with db:
            yield db
    finally:
        db.close()

def result_path(ident):
    check(isinstance(ident,str) and bool(re.fullmatch('[a-f0-9]{32}',ident)), 'Comparación no válida.')
    p=STORE/ident/'result.json'
    check(p.is_file(), 'No se encontró la comparación.')
    return p

def read_result(ident):
    return json.loads(result_path(ident).read_text(encoding='utf8'))

def station_ref(result, station):
    check(isinstance(station,(float,int)), 'Progresiva no válida.')
    ref=next((r for r in result['references'] if abs(r['station']-station)<.001),None)
    check(ref is not None, 'La progresiva no pertenece a esta comparación.')
    return ref

def sync_campaigns():
    months=['enero','febrero','marzo','abril','mayo','junio','julio','agosto','septiembre','octubre','noviembre','diciembre']
    with connect() as db:
        for p in STORE.glob('*/campaign.json'):
            c=json.loads(p.read_text(encoding='utf8'))
            if c['name'].upper().startswith('PRUEBA'):continue
            month=next((i+1 for i,m in enumerate(months) if m in c['name'].lower()),None)
            year=re.search(r'20\d{2}',c['name'])
            db.execute('INSERT OR IGNORE INTO campaigns VALUES(?,?,?,?,?)',
                       (c['id'],month,int(year[0]) if year else None,c['name'],datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat()))

def campaigns():
    sync_campaigns()
    with connect() as db:rows=[dict(r) for r in db.execute('SELECT * FROM campaigns ORDER BY year DESC,month DESC,created DESC')]
    output=[]
    for row in rows:
        try:c=read_campaign(row['id'])
        except (OSError,ValueError):continue
        row.update(crs=c['crs'],files={'VIDEO':2,'ORTOFOTO':1,'XML':1,'PLANO_OTROS':len(c['plans'])})
        output.append(row)
    return output

def update_campaign(payload):
    ident=payload.get('id');c=read_campaign(ident)
    month,year=int(payload.get('month',0)),int(payload.get('year',0))
    check(1<=month<=12 and 2000<=year<=2100,'Indica un mes y año válidos.')
    sync_campaigns()
    with connect() as db:db.execute('UPDATE campaigns SET month=?,year=? WHERE id=?',(month,year,ident))
    return {'id':ident,'month':month,'year':year,'name':c['name']}

def comparisons():
    rows=[]
    for p in STORE.glob('*/result.json'):
        r=json.loads(p.read_text(encoding='utf8'))
        if any(m['name'].upper().startswith('PRUEBA') for m in r['months']):continue
        ids=[m['video'].split('/')[2] for m in r['months']]
        rows.append(dict(id=p.parent.name,ids=ids,months=[m['name'] for m in r['months']],url=public(p),created=datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat()))
    return sorted(rows,key=lambda r:r['created'],reverse=True)

def findings(comparison=None):
    with connect() as db:
        query='SELECT * FROM findings'+(' WHERE comparison=?' if comparison else '')+' ORDER BY updated DESC'
        return [dict(r) for r in db.execute(query,(comparison,) if comparison else ())]

def save_finding(payload):
    result=read_result(payload.get('comparison'))
    ref=station_ref(result,payload.get('station'))
    category=payload.get('category');level=payload.get('level')
    check(category in TYPES,'Categoría de hallazgo no válida.')
    check(level in LEVELS,'Nivel de atención no válido.')
    evidence=str(payload.get('evidence','')).strip()
    rationale=str(payload.get('rationale','')).strip()
    reviewer=str(payload.get('reviewer','')).strip()
    check(10<=len(evidence)<=4000,'Describe la evidencia (entre 10 y 4000 caracteres).')
    check(10<=len(rationale)<=4000,'Explica el motivo del nivel de atención (entre 10 y 4000 caracteres).')
    check(2<=len(reviewer)<=150,'Indica quién revisa el hallazgo.')
    check(any(i.get('coverage',0)>0 for i in ref['images']) or any(v.get('url') for v in ref['videos']), 'La progresiva no dispone de imágenes válidas.')
    ident=payload.get('id') or uuid.uuid4().hex
    check(bool(re.fullmatch('[a-f0-9]{32}',ident)),'Identificador no válido.')
    verified=bool(payload.get('verified',False))
    stamp=now()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        prior=db.execute('SELECT * FROM findings WHERE id=?',(ident,)).fetchone()
        if payload.get('id'):check(prior is not None,'El hallazgo ya no está activo. Actualiza la vista o restáuralo desde Hallazgos eliminados.')
        if prior:check(prior['comparison']==payload['comparison'] and abs(prior['station']-ref['station'])<.001,'No se puede reasignar un hallazgo a otra evidencia.')
        created=prior['created'] if prior else stamp
        record=dict(id=ident,comparison=payload['comparison'],station=ref['station'],category=category,level=level,evidence=evidence,rationale=rationale,reviewer=reviewer,verified=int(verified),created=created,updated=stamp)
        db.execute('INSERT OR REPLACE INTO findings VALUES(?,?,?,?,?,?,?,?,?,?,?)',tuple(record.values()))
        db.execute('INSERT INTO reviews VALUES(?,?,?,?)',(uuid.uuid4().hex,ident,json.dumps(record,ensure_ascii=False),stamp))
    return record

def deleted_findings(comparison):
    read_result(comparison)
    with connect() as db:
        rows=db.execute('SELECT record,deleted FROM deleted_findings WHERE comparison=? ORDER BY deleted DESC',(comparison,)).fetchall()
    return [{**json.loads(row['record']),'deleted':row['deleted']} for row in rows]

def delete_finding(payload):
    comparison=payload.get('comparison');read_result(comparison)
    ident=payload.get('id')
    check(isinstance(ident,str) and bool(re.fullmatch('[a-f0-9]{32}',ident)),'Hallazgo no válido.')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM findings WHERE id=? AND comparison=?',(ident,comparison)).fetchone()
        check(row is not None,'El hallazgo ya no está activo en esta comparación. Actualiza la vista.')
        record=dict(row)
        check(not payload.get('expected_updated') or record['updated']==payload['expected_updated'],'El hallazgo fue corregido después de abrir esta vista. Actualiza antes de eliminarlo.')
        stamp=now()
        db.execute('INSERT INTO deleted_findings VALUES(?,?,?,?)',(ident,comparison,json.dumps(record,ensure_ascii=False),stamp))
        db.execute('DELETE FROM findings WHERE id=?',(ident,))
        db.execute('INSERT INTO reviews VALUES(?,?,?,?)',(uuid.uuid4().hex,ident,json.dumps(dict(action='deleted',finding=record),ensure_ascii=False),stamp))
    return dict(id=ident,state='deleted',comparison=comparison)

def restore_finding(payload):
    comparison=payload.get('comparison');read_result(comparison)
    ident=payload.get('id')
    check(isinstance(ident,str) and bool(re.fullmatch('[a-f0-9]{32}',ident)),'Hallazgo no válido.')
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT record FROM deleted_findings WHERE id=? AND comparison=?',(ident,comparison)).fetchone()
        check(row is not None,'El hallazgo no está en la lista de eliminados de esta comparación.')
        record=json.loads(row['record']);stamp=now();record['updated']=stamp
        fields=('id','comparison','station','category','level','evidence','rationale','reviewer','verified','created','updated')
        db.execute('INSERT INTO findings VALUES(?,?,?,?,?,?,?,?,?,?,?)',tuple(record[key] for key in fields))
        db.execute('DELETE FROM deleted_findings WHERE id=?',(ident,))
        db.execute('INSERT INTO reviews VALUES(?,?,?,?)',(uuid.uuid4().hex,ident,json.dumps(dict(action='restored',finding=record),ensure_ascii=False),stamp))
    return dict(id=ident,state='restored',comparison=comparison)

def model_status():
    rows=findings()
    counts={k:sum(r['category']==k and r['verified'] for r in rows) for k in TYPES}
    with connect() as db:revisions=db.execute('SELECT COUNT(*) FROM reviews').fetchone()[0]
    return dict(mode='collecting_reviewed_examples',trained=False,findings=len(rows),verified=sum(bool(r['verified']) for r in rows),revisions=revisions,by_category=counts,
                message='Banco de ejemplos supervisados. Aún no hay un modelo de anomalías entrenado ni precisión validada.')

def training_export():
    rows=[]
    for finding in findings():
        result=read_result(finding['comparison']);ref=station_ref(result,finding['station'])
        rows.append(dict(**finding,months=result['months'],images=ref['images'],videos=ref['videos'],crs=result['crs']))
    return {'schema':'hidro-vision-training-v1','exported_at':now(),'examples':rows,'note':'Etiquetas humanas; separar campañas y ubicaciones entre entrenamiento y evaluación. No son predicciones de un modelo.'}

def prepare_alert(payload):
    with connect() as db:
        row=db.execute('SELECT * FROM findings WHERE id=?',(payload.get('finding'),)).fetchone()
        check(row is not None,'Hallazgo no encontrado.')
        finding=dict(row)
        result=read_result(finding['comparison'])
        body=dict(event='hidro_vision.reviewed_finding',schema_version=1,finding=finding,
                  category=TYPES[finding['category']],attention=LEVELS[finding['level']],
                  months=[m['name'] for m in result['months']],
                  report_url=payload.get('report_url'),
                  delivery_note='Preparado localmente. Enviar requiere Make y destinatarios configurados. Las rutas locales no son accesibles desde Make.')
        ident=uuid.uuid4().hex
        db.execute('INSERT INTO alerts VALUES(?,?,?,?,?)',(ident,finding['id'],json.dumps(body,ensure_ascii=False),'prepared_not_sent',now()))
    return dict(id=ident,state='prepared_not_sent',payload=body)

def alert_list():
    with connect() as db:return [dict(r) for r in db.execute('SELECT id,finding,state,created FROM alerts ORDER BY created DESC')]


def source_fingerprint(result, rows):
    material=json.dumps({'result':result,'findings':sorted(rows,key=lambda r:r['id'])},sort_keys=True,ensure_ascii=False)
    return hashlib.sha256(material.encode('utf8')).hexdigest()

def report_list(comparison):
    with connect() as db:
        rows=[dict(r) for r in db.execute('SELECT r.*,s.snapshot FROM reports r LEFT JOIN report_snapshots s ON s.report=r.id WHERE comparison=? ORDER BY created DESC,id DESC',(comparison,))]
    if not rows:return []
    current=source_fingerprint(read_result(comparison),findings(comparison))
    for row in rows:
        snapshot=json.loads(row.pop('snapshot') or '{}')
        row.update(executive=bool(snapshot),project=snapshot.get('project',''),stale=snapshot.get('source_fingerprint')!=current)
    return rows

def latest_report(comparison, expected=None):
    read_result(comparison)
    with connect() as db:
        row=db.execute('SELECT r.*,s.snapshot FROM reports r LEFT JOIN report_snapshots s ON s.report=r.id WHERE comparison=? ORDER BY created DESC,id DESC LIMIT 1',(comparison,)).fetchone()
    check(row is not None,'Genera primero el informe ejecutivo de esta comparación.')
    report=dict(row)
    check(expected is None or report['id']==expected,'El último informe cambió. Actualiza la vista antes de continuar.')
    snapshot=json.loads(report.pop('snapshot') or '{}')
    check(snapshot,'Genera un nuevo informe ejecutivo; el informe anterior usa la plantilla antigua.')
    check(snapshot['source_fingerprint']==source_fingerprint(read_result(comparison),findings(comparison)),'Hay cambios posteriores al informe. Genera un nuevo PDF antes de enviarlo.')
    path=(STORE/report['url'].removeprefix('/data/')).resolve()
    check(path.is_relative_to(STORE.resolve()) and path.is_file(),'No se encontró el PDF local del informe.')
    check(hashlib.sha256(path.read_bytes()).hexdigest()==snapshot['pdf_sha256'],'El PDF cambió después de generarse. Genera un nuevo informe.')
    return report,snapshot,path

def make_report(comparison, project=None):
    from executive_report import build_pdf
    result=read_result(comparison)
    rows=findings(comparison)
    if project is None:
        previous=report_list(comparison)
        project=previous[0]['project'] if previous and previous[0]['project'] else 'Dique / tramo en revisión'
    project=str(project).strip()
    check(3<=len(project)<=150,'Indica el nombre del dique o tramo (3 a 150 caracteres).')
    ident=uuid.uuid4().hex
    folder=STORE/comparison/'reports';folder.mkdir(exist_ok=True)
    target=folder/(ident+'.pdf')
    created=now()
    build_pdf(target,result,rows,{'project':project},created,TYPES,STORE)
    snapshot=dict(project=project,source_fingerprint=source_fingerprint(result,rows),pdf_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                  months=[m['name'].replace('_',' ') for m in result['months']],findings=len(rows),
                  levels={k:sum(r['level']==k for r in rows) for k in LEVELS},pending=sum(not r['verified'] for r in rows))
    url=public(target)
    with connect() as db:
        db.execute('INSERT INTO reports VALUES(?,?,?,?)',(ident,comparison,url,created))
        db.execute('INSERT INTO report_snapshots VALUES(?,?)',(ident,json.dumps(snapshot,ensure_ascii=False)))
    return dict(id=ident,url=url,mode='executive_template',findings=len(rows),project=project)
