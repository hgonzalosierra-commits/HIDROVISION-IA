import unittest, tempfile, json
from pathlib import Path
import processor as p
import platform_store as workflow
import test_comparison as fixtures

class PlatformTest(unittest.TestCase):
    def setUp(self):
        qa=p.ROOT/'.qa';qa.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=qa)
        self.old=(p.STORE,workflow.STORE,workflow.DB)
        p.STORE=workflow.STORE=Path(self.tmp.name)/'store';p.STORE.mkdir()
        workflow.DB=p.STORE/'platform.sqlite3'
        fixture=fixtures.ComparisonTest();fixture.tmp=self.tmp
        a=fixture.campaign('Enero_2026');b=fixture.campaign('Julio_2026',120)
        self.ids=[a['id'],b['id']]
        self.result=p.compare(self.ids)
        self.comparison=self.result['download'].split('/')[2]

    def tearDown(self):
        p.STORE,workflow.STORE,workflow.DB=self.old
        self.tmp.cleanup()

    def payload(self):
        return dict(comparison=self.comparison,station=100,category='agua',level='prioritaria',evidence='El canal mojado aparece más estrecho en la segunda imagen.',rationale='Se requiere contrastar el nivel del agua en las dos fechas.',reviewer='Revisor de prueba',verified=False)

    def test_history_review_and_training(self):
        self.assertEqual(len(workflow.campaigns()),2)
        workflow.update_campaign(dict(id=self.ids[0],month=1,year=2026))
        row=workflow.save_finding(self.payload())
        self.assertEqual(len(workflow.findings(self.comparison)),1)
        self.assertFalse(workflow.model_status()['trained'])
        update={**self.payload(),'id':row['id'],'verified':True,'level':'seguimiento'}
        workflow.save_finding(update)
        status=workflow.model_status()
        self.assertEqual(status['revisions'],2)
        self.assertEqual(status['verified'],1)
        self.assertEqual(len(workflow.training_export()['examples']),1)

    def test_validation_and_outbox_no_send(self):
        invalid=self.payload();invalid['station']=99999
        with self.assertRaisesRegex(ValueError,'progresiva'):workflow.save_finding(invalid)
        invalid=self.payload();invalid['rationale']=''
        with self.assertRaisesRegex(ValueError,'motivo'):workflow.save_finding(invalid)
        row=workflow.save_finding(self.payload())
        alert=workflow.prepare_alert({'finding':row['id']})
        self.assertEqual(alert['state'],'prepared_not_sent')
        self.assertEqual(workflow.alert_list()[0]['finding'],row['id'])

    def test_pdf_includes_review_and_evidence(self):
        from pypdf import PdfReader
        row=workflow.save_finding(self.payload())
        report=workflow.make_report(self.comparison)
        reader=PdfReader(p.STORE/report['url'].removeprefix('/data/'))
        text='\n'.join(page.extract_text() for page in reader.pages)
        self.assertIn('Revisor de prueba',text)
        self.assertIn('El canal mojado',text)
        self.assertGreaterEqual(len(reader.pages),2)
        self.assertEqual(len(workflow.report_list(self.comparison)),1)

if __name__=='__main__':unittest.main()
