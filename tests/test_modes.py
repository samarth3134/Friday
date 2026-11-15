"""Mode-system acceptance tests. Mocks Ollama HTTP; no live model is called."""
import importlib.util
import json
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.support import ROOT as SUPPORT_ROOT, load_module  # noqa: E402


def load_brain(**stubs):
    config = types.SimpleNamespace(USER_NAME='Test user', OLLAMA_MODEL='test-model',
        WEATHER_CITY='Bengaluru', WINDOWS_USER='test-user', ALLOWED_ROOTS=[],
        BLACKLISTED_PATHS=[], MAX_READ_CHARS=50000)
    request_stub = types.SimpleNamespace(
        get=Mock(side_effect=AssertionError('Network forbidden')),
        post=Mock(side_effect=AssertionError('Network forbidden')))
    imports = {'config': config, 'requests': request_stub}
    imports.update(stubs)
    spec = importlib.util.spec_from_file_location('tested_brain_modes', SUPPORT_ROOT / 'brain.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, imports):
        spec.loader.exec_module(module)
    return module


class ModesJsonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='friday-modes-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'modes.json'
        self.path.write_text(json.dumps({
            'version': 1,
            'fast': {'model': 'qwen3:4b', 'system': 'fast system', 'num_ctx': 8192,
                     'num_predict': 200, 'think': False, 'memory': 'personal',
                     'web_search': False, 'keep_alive': '30m', 'spoken': 'short'},
            'think': {'model': 'qwen3:4b', 'system': 'think system', 'num_ctx': 16384,
                      'num_predict': 1536, 'think': True, 'memory': 'all',
                      'web_search': True, 'keep_alive': '30m', 'spoken': 'summary'},
        }), encoding='utf-8')
        import modes
        self.modes = modes
        self._old_file = modes.MODES_FILE
        self._old_state = dict(modes._state)
        modes.MODES_FILE = self.path
        modes._state = {"active": "fast"}
        self.addCleanup(lambda: setattr(modes, 'MODES_FILE', self._old_file))
        self.addCleanup(lambda: setattr(modes, '_state', self._old_state))

    def test_load_modes_round_trips_builtin_settings(self):
        modes = self.modes.load_modes()
        self.assertEqual(modes['fast']['num_ctx'], 8192)
        self.assertFalse(modes['fast']['think'])
        self.assertEqual(modes['fast']['memory'], 'personal')
        self.assertFalse(modes['fast']['web_search'])
        self.assertTrue(modes['think']['think'])
        self.assertEqual(modes['think']['memory'], 'all')
        self.assertTrue(modes['think']['web_search'])

    def test_unknown_mode_falls_back_and_custom_create_round_trip(self):
        self.assertEqual(self.modes.list_modes(), ['fast', 'think'])
        ok, message = self.modes.set_active_mode('missing')
        self.assertFalse(ok)
        ok, message = self.modes.set_active_mode('think')
        self.assertTrue(ok)
        resolved = self.modes.set_to_fast()
        self.assertEqual(self.modes.active_mode(), 'fast')

        created_ok, created_msg = self.modes.create_mode_from_text(
            'make a mode called tutor that writes patient haiku')
        self.assertTrue(created_ok)
        self.assertIn('tutor', created_msg)
        saved = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(saved['tutor']['system'], 'writes patient haiku')
        self.assertIn('tutor', self.modes.list_modes())
        ok, message = self.modes.set_active_mode('tutor')
        self.assertTrue(ok)


class BrainModeSwitchTests(unittest.TestCase):
    def setUp(self):
        self.brain = load_brain()
        self.brain._safe_import = Mock(return_value=None)
        self.brain._save_exchange = Mock()
        import modes
        self.modes = modes
        temp = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        temp.write(json.dumps({'version': 1,
            'fast': {'model': 'qwen3:4b', 'system': 'fast', 'num_ctx': 8192, 'num_predict': 200,
                     'think': False, 'memory': 'personal', 'web_search': False,
                     'keep_alive': '30m', 'spoken': 'short'},
            'think': {'model': 'qwen3:4b', 'system': 'think', 'num_ctx': 16384, 'num_predict': 1536,
                      'think': True, 'memory': 'all', 'web_search': True,
                      'keep_alive': '30m', 'spoken': 'summary'}}))
        temp.close()
        self.temp_path = Path(temp.name)
        self._old_file = self.modes.MODES_FILE
        self._old_state = dict(self.modes._state)
        self.modes.MODES_FILE = self.temp_path
        self.modes._state = {"active": "fast"}
        self.addCleanup(lambda: setattr(self.modes, 'MODES_FILE', self._old_file))
        self.addCleanup(lambda: setattr(self.modes, '_state', self._old_state))
        self.addCleanup(self.temp_path.unlink)

    def test_explicit_switches_stay_fast_by_default(self):
        self.assertEqual(self.modes.active_mode(), 'fast')
        reply = self.brain.respond('think about this')
        self.assertEqual(self.modes.active_mode(), 'think')

        reply = self.brain.respond('switch to fast')
        self.assertEqual(self.modes.active_mode(), 'fast')
        reply = self.brain.respond('switch to think')
        self.assertEqual(self.modes.active_mode(), 'think')

        reply = self.brain.respond('back to normal')
        self.assertEqual(self.modes.active_mode(), 'fast')
        reply = self.brain.respond('quick')
        self.assertEqual(self.modes.active_mode(), 'fast')

    def test_unknown_mode_stays_fast(self):
        reply = self.brain.respond('switch to nope')
        self.assertIn('do not have a mode called nope', reply)
        self.assertEqual(self.modes.active_mode(), 'fast')


class EscalationTests(unittest.TestCase):
    def setUp(self):
        self.brain = load_brain()
        self.brain._safe_import = Mock(return_value=None)
        self.brain._save_exchange = Mock()
        import modes
        self.modes = modes
        temp = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        temp.write(json.dumps({'version': 1,
            'fast': {'model': 'qwen3:4b', 'system': 'fast', 'num_ctx': 8192, 'num_predict': 200,
                     'think': False, 'memory': 'personal', 'web_search': False,
                     'keep_alive': '30m', 'spoken': 'short'},
            'think': {'model': 'qwen3:4b', 'system': 'think', 'num_ctx': 16384, 'num_predict': 1536,
                      'think': True, 'memory': 'all', 'web_search': True,
                      'keep_alive': '30m', 'spoken': 'summary'}}))
        temp.close()
        self.temp_path = Path(temp.name)
        self._old_file = self.modes.MODES_FILE
        self._old_state = dict(self.modes._state)
        self.modes.MODES_FILE = self.temp_path
        self.modes._state = {"active": "fast"}
        self.addCleanup(lambda: setattr(self.modes, 'MODES_FILE', self._old_file))
        self.addCleanup(lambda: setattr(self.modes, '_state', self._old_state))
        self.addCleanup(self.temp_path.unlink)

    def test_tool_intents_never_escalate(self):
        with patch.object(self.brain, 'route', return_value='ok') as route, \
                patch.object(self.brain, '_memory_context', return_value=''):
            self.brain.respond('should I bring a jacket?')  # weather intent: tool command, stays fast
            self.assertEqual(route.call_args.kwargs.get('mode_name'), 'fast')
            self.brain.respond('why is the sky blue?')    # research intent
            self.assertEqual(route.call_args.kwargs.get('mode_name'), 'think')

    def test_reasoning_cues_escalate_but_only_once(self):
        with patch.object(self.brain, 'route', return_value='ok') as route, \
                patch.object(self.brain, '_memory_context', return_value=''):
            self.brain.respond('why is the sky blue?')
            self.assertEqual(route.call_args.kwargs.get('mode_name'), 'think')
            self.assertEqual(self.modes.active_mode(), 'fast')  # one-shot, not a mode switch
            self.brain.respond('explain why the sky is blue')
            self.assertEqual(route.call_args.kwargs.get('mode_name'), 'think')

    def test_long_questions_escalate(self):
        text = 'what ' * 80 + 'is going on with this weird situation'
        self.assertGreater(len(text), 180)
        with patch.object(self.brain, 'route', return_value='ok') as route, \
                patch.object(self.brain, '_memory_context', return_value=''):
            self.brain.respond(text)
            self.assertEqual(route.call_args.kwargs.get('mode_name'), 'think')

    def test_tool_intent_gets_no_memory_but_chat_does(self):
        memory = Mock()
        memory.search_memory.return_value = [{'text': 'fact'}]

        def _import(name):
            return memory if name == 'memory' else None

        self.brain._safe_import = Mock(side_effect=_import)
        with patch.object(self.brain, 'route', return_value='ok'):
            self.brain.respond('capital of france?')          # casual → not personal in fast
            fast_calls = memory.search_memory.call_count
            self.assertEqual(fast_calls, 0)
            self.brain.respond('what is my favorite color?')   # personal
            self.assertEqual(memory.search_memory.call_count, 1)


class WebSearchTests(unittest.TestCase):
    def setUp(self):
        self.brain = load_brain()
        import modes
        self.modes = modes
        temp = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
        temp.write(json.dumps({'version': 1,
            'fast': {'model': 'qwen3:4b', 'system': 'fast', 'num_ctx': 8192, 'num_predict': 200,
                     'think': False, 'memory': 'none', 'web_search': False,
                     'keep_alive': '30m', 'spoken': 'short'},
            'think': {'model': 'qwen3:4b', 'system': 'think', 'num_ctx': 16384, 'num_predict': 1536,
                      'think': True, 'memory': 'all', 'web_search': True,
                      'keep_alive': '30m', 'spoken': 'summary'}}))
        temp.close()
        self.temp_path = Path(temp.name)
        self._old_file = self.modes.MODES_FILE
        self._old_state = dict(self.modes._state)
        self.modes.MODES_FILE = self.temp_path
        self.modes._state = {"active": "fast"}
        self.addCleanup(lambda: setattr(self.modes, 'MODES_FILE', self._old_file))
        self.addCleanup(lambda: setattr(self.modes, '_state', self._old_state))
        self.addCleanup(self.temp_path.unlink)

    def test_fast_mode_does_not_call_web_search(self):
        search = MagicMock()
        search.web_search.return_value = 'web result'
        self.brain._safe_import = Mock(return_value=search)
        with patch.object(self.brain, '_ollama', return_value='answer') :
            self.brain.respond('search for planets')  # search intent
            search.web_search.assert_not_called()

    def test_think_mode_calls_web_search(self):
        search = MagicMock()
        search.web_search.return_value = 'web result'
        search.news_search.return_value = 'news result'

        def _import(name):
            return search if name == 'search' else None

        self.brain._safe_import = Mock(side_effect=_import)
        self.modes._state = {"active": "think"}
        with patch.object(self.brain, '_ollama', return_value='answer'):
            self.brain.respond('search for planets')
            search.web_search.assert_called_once_with('planets')


if __name__ == '__main__':
    unittest.main()
