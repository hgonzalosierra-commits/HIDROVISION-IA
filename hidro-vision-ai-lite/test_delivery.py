import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import processor as p
import platform_store as workflow
import report_delivery as delivery


class DeliveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.previous=(p.STORE,workflow.STORE,workflow.DB,delivery.CONFIG)
        p.STORE=workflow.STORE=root/'store';p.STORE.mkdir()
        workflow.DB=p.STORE/'platform.sqlite3';delivery.CONFIG=root/'integration_config.json'
        self.cloud=root/'OneDrive'/'HIDRO-VISION'/'Informes enviados';self.cloud.mkdir(parents=True)
        self.comparison='a'*32
        folder=p.STORE/self.comparison;folder.mkdir()
        from PIL import Image
        Image.new('RGB',(320,180),(40,100,140)).save(folder/'evidence.jpg')
        ref=dict(station=100,images=[dict(url=p.public(folder/'evidence.jpg'),coverage=100)]*2,
                 videos=[dict(url=p.public(folder/'evidence.jpg'),time=12.5,station=100)]*2)
        result=dict(months=[dict(name='ENERO_2026'),dict(name='JULIO_2026')],crs='EPSG:32718',start=0,end=100,references=[ref],warnings=[])
        (folder/'result.json').write_text(json.dumps(result),encoding='utf8')
        self.finding=dict(comparison=self.comparison,station=100,category='grietas',level='urgente',evidence='Grietas observadas en la estructura durante la revisión.',rationale='Coordinar una verificación de campo con el responsable técnico.',reviewer='Revisor de prueba',verified=False)
        workflow.save_finding(self.finding)
        self.report=workflow.make_report(self.comparison,'Dique - Tramo 03')
        delivery.save_settings(dict(onedrive_folder=str(self.cloud),webhook_url='https://hook.us1.make.com/test-only-never-contact'))

    def tearDown(self):
        p.STORE,workflow.STORE,workflow.DB,delivery.CONFIG=self.previous
        self.tmp.cleanup()

    def request(self):
        return dict(comparison=self.comparison,report_id=self.report['id'],sync_confirmed=True,scenario_confirmed=True)

    def test_prepare_only_latest_pdf_and_keep_source(self):
        staged=delivery.prepare(self.request())
        files=list(self.cloud.iterdir())
        self.assertEqual(len(files),1)
        self.assertEqual(files[0].suffix,'.pdf')
        self.assertEqual(hashlib.sha256(files[0].read_bytes()).hexdigest(),staged['payload']['sha256'])
        self.assertEqual(staged['payload']['file_path'],'/HIDRO-VISION/Informes enviados/'+files[0].name)
        self.assertIn('Dique - Tramo 03',staged['payload']['email_intro'])
        self.assertEqual(staged['payload']['urgent'],1)
        again=delivery.prepare(self.request())
        self.assertEqual(staged['id'],again['id'])
        self.assertTrue((p.STORE/self.report['url'].removeprefix('/data/')).is_file())

    def test_stale_report_and_old_selected_report_are_rejected(self):
        record=workflow.findings(self.comparison)[0]
        workflow.save_finding({**self.finding,'id':record['id'],'verified':True})
        with self.assertRaisesRegex(ValueError,'cambios posteriores'):delivery.prepare(self.request())
        newer=workflow.make_report(self.comparison,'Dique - Tramo 03')
        with self.assertRaisesRegex(ValueError,'último informe cambió'):delivery.prepare(self.request())
        self.report=newer
        delivery.prepare(self.request())

    def test_changed_pdf_is_rejected(self):
        path=p.STORE/self.report['url'].removeprefix('/data/')
        path.write_bytes(path.read_bytes()+b'changed')
        with self.assertRaisesRegex(ValueError,'PDF cambió'):delivery.prepare(self.request())

    def test_received_is_not_sent_and_duplicate_is_blocked(self):
        delivery.prepare(self.request())
        with patch.object(delivery,'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=b'Accepted'
            answer=delivery.notify_make(self.request())
            self.assertEqual(answer['state'],'make_received')
            with self.assertRaisesRegex(ValueError,'ya fue notificado'):delivery.notify_make(self.request())
            self.assertEqual(opener.return_value.open.call_count,1)

    def test_sent_requires_matching_confirmation(self):
        delivery.prepare(self.request())
        with patch.object(delivery,'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value=json.dumps(dict(status='sent',report_id=self.report['id'])).encode()
            self.assertEqual(delivery.notify_make(self.request())['state'],'sent')

    def test_timeout_does_not_retry_or_mark_sent(self):
        delivery.prepare(self.request())
        with patch.object(delivery,'build_opener') as opener:
            opener.return_value.open.side_effect=TimeoutError()
            self.assertEqual(delivery.notify_make(self.request())['state'],'uncertain')
            with self.assertRaises(ValueError):delivery.notify_make(self.request())
            self.assertEqual(opener.return_value.open.call_count,1)

    def test_concurrent_send_is_blocked(self):
        delivery.prepare(self.request())
        started,release=threading.Event(),threading.Event()
        def wait_response(*args,**kwargs):
            started.set();release.wait(5)
            raise TimeoutError()
        with patch.object(delivery,'build_opener') as opener:
            opener.return_value.open.side_effect=wait_response
            thread=threading.Thread(target=delivery.notify_make,args=(self.request(),))
            thread.start();self.assertTrue(started.wait(5))
            try:
                with self.assertRaisesRegex(ValueError,'en curso'):delivery.notify_make(self.request())
            finally:release.set();thread.join(5)
            self.assertEqual(opener.return_value.open.call_count,1)

    def test_settings_redact_secret_and_validate_destination(self):
        self.assertNotIn('webhook_url',delivery.settings())
        self.assertNotIn('api_key',delivery.settings())
        with self.assertRaises(ValueError):delivery.save_settings(dict(onedrive_folder=str(self.cloud),webhook_url='http://localhost:8765/api/platform/report'))
        with self.assertRaises(ValueError):delivery.valid_webhook('https://hook.make.com/test?prueba=1')
        delivery.prepare(self.request())
        with self.assertRaisesRegex(ValueError,'sincronización|OneDrive web'):delivery.notify_make({**self.request(),'sync_confirmed':False})
        with self.assertRaisesRegex(ValueError,'Make ya'):delivery.notify_make({**self.request(),'scenario_confirmed':False})

    def test_empty_report_does_not_claim_safety(self):
        from pypdf import PdfReader
        with workflow.connect() as db:db.execute('DELETE FROM findings')
        report=workflow.make_report(self.comparison,'Sin revisión')
        reader=PdfReader(p.STORE/report['url'].removeprefix('/data/'))
        text='\n'.join(page.extract_text() for page in reader.pages)
        self.assertEqual(len(reader.pages),1)
        self.assertIn('no certifica ausencia',text)

    def test_three_color_report_and_long_text(self):
        from pypdf import PdfReader
        original=workflow.findings(self.comparison)[0]
        for level in ['prioritaria','seguimiento']:
            workflow.save_finding({**self.finding,'id':None,'level':level,'evidence':'Evidencia revisada. '*180,'rationale':'Motivo registrado. '*180})
        report=workflow.make_report(self.comparison,'Dique - Tramo 03')
        reader=PdfReader(p.STORE/report['url'].removeprefix('/data/'))
        self.assertEqual(len(reader.pages),4)
        text='\n'.join(page.extract_text() for page in reader.pages)
        self.assertIn('INFORME EJECUTIVO',text)
        self.assertIn('Alerta urgente',text)
        self.assertIn('Inspección prioritaria',text)
        self.assertIn('Seguimiento',text)


if __name__=='__main__':unittest.main()
