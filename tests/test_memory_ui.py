"""Memory contracts and UI callbacks; no real Chroma, microphone, or dashboard."""
import ast
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, Mock, patch

from tests.support import ROOT, load_module


class SourceTests(unittest.TestCase):
    def test_all_application_sources_parse(self):
        sources = sorted(ROOT.glob('*.py'))
        self.assertEqual(len(sources), 18)
        for source in sources:
            with self.subTest(file=source.name):
                ast.parse(source.read_text(encoding='utf-8-sig'), filename=source.name)


class OptionalStartupTests(unittest.TestCase):
    def test_missing_optional_services_leave_main_usable(self):
        app = load_module('main')
        with patch.dict(sys.modules, {'tasks': None, 'memory': None,
                                      'whatsapp_desktop': None, 'wakeword': None}), \
                patch.object(app, 'check_ollama', return_value=True), \
                patch.object(app, 'launch_dashboard') as launch, patch('builtins.print'):
            app.main()
        launch.assert_called_once()

    def test_terminal_still_answers_without_voice_module(self):
        app = load_module('main')
        brain = Mock()
        brain.process.return_value = 'text answer'
        with patch.dict(sys.modules, {'voice': None, 'brain': brain}), \
                patch('builtins.input', side_effect=['hello', 'quit']), \
                patch('builtins.print') as output:
            app.terminal_loop()
        brain.process.assert_called_once_with('hello')
        output.assert_any_call('Friday: text answer')


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.chroma = MagicMock()
        self.memory = load_module('memory', {'chromadb': self.chroma})
        self.collection = self.memory.collection
        self.memory._now = lambda: '2026-11-06T10:00:00+00:00'

    def test_save_memory_id_text_metadata_and_empty_input(self):
        for text in (None, 1, '', ' '):
            self.assertIsNone(self.memory.save_memory(text))
        self.collection.add.assert_not_called()
        mid = self.memory.save_memory('  A fact  ')
        args = self.collection.add.call_args.kwargs
        self.assertEqual(args['ids'], [mid])
        self.assertEqual(len(mid), 36)
        self.assertEqual(args['documents'], ['A fact'])
        self.assertEqual(args['metadatas'], [{'timestamp': self.memory._now(), 'type': 'fact'}])
        self.memory.save_memory('remember that I like tea')
        self.assertEqual(self.collection.add.call_args.kwargs['metadatas'][0]['type'], 'preference')
        metadata = {'type': 'preference', 'source': 'test'}
        self.memory.save_memory('coffee', metadata)
        self.assertEqual(metadata, {'type': 'preference', 'source': 'test'})
        self.assertEqual(self.collection.add.call_args.kwargs['metadatas'][0]['source'], 'test')

    def test_search_query_contract_empty_and_invalid(self):
        for value in ('', ' ', None, 123):
            self.assertEqual(self.memory.search_memory(value), [])
        self.collection.query.assert_not_called()
        self.collection.query.return_value = {'documents': [['tea']], 'metadatas': [[{'type': 'fact'}]],
                                              'distances': [[0.1]]}
        result = self.memory.search_memory(' drink ', n=2)
        self.collection.query.assert_called_once_with(query_texts=['drink'], n_results=2,
            include=['documents', 'metadatas', 'distances'])
        self.assertEqual(result, [{'text': 'tea', 'metadata': {'type': 'fact'}, 'distance': 0.1}])
        self.collection.query.return_value = {'documents': [[]], 'metadatas': [[]], 'distances': [[]]}
        self.assertEqual(self.memory.search_memory('unknown'), [])

    def test_conversation_roles_and_recent_chronology(self):
        cid = self.memory.save_conversation(' Question ', ' Answer ')
        args = self.collection.add.call_args.kwargs
        self.assertEqual(args['documents'], ['Question', 'Answer'])
        self.assertEqual(len(set(args['ids'])), 2)
        self.assertEqual([m['role'] for m in args['metadatas']], ['user', 'friday'])
        self.assertTrue(all(m['conversation_id'] == cid for m in args['metadatas']))
        documents, metadata = [], []
        for index in (3, 1, 2):
            for role in ('friday', 'user'):
                documents.append(f'{role}-{index}')
                metadata.append({'conversation_id': str(index), 'timestamp': f'2026-11-0{index}', 'role': role})
        self.collection.get.return_value = {'documents': documents, 'metadatas': metadata}
        recent = self.memory.get_recent(2)
        self.assertEqual([p['user'] for p in recent], ['user-2', 'user-3'])
        self.assertEqual([p['friday'] for p in recent], ['friday-2', 'friday-3'])

    def test_regression_remember_request_stores_one_preference(self):
        brain = load_module('brain')
        with patch.object(brain, '_safe_import', return_value=self.memory):
            self.collection.query.return_value = {'documents': [[]], 'metadatas': [[]], 'distances': [[]]}
            brain.respond('remember that I like tea')
        preferences = [m for call in self.collection.add.call_args_list
                       for m in call.kwargs['metadatas'] if m['type'] == 'preference']
        self.assertEqual(len(preferences), 1, 'A remember request must not create duplicate preferences')


class UiTests(unittest.TestCase):
    def setUp(self):
        self.brain, self.dashboard, self.voice = Mock(), Mock(), Mock()
        self.ui = load_module('ui', {'brain': self.brain, 'dashboard': self.dashboard, 'voice': self.voice})

    def test_submit_preserves_history_and_empty_input(self):
        history = [{'role': 'user', 'content': 'old'}]
        self.brain.classify_intent.return_value = 'casual'
        self.brain.process.return_value = 'Hello'
        result, cleared, label = self.ui._append_response(history, ' Hi ')
        self.assertEqual(result[0], {'role': 'user', 'content': 'old'})
        self.assertEqual(result[1], {'role': 'user', 'content': 'Hi'})
        self.assertIn('Hello', result[2]['content'])
        self.assertEqual(cleared, '')
        self.assertEqual(label, 'Handled by: casual')
        self.brain.process.assert_called_once_with('Hi')
        for blank in (None, '', ' '):
            self.assertEqual(self.ui._append_response(result, blank), (result, '', 'Handled by: none'))
        self.assertEqual(len(result), 3)

    def test_mic_empty_and_success_callbacks(self):
        self.voice.listen.return_value = None
        history, text, explanation = self.ui._mic_response([])
        self.assertEqual((history, text), ([], ''))
        self.assertIn('Could not hear', explanation)
        self.brain.process.assert_not_called()
        self.voice.listen.return_value = 'hello'
        self.brain.classify_intent.return_value = 'casual'
        self.brain.process.return_value = 'answer'
        history, _, _ = self.ui._mic_response([])
        self.assertEqual(len(history), 2)
        self.brain.process.assert_called_once_with('hello')

    def test_regression_mic_failure_has_visible_explanation(self):
        self.voice.listen.return_value = None
        history, text, label = self.ui._mic_response([])
        self.assertTrue(history or text or 'could not' in label.lower(),
                        'The UI should explain why microphone input produced no message')

    def test_status_escaping_and_missing_memory(self):
        value = '<script>alert("x")</script>'
        status = dict.fromkeys(('current_time', 'date', 'weather', 'todays_tasks', 'todays_calendar_events',
                               'unread_email_count', 'unread_whatsapp_count', 'now_playing'), value)
        status['recent_memory_snippets'] = [value]
        status['friday_state'] = value
        self.dashboard.get_status.return_value = status
        rendered = self.ui._format_status()
        self.assertNotIn('<script>', rendered.lower())
        self.assertIn('&lt;script&gt;', rendered)
        status['recent_memory_snippets'] = None
        self.assertIn('No recent memory yet.', self.ui._format_status())
        status.update(weather='Weather is unavailable.', unread_email_count='Email is unavailable.')
        self.assertIn('Weather is unavailable.', self.ui._format_status())


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.dashboard = load_module('dashboard')

    def test_service_failures_and_unavailable_memory_fall_back(self):
        with patch.object(self.dashboard, '_import', return_value=None):
            result = self.dashboard.get_status()
        self.assertEqual(result['friday_state'], 'idle')
        self.assertEqual(result['recent_memory_snippets'], [])
        self.assertIn('unavailable', result['weather'])
        broken = Mock()
        broken.get_weather.side_effect = RuntimeError('offline')
        with patch.object(self.dashboard, '_import', return_value=broken):
            self.assertEqual(self.dashboard._call('weather', 'get_weather', 'fallback'), 'fallback')

    def test_regression_status_refresh_does_not_drive_whatsapp_ui(self):
        messaging = Mock()
        messaging.gmail_get_unread.return_value = 'You have no unread emails.'
        messaging.wa_get_unread.return_value = 'not implemented'
        def resolve(name):
            return messaging if name == 'messaging' else None
        with patch.object(self.dashboard, '_import', side_effect=resolve):
            self.dashboard.get_status()
        messaging.wa_get_unread.assert_not_called()

    def test_count_parser_no_unread_and_failure_messages(self):
        self.assertEqual(self.dashboard._count_from_spoken('You have no unread emails.'), 0)
        self.assertEqual(self.dashboard._count_from_spoken('Could not connect: offline'), 'Could not connect: offline')
        self.assertEqual(self.dashboard._count_from_spoken('Unread emails: one; two.'), 2)

    def test_status_cached_within_ttl_and_rebuilds_after_expiry(self):
        calls = []
        def fake_call(module, function, fallback, *args):
            calls.append((module, function))
            return fallback
        with patch.object(self.dashboard, '_call', side_effect=fake_call), \
                patch.object(self.dashboard, '_import', return_value=None), \
                patch.object(self.dashboard, '_recent_memory', return_value=[]):
            self.dashboard.clear_status_cache()
            self.dashboard.get_status()
            first_build = list(calls)
            self.assertTrue(first_build)
            self.dashboard.get_status()
            self.assertEqual(calls, first_build, 'a fresh cache entry must not rebuild the status')
            self.dashboard.STATUS_CACHE_TTL_SECONDS = 0
            self.dashboard.get_status()
            self.assertGreater(len(calls), len(first_build))


if __name__ == '__main__':
    unittest.main()
