import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.evaluation import router


class ReportApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patch = patch('app.evaluation.REPORTS', self.root)
        self.patch.start()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def test_list_skips_nonreports_and_detail_preserves_all_data(self):
        report = {'results': [{'question': '<script>alert(1)</script>', 'actual': {'trace': []}}],
                  'summary': {'total': 1}, 'judge_model': 'test'}
        (self.root/'run.json').write_text(json.dumps(report))
        (self.root/'input.json').write_text('[]')
        (self.root/'broken.json').write_text('{')
        self.assertEqual([r['name'] for r in self.client.get('/api/evaluations').json()['reports']], ['run.json'])
        self.assertEqual(self.client.get('/api/evaluations/run.json').json(), report)

    def test_missing_invalid_and_symlink_reports(self):
        (self.root/'invalid.json').write_text('[]')
        (self.root/'link.json').symlink_to(self.root/'invalid.json')
        self.assertEqual(self.client.get('/api/evaluations/missing.json').status_code, 404)
        self.assertEqual(self.client.get('/api/evaluations/invalid.json').status_code, 422)
        self.assertEqual(self.client.get('/api/evaluations/link.json').status_code, 404)
        self.assertEqual(self.client.get('/api/evaluations').json(), {'reports': []})
