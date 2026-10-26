import unittest
import json
import platform_store as workflow
import test_platform as fixtures


class FindingArchiveTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.PlatformTest();self.fixture.setUp()
        self.comparison=self.fixture.comparison
        self.row=workflow.save_finding(self.fixture.payload())

    def tearDown(self):self.fixture.tearDown()

    def test_delete_and_restore_preserve_evidence_and_audit(self):
        workflow.delete_finding(dict(comparison=self.comparison,id=self.row['id'],expected_updated=self.row['updated']))
        self.assertEqual(workflow.findings(self.comparison),[])
        deleted=workflow.deleted_findings(self.comparison)
        self.assertEqual(deleted[0]['evidence'],self.row['evidence'])
        self.assertEqual(len(workflow.training_export()['examples']),0)
        workflow.restore_finding(dict(comparison=self.comparison,id=self.row['id']))
        restored=workflow.findings(self.comparison)[0]
        self.assertEqual(restored['id'],self.row['id'])
        self.assertEqual(restored['rationale'],self.row['rationale'])
        self.assertEqual(restored['created'],self.row['created'])
        self.assertEqual(workflow.deleted_findings(self.comparison),[])
        with workflow.connect() as db:
            actions=[json.loads(r[0]).get('action') for r in db.execute('SELECT record FROM reviews WHERE finding=? ORDER BY created',(self.row['id'],))]
        self.assertEqual(actions,[None,'deleted','restored'])

    def test_old_report_stays_on_disk_but_is_stale(self):
        report=workflow.make_report(self.comparison,'Dique de prueba')
        from pathlib import Path
        path=workflow.STORE/report['url'].removeprefix('/data/')
        original=path.read_bytes()
        workflow.delete_finding(dict(comparison=self.comparison,id=self.row['id']))
        self.assertTrue(workflow.report_list(self.comparison)[0]['stale'])
        with self.assertRaisesRegex(ValueError,'cambios posteriores'):workflow.latest_report(self.comparison)
        self.assertEqual(path.read_bytes(),original)
        current=workflow.make_report(self.comparison,'Dique de prueba')
        self.assertEqual(current['findings'],0)

    def test_old_editor_cannot_resurrect_deleted_record(self):
        workflow.delete_finding(dict(comparison=self.comparison,id=self.row['id']))
        with self.assertRaisesRegex(ValueError,'ya no está activo'):
            workflow.save_finding({**self.fixture.payload(),'id':self.row['id']})
        with self.assertRaises(ValueError):workflow.delete_finding(dict(comparison=self.comparison,id=self.row['id']))
        self.assertEqual(workflow.findings(self.comparison),[])
        self.assertEqual(len(workflow.deleted_findings(self.comparison)),1)

    def test_newer_edits_and_other_comparisons_cannot_be_deleted(self):
        with self.assertRaisesRegex(ValueError,'corregido'):
            workflow.delete_finding(dict(comparison=self.comparison,id=self.row['id'],expected_updated='old'))
        with self.assertRaises(ValueError):workflow.delete_finding(dict(comparison='b'*32,id=self.row['id']))
        self.assertEqual(len(workflow.findings(self.comparison)),1)


if __name__=='__main__':unittest.main()
