import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from core.glossary_manager import GlossaryManager


class CategoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.manager = GlossaryManager(str(Path(self.temp.name) / 'glossary.json'))

    def tearDown(self):
        self.temp.cleanup()

    def test_migration_keeps_terms_and_stable_ids(self):
        self.manager.reload({'terms_zh_to_en': {'张三': 'Zhang San'}, 'asr_fixes': {'章三': '张三'}}, persist=True)
        data = self.manager.to_dict()
        entry = data['entries'][0]
        self.assertEqual(entry['category_id'], 'uncategorized')
        reopened = GlossaryManager(self.manager.dict_path).to_dict()
        self.assertEqual(reopened['entries'][0]['id'], entry['id'])
        self.assertEqual(reopened['asr_fixes'], {'章三': '张三'})

    def test_disabled_category_and_entry_are_not_sent_to_cloud(self):
        self.manager.reload({'terms_zh_to_en': {'张三': 'Zhang San', '计划': 'Plan'}})
        data = self.manager.to_dict()
        data['categories'].append({'id':'meeting','name':'本次会议','enabled':False})
        data['entries'][0]['category_id'] = 'meeting'
        data['entries'][1]['enabled'] = False
        self.manager.reload(data)
        self.assertEqual(self.manager.get_cloud_phrases('en'), {})
        self.assertEqual(len(self.manager.to_dict()['entries']), 2)

    def test_deleted_category_moves_terms_without_deleting(self):
        self.manager.reload({'terms_zh_to_en': {'术语': 'Term'}})
        data = self.manager.to_dict()
        data['entries'][0]['category_id'] = 'people'
        self.manager.reload(data)
        data = self.manager.to_dict()
        data['categories'] = [c for c in data['categories'] if c['id'] != 'people']
        self.manager.reload(data)
        self.assertEqual(self.manager.to_dict()['entries'][0]['category_id'], 'uncategorized')
        self.assertEqual(self.manager.get_cloud_phrases('en'), {'术语':'Term'})

    def test_duplicate_translation_conflict_rejected(self):
        self.manager.reload({'terms_zh_to_en': {'术语': 'Term'}})
        data = self.manager.to_dict()
        data['entries'].append(dict(data['entries'][0], id='new', target='Other'))
        with self.assertRaises(ValueError):
            self.manager.reload(data)

    def test_disk_failure_keeps_previous_memory_and_cloud_terms(self):
        self.manager.reload({'terms_zh_to_en': {'旧': 'Old'}}, persist=True)
        previous = self.manager.to_dict()
        with patch('core.glossary_manager.os.replace', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.manager.reload({'terms_zh_to_en': {'新': 'New'}}, persist=True)
        self.assertEqual(self.manager.to_dict(), previous)
        self.assertEqual(self.manager.get_cloud_phrases('en'), {'旧': 'Old'})


if __name__ == '__main__':
    unittest.main()
