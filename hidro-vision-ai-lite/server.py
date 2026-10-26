"""Servidor local del visor. Ejecutar: python server.py"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
import json, threading, uuid, traceback, shutil
from processor import ROOT, STORE, load_campaign, compare
import platform_store as workflow
import weather_context
import report_delivery as delivery

JOBS = {}
BUSY = threading.Lock()

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT/'docs'), **kwargs)

    def translate_path(self, path):
        path = unquote(urlparse(path).path)
        if path.startswith('/data/'):
            resolved = (STORE / path[6:]).resolve()
            if not resolved.is_relative_to(STORE.resolve()): return str(STORE/'missing')
            return str(resolved)
        return super().translate_path(path)

    def send_json(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode('utf8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.headers.get('Host','').lower() not in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}:
            return self.send_json(403,{'error':'Accede desde la dirección local del aplicativo.'})
        route = urlparse(self.path).path
        if route == '/api/health':return self.send_json(200, {'ready':True})
        if route.startswith('/api/platform/'):
            try:
                query=parse_qs(urlparse(self.path).query)
                comparison=query.get('comparison',[None])[0]
                actions={
                    '/api/platform/weather':lambda:weather_context.context(comparison),
                    '/api/platform/campaigns':workflow.campaigns,
                    '/api/platform/comparisons':workflow.comparisons,
                    '/api/platform/findings':lambda:workflow.findings(comparison),
                    '/api/platform/deleted-findings':lambda:workflow.deleted_findings(comparison),
                    '/api/platform/model':workflow.model_status,
                    '/api/platform/training':workflow.training_export,
                    '/api/platform/alerts':workflow.alert_list,
                    '/api/platform/reports':lambda:workflow.report_list(comparison),
                    '/api/platform/delivery-settings':delivery.settings,
                    '/api/platform/deliveries':lambda:delivery.list_deliveries(comparison),
                }
                if route not in actions:return self.send_json(404,{'error':'Ruta no encontrada.'})
                return self.send_json(200,actions[route]())
            except Exception as e:return self.send_json(400,{'error':str(e)})
        if route.startswith('/api/job/'):
            job=JOBS.get(route.rsplit('/',1)[-1])
            return self.send_json(200 if job else 404, job or {'error':'Trabajo no encontrado.'})
        if route.startswith('/data/'):
            path=Path(self.translate_path(self.path))
            if not path.is_file():return self.send_error(404)
            size=path.stat().st_size
            start,end=0,size-1
            partial=False
            if self.headers.get('Range'):
                import re
                match=re.fullmatch(r'bytes=(\d+)-(\d*)',self.headers['Range'])
                if not match:return self.send_error(416)
                start=int(match[1]);end=min(int(match[2]) if match[2] else end,end)
                if start>end:return self.send_error(416)
                partial=True
            self.send_response(206 if partial else 200)
            self.send_header('Content-Type',self.guess_type(str(path)))
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"sandbox")
            if path.suffix.lower() not in {'.png','.jpg','.jpeg','.pdf','.mp4','.webm','.mov','.m4v','.json'}:
                self.send_header('Content-Disposition','attachment')
            self.send_header('Accept-Ranges','bytes')
            self.send_header('Content-Length',str(end-start+1))
            if partial:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
            self.end_headers()
            try:
                with path.open('rb') as f:
                    f.seek(start);remaining=end-start+1
                    while remaining>0:
                        buf=f.read(min(1024*1024,remaining))
                        if not buf:break
                        self.wfile.write(buf);remaining-=len(buf)
            except (ConnectionAbortedError,ConnectionResetError,BrokenPipeError):pass
            return
        super().do_GET()

    def do_POST(self):
        if self.headers.get('Host','').lower() not in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}:
            return self.send_json(403,{'error':'Accede desde la dirección local del aplicativo.'})
        origin=self.headers.get('Origin')
        if origin and origin != 'http://'+self.headers.get('Host',''):
            return self.send_json(403,{'error':'Solo se aceptan cargas desde este aplicativo local.'})
        if self.headers.get('X-Hidro-Client')!='local':return self.send_json(403,{'error':'Solicitud no permitida.'})
        parsed=urlparse(self.path)
        try:
            length=int(self.headers.get('Content-Length',0))
            if parsed.path.startswith('/api/platform/'):
                if not 0<length<=32768:raise ValueError('Tamaño de solicitud no válido.')
                payload=json.loads(self.rfile.read(length))
                actions={
                    '/api/platform/campaign':workflow.update_campaign,
                    '/api/platform/finding':workflow.save_finding,
                    '/api/platform/delete-finding':workflow.delete_finding,
                    '/api/platform/restore-finding':workflow.restore_finding,
                    '/api/platform/report':lambda p:workflow.make_report(p.get('comparison'),p.get('project')),
                    '/api/platform/alert':workflow.prepare_alert,
                    '/api/platform/delivery-settings':delivery.save_settings,
                    '/api/platform/prepare-report':delivery.prepare,
                    '/api/platform/send-report':delivery.notify_make,
                }
                if parsed.path not in actions:return self.send_json(404,{'error':'Ruta no encontrada.'})
                return self.send_json(200,actions[parsed.path](payload))
            if parsed.path=='/api/upload':
                if not 0<length<=30*1024**3:raise ValueError('El ZIP debe tener entre 1 byte y 30 GB.')
                name=parse_qs(parsed.query).get('name',['campaña.zip'])[0]
                if not name.lower().endswith('.zip'):raise ValueError('Selecciona un archivo ZIP.')
                temp=STORE/(uuid.uuid4().hex+'.zip')
                try:
                    with temp.open('wb') as f:
                        remaining=length
                        while remaining:
                            chunk=self.rfile.read(min(1024*1024,remaining))
                            if not chunk:raise ValueError('La carga se interrumpió.')
                            f.write(chunk);remaining-=len(chunk)
                    data=load_campaign(temp,name)
                finally:temp.unlink(missing_ok=True)
                return self.send_json(200,data)
            if parsed.path=='/api/compare':
                if length>4096:raise ValueError('Solicitud demasiado grande.')
                payload=json.loads(self.rfile.read(length))
                if not BUSY.acquire(blocking=False):return self.send_json(409,{'error':'Hay una comparación en curso.'})
                ident=uuid.uuid4().hex
                JOBS[ident]={'state':'running','message':'Procesando ortofotos, alineamiento y fotogramas…'}
                def work():
                    try:JOBS[ident]={'state':'done','result':compare(payload['ids'])}
                    except Exception as e:
                        traceback.print_exc()
                        JOBS[ident]={'state':'error','error':str(e)}
                    finally:BUSY.release()
                threading.Thread(target=work,daemon=True).start()
                return self.send_json(202,{'job':ident})
            return self.send_json(404,{'error':'Ruta no encontrada.'})
        except Exception as e:
            traceback.print_exc()
            return self.send_json(400,{'error':str(e)})

if __name__=='__main__':
    print('HIDRO-VISION AI: http://127.0.0.1:8765',flush=True)
    ThreadingHTTPServer(('127.0.0.1',8765),Handler).serve_forever()
