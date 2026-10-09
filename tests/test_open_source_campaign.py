"""No-network, synthetic tests for the campaign contract."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'tools/validate_open_source_campaign.py'
spec = importlib.util.spec_from_file_location('campaign_validator', SOURCE)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


def fixtures(last=56):
    children = []
    lines = ['| PR | Encargo |', '| --- | --- |']
    for n in range(11, last + 1):
        title = f'Tarea {n}'
        lines.append(f'| [#{n}](https://github.com/davidpd89/ci-sandbox-tmp/pull/{n}) | {title} |')
        children.append({'number': n, 'title': title, 'objective': title, 'state': 'open',
                         'base': v.PARENT, 'head': f'research/{n-10:02}-task',
                         'head_sha': 'a' * 40, 'area': 'quality', 'related_prs': [],
                         'url': f'https://github.com/{v.REPO}/pull/{n}'})
    doc = {'schema_version': 1, 'repository': v.REPO, 'parent_pr': 10,
           'parent_head': v.PARENT, 'children': children}
    return doc, '\n'.join(lines)


class CampaignMetadataTests(unittest.TestCase):
    def setUp(self):
        self.doc, self.protocol = fixtures()

    def test_valid_snapshot(self):
        self.assertEqual(v.check_metadata(self.doc, self.protocol), [])

    def test_contiguous_extension_preserves_initial_wave(self):
        doc, protocol = fixtures(last=86)
        self.assertEqual(v.check_metadata(doc, protocol), [])

    def test_extension_gap_fails(self):
        doc, protocol = fixtures(last=86)
        doc['children'] = [p for p in doc['children'] if p['number'] != 57]
        self.assertTrue(v.check_metadata(doc, protocol))

    def test_extension_duplicate_fails(self):
        doc, protocol = fixtures(last=86)
        doc['children'][-1]['number'] = 85
        self.assertTrue(v.check_metadata(doc, protocol))

    def test_missing_child(self):
        self.doc['children'].pop()
        self.assertTrue(v.check_metadata(self.doc, self.protocol))

    def test_missing_index(self):
        self.protocol = self.protocol.replace('| [#11]', '| [#99]')
        self.assertIn('protocol index is incomplete or duplicated', v.check_metadata(self.doc, self.protocol))

    def test_duplicate_child(self):
        self.doc['children'][1] = copy.deepcopy(self.doc['children'][0])
        self.assertTrue(v.check_metadata(self.doc, self.protocol))

    def test_wrong_url(self):
        self.doc['children'][0]['url'] += '-fake'
        self.assertTrue(any('link' in e for e in v.check_metadata(self.doc, self.protocol)))

    def test_wrong_index_url(self):
        self.protocol = self.protocol.replace('/pull/11)', '/pull/999)')
        self.assertTrue(any('link' in e for e in v.check_metadata(self.doc, self.protocol)))

    def test_bad_head_or_base(self):
        self.doc['children'][0]['base'] = 'main'
        self.doc['children'][1]['head'] = 'main'
        self.assertTrue(len(v.check_metadata(self.doc, self.protocol)) >= 2)

    def test_duplicate_objective_and_related(self):
        self.doc['children'][1]['objective'] = 'Tarea 11'
        self.doc['children'][1]['related_prs'] = [12]
        self.assertTrue(len(v.check_metadata(self.doc, self.protocol)) >= 2)

    def test_live_pagination_keeps_page_size_stable(self):
        urls = []
        def opener(req, timeout):
            urls.append(req.full_url)
            page = 1 if req.full_url.endswith('page=1') else 2
            start = 1 if page == 1 else 101
            count = 100 if page == 1 else 1
            return io.BytesIO(json.dumps([{'number': n} for n in range(start, start + count)]).encode())
        loaded = v.fetch_live(opener=opener)
        self.assertEqual(len(loaded), 101)
        self.assertEqual(len(urls), 2)
        self.assertTrue(all('per_page=100&' in url for url in urls))
        self.assertTrue(urls[-1].endswith('page=2'))

    def test_live_missing_link_and_drift(self):
        live = {10: {'base': {'ref': 'main'}, 'head': {'ref': v.PARENT}, 'state': 'open'}}
        errs, _ = v.check_live(self.doc, live)
        self.assertTrue(any('broken link' in x for x in errs))

    def test_live_sha_drift_warning_not_merge_approval(self):
        live = {10: {'base': {'ref': 'main'}, 'head': {'ref': v.PARENT}, 'state': 'open'}}
        for p in self.doc['children']:
            live[p['number']] = {'html_url': p['url'], 'base': {'ref': p['base']},
                                 'head': {'ref': p['head'], 'sha': 'b' * 40},
                                 'state': p['state'], 'title': p['title']}
        errs, warnings = v.check_live(self.doc, live)
        self.assertFalse(errs)
        self.assertEqual(len(warnings), 46)


class CampaignPrivacyTests(unittest.TestCase):
    def test_public_synthetic_fixture(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'docs/open-source-scouting/fixtures/test.json')
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'actor': 'test@example.com', 'id': 'fake-001'}))
            self.assertEqual(v.check_privacy(['docs/open-source-scouting/fixtures/test.json'], Path(d)), [])

    def test_secret_synthetic_fixture_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'docs/open-source-scouting/fixtures/test.json')
            path.parent.mkdir(parents=True)
            path.write_text('token' + '=' + 'secret_value_that_must_not_escape')
            self.assertTrue(any('secret' in e for e in v.check_privacy(['docs/open-source-scouting/fixtures/test.json'], Path(d))))

    def test_identifying_fixture_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'docs/open-source-scouting/fixtures/test.json')
            path.parent.mkdir(parents=True)
            path.write_text('person@' + 'real-user.test')
            self.assertTrue(any('non-synthetic' in e for e in v.check_privacy(['docs/open-source-scouting/fixtures/test.json'], Path(d))))

    def test_sensitive_path_rejected_even_without_file(self):
        self.assertTrue(any('forbidden' in e for e in v.check_privacy(['profiles/real.sqlite'], Path('/tmp'))))

    def test_validator_source_is_not_a_secret(self):
        self.assertEqual(v.check_privacy(['tools/validate_open_source_campaign.py'], SOURCE.parents[1]), [])

    def test_sensitive_nested_cache_path_blocked(self):
        self.assertTrue(any('forbidden' in e for e in v.check_privacy(
            ['00_OPERATIVO/cache/errores/event.json'], Path('/tmp'))))
        self.assertTrue(any('forbidden' in e for e in v.check_privacy(
            ['local/profile/prefs.json'], Path('/tmp'))))

    def test_scope_brief_is_not_an_implementation(self):
        self.assertTrue(v.check_child_deliverables(['docs/open-source-scouting/tasks/01-x.md']))

    def test_child_needs_evidence_and_test(self):
        with tempfile.TemporaryDirectory() as d:
            doc = Path(d, 'docs/research/work.md')
            doc.parent.mkdir(parents=True)
            doc.write_text('\n'.join(('## Problema', '## Alternativas', '## Licencias y procedencia',
                                        '## Decisión', '## Pruebas', '## Retirada',
                                        'Fuente primaria: https://docs.github.com/en/rest/pulls/pulls',
                                        'Fecha de consulta: 2026-10-09', 'Licencia SPDX: NOASSERTION',
                                        'Referencia inmutable: N/A (sin codigo incorporado)')), encoding='utf-8')
            paths = ['docs/research/work.md', 'tests/test_work.py']
            self.assertEqual(v.check_child_deliverables(paths, Path(d)), [])

    def test_child_missing_spdx_metadata_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d, 'docs/research/work.md')
            path.parent.mkdir(parents=True)
            path.write_text('\n'.join(('## Problema', '## Alternativas', '## Licencias y procedencia',
                                        '## Decisión', '## Pruebas', '## Retirada')), encoding='utf-8')
            self.assertTrue(v.check_child_deliverables(['docs/research/work.md', 'tests/test_work.py'], Path(d)))

    def test_symlink_outside_root_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            link = root / 'docs/research/link.md'
            link.parent.mkdir(parents=True)
            link.symlink_to(root.parent / 'not-here', target_is_directory=False)
            self.assertTrue(v.check_privacy(['docs/research/link.md'], root))

    def test_deleted_path_does_not_disclose_content(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(v.check_privacy(['docs/research/deleted.md'], Path(d)), [])


if __name__ == '__main__':
    unittest.main()
