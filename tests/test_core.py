"""Core acceptance tests. No network, app launch, real memory, or live file mutations."""
import importlib.util
import io
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, **stubs):
    config = types.SimpleNamespace(USER_NAME='Test user', OLLAMA_MODEL='test-model',
        WEATHER_CITY='Bengaluru', WINDOWS_USER='test-user', ALLOWED_ROOTS=[],
        BLACKLISTED_PATHS=[], MAX_READ_CHARS=50000,
        REQUIRE_CONFIRM_ON_DELETE=True, REQUIRE_CONFIRM_ON_WRITE=True)
    request_stub = types.SimpleNamespace(get=Mock(side_effect=AssertionError('Network forbidden')),
                                         post=Mock(side_effect=AssertionError('Network forbidden')))
    imports = {'config': config, 'requests': request_stub}
    imports.update(stubs)
    spec = importlib.util.spec_from_file_location('tested_' + name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, imports):
        spec.loader.exec_module(module)
    return module


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.app = load('main')
        self.output = io.StringIO()
        self.capture = redirect_stdout(self.output)
        self.capture.__enter__()
        self.addCleanup(self.capture.__exit__, None, None, None)

    def test_ollama_health_and_failures(self):
        response = Mock()
        self.app.requests.get = Mock(return_value=response)
        self.assertTrue(self.app.check_ollama())
        self.app.requests.get.assert_called_once_with('http://localhost:11434/api/tags', timeout=3)
        for error in (TimeoutError(), ConnectionRefusedError(), RuntimeError('HTTP 500')):
            with self.subTest(error=type(error).__name__):
                self.app.requests.get = Mock(side_effect=error)
                self.assertFalse(self.app.check_ollama())
        response.raise_for_status.side_effect = RuntimeError('HTTP 404')
        self.app.requests.get = Mock(return_value=response)
        self.assertFalse(self.app.check_ollama())
        self.assertIn('ollama pull llama3', self.output.getvalue())

    def test_dashboard_port_dispatch(self):
        ui = Mock()
        with patch.dict(sys.modules, {'ui': ui}):
            self.app.launch_dashboard()
        ui.build_app.return_value.launch.assert_called_once_with(server_port=7862)

    def test_launch_failure_enters_terminal(self):
        for failure in (OSError('port occupied'), RuntimeError('Gradio failed')):
            with self.subTest(error=str(failure)), patch.multiple(self.app,
                    check_ollama=Mock(return_value=True), initialize_tasks=Mock(),
                    initialize_memory=Mock(), start_whatsapp=Mock(), start_wakeword=Mock(),
                    launch_dashboard=Mock(side_effect=failure), terminal_loop=Mock()):
                self.app.main()
                self.app.terminal_loop.assert_called_once()

    def test_ollama_absent_aborts_before_services(self):
        with patch.object(self.app, 'check_ollama', return_value=False), patch.object(self.app, 'initialize_tasks') as init:
            with self.assertRaises(SystemExit) as result:
                self.app.main()
            self.assertEqual(result.exception.code, 1)
            init.assert_not_called()

    def test_terminal_input_and_clean_exit(self):
        for ending in ('exit', 'quit', EOFError(), KeyboardInterrupt()):
            with self.subTest(ending=str(ending)):
                brain, voice = Mock(), Mock()
                brain.process.return_value = 'answer'
                with patch.dict(sys.modules, {'brain': brain, 'voice': voice}), patch('builtins.input', side_effect=[' ', ' hello ', ending]):
                    self.app.terminal_loop()
                brain.process.assert_called_once_with('hello')
                voice.speak.assert_called_once_with('answer')

    def test_regression_missing_optional_import_is_handled(self):
        with patch.dict(sys.modules, {'whatsapp_desktop': None}):
            try:
                self.app.start_whatsapp()
            except ImportError:
                self.fail('Missing WhatsApp dependency escapes startup fallback')


class BrainTests(unittest.TestCase):
    def setUp(self):
        self.brain = load('brain')
        self.brain._safe_import = Mock(return_value=None)
        self.capture = redirect_stdout(io.StringIO())
        self.capture.__enter__()
        self.addCleanup(self.capture.__exit__, None, None, None)

    def test_intent_examples_case_and_punctuation(self):
        examples = {'list folder D:/projects': 'file_list', 'find file report': 'file_search',
          'read file report.txt': 'file_read', 'open file report.txt': 'file_open',
          'delete file report.txt': 'file_delete', 'create file report.txt': 'file_write',
          'volume 20': 'system_volume', 'open notepad': 'system_app', 'lock screen': 'system_screen',
          'restart in 60': 'system_power', 'weather': 'weather', 'add task buy milk': 'task',
          'play music': 'music', 'unread email': 'email', 'whatsapp': 'whatsapp',
          'calendar today': 'calendar', 'analyze image cat.png': 'vision',
          'remember that I like tea': 'memory_save', 'recall our discussion': 'memory_recall',
          'search for planets': 'search', 'explain gravity': 'research', 'hello': 'casual'}
        for phrase, intent in examples.items():
            for variant in (phrase, phrase.upper() + '!'):
                with self.subTest(phrase=variant):
                    self.assertEqual(self.brain.classify_intent(variant), intent)

    def test_regression_intent_collisions(self):
        for text, expected in [('list tasks', 'task'), ('show weather', 'weather'),
                ('show calendar', 'calendar'), ('play my playlist', 'music'),
                ('music volume 20', 'music')]:
            with self.subTest(text=text):
                self.assertEqual(self.brain.classify_intent(text), expected)

    def test_extract_quoted_paths_and_search_terms(self):
        self.assertEqual(self.brain._extract_path('list folder "D:/My Work"'), 'D:/My Work')
        self.assertEqual(self.brain._extract_path('list D:\\My Work'), 'D:\\My Work')
        self.assertEqual(self.brain._extract_path('show desktop'), 'C:/Users/test-user/Desktop')
        self.assertEqual(self.brain._extract_file_search_term('find file named report.txt'), 'report.txt')
        self.assertEqual(self.brain._extract_file_search_term('find file "annual report"'), 'annual report')

    def test_entry_points_and_tool_error(self):
        for value in (None, 5, '', ' '):
            self.assertIn('did not catch', self.brain.respond(value))
        with patch.object(self.brain, 'route', return_value='answer') as route, patch.object(self.brain, '_save_exchange') as save:
            for name in ('respond', 'process', 'handle', 'chat'):
                self.assertEqual(getattr(self.brain, name)(' hello '), 'answer')
            self.assertEqual(save.call_count, 4)
            self.assertEqual(route.call_count, 4)
        with patch.object(self.brain, 'route', side_effect=RuntimeError('test failure')):
            self.assertIn('test failure', self.brain.respond('hello'))

    def test_ollama_success_empty_and_errors(self):
        response = Mock()
        response.json.return_value = {'response': '  good answer  '}
        self.brain.requests.post = Mock(return_value=response)
        self.assertEqual(self.brain._ollama('hello', context='known fact'), 'good answer')
        kwargs = self.brain.requests.post.call_args.kwargs
        self.assertEqual(kwargs['json']['model'], 'test-model')
        self.assertFalse(kwargs['json']['stream'])
        self.assertIn('known fact', kwargs['json']['prompt'])
        response.json.return_value = {}
        self.assertIn('I am here', self.brain._ollama('hello'))
        response.json.side_effect = ValueError('malformed json')
        self.assertIn('could not reach', self.brain._ollama('hello'))
        response.json.side_effect = None
        for error in (TimeoutError(), RuntimeError('model not found'), RuntimeError('HTTP 500')):
            response.raise_for_status.side_effect = error
            self.assertIn('could not reach', self.brain._ollama('hello'))

    def test_memory_failures_do_not_break_exchange(self):
        memory = Mock()
        self.brain._safe_import.return_value = memory
        memory.search_memory.side_effect = RuntimeError('database unavailable')
        memory.save_conversation.side_effect = RuntimeError('database unavailable')
        with patch.object(self.brain, 'route', return_value='answer'):
            self.assertEqual(self.brain.respond('hello'), 'answer')
        memory.save_conversation.assert_called_once_with('hello', 'answer')
        memory.search_memory.side_effect = None
        memory.search_memory.return_value = [{'text': 'fact'}, 'other', {'text': ''}]
        self.assertEqual(self.brain._memory_context('hello'), 'fact\nother')

    def test_file_dispatch_and_missing_write_arguments(self):
        files = Mock()
        self.brain._safe_import.return_value = files
        for text, intent, method, args in [
            ('find file "report"', 'file_search', 'find_file', ('report',)),
            ('read file "D:/a b.txt"', 'file_read', 'read_file', ('D:/a b.txt',)),
            ('open file "D:/a.txt"', 'file_open', 'open_file', ('D:/a.txt',)),
            ('delete file "D:/a.txt"', 'file_delete', 'delete_file', ('D:/a.txt',)),
            ('list folder "D:/a"', 'file_list', 'list_dir', ('D:/a',)),
            ('create file "D:/a.txt" with hello', 'file_write', 'write_file', ('D:/a.txt', 'hello'))]:
            with self.subTest(intent=intent):
                self.brain._route_files(text, intent)
                getattr(files, method).assert_called_once_with(*args)
        self.assertIn('path and content', self.brain._route_files('create file', 'file_write'))

    def test_search_context_forwarded(self):
        search = Mock()
        search.web_search.return_value = 'Title URL summary'
        self.brain._safe_import.return_value = search
        with patch.object(self.brain, '_ollama', return_value='summary') as llm:
            self.assertEqual(self.brain._route_search('search for planets', 'search', 'memory'), 'summary')
            search.web_search.assert_called_once_with('planets')
            self.assertIn('Title URL summary', llm.call_args.args[2])
            self.assertIn('memory', llm.call_args.args[2])

    def test_regression_task_identifier_parsing(self):
        tasks = Mock()
        self.brain._safe_import.return_value = tasks
        self.brain._route_task('complete task 1')
        tasks.complete_task.assert_called_once_with('1')

    def test_regression_task_due_date_priority(self):
        tasks = Mock()
        self.brain._safe_import.return_value = tasks
        self.brain._route_task('add task submit report due 2026-11-07 priority high')
        tasks.add_task.assert_called_once_with('submit report', due_date='2026-11-07', priority='high')

    def test_regression_lowercase_city(self):
        weather = Mock()
        self.brain._safe_import.return_value = weather
        self.brain._route_weather('weather in new delhi')
        self.assertEqual(weather.get_weather.call_args.args[0].lower(), 'new delhi')

    def test_regression_calendar_delete_today_does_not_list(self):
        calendar = Mock()
        self.brain._safe_import.return_value = calendar
        self.brain._route_calendar('delete event meeting today')
        calendar.get_today.assert_not_called()

    def test_regression_router_integration_task_commands(self):
        tasks = Mock()
        self.brain._safe_import.return_value = tasks
        self.brain._route_task('delete task 1')
        tasks.delete_task.assert_called_once_with('1')
        tasks.reset_mock()
        self.brain._route_task('list tasks')
        tasks.list_tasks.assert_called_once_with('all')
        tasks.reset_mock()
        self.brain._route_task('list overdue tasks')
        tasks.get_overdue.assert_called_once_with()

    def test_music_queue_routing(self):
        music = Mock()
        self.brain._safe_import.return_value = music
        self.brain._route_music('add to queue test song')
        music.add_to_queue.assert_called_once_with('test song')
        music.reset_mock()
        self.brain._route_music('add Test Song Again to the queue')
        music.add_to_queue.assert_called_once_with('Test Song Again')
        music.reset_mock()
        self.brain._route_music('clear the queue')
        music.clear_queue.assert_called_once_with()

    def test_pending_file_confirmation_intercepts_yes_and_cancel(self):
        filesystem = Mock()
        filesystem.has_pending.return_value = True
        filesystem.confirm_pending.return_value = 'I wrote to a.txt.'
        filesystem.cancel_pending.return_value = 'Cancelled.'
        self.brain._safe_import.return_value = filesystem
        with patch.object(self.brain, '_save_exchange'):
            self.assertEqual(self.brain.respond('yes'), 'I wrote to a.txt.')
            filesystem.confirm_pending.assert_called_once_with()
            self.assertEqual(self.brain.respond('cancel'), 'Cancelled.')
            filesystem.cancel_pending.assert_called_once_with()
        filesystem.reset_mock()
        filesystem.has_pending.return_value = False
        filesystem.search_memory.return_value = []
        with patch.object(self.brain, 'route', return_value='ollama reply') as route, \
                patch.object(self.brain, '_save_exchange'):
            self.assertEqual(self.brain.respond('yes'), 'ollama reply')
            route.assert_called_once()
            filesystem.confirm_pending.assert_not_called()


class TaskTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='friday-task-tests-')
        self.addCleanup(self.temp.cleanup)
        self.connections = []
        self.addCleanup(lambda: [connection.close() for connection in self.connections])
        def connect(path):
            connection = sqlite3.connect(path)
            self.connections.append(connection)
            return connection
        old = os.getcwd()
        try:
            os.chdir(self.temp.name)
            self.tasks = load('tasks', sqlite3=types.SimpleNamespace(connect=connect))
        finally:
            os.chdir(old)
        self.tasks.DB_PATH = str(Path(self.temp.name) / 'memory.db')
        self.tasks._today = lambda: '2026-11-06'
        self.tasks._now = lambda: '2026-11-06T10:00:00'

    def test_create_and_persist_valid_tasks_reject_blank(self):
        for value in ('', ' ', None, 4):
            self.assertIn('need a task title', self.tasks.add_task(value))
        self.assertIn('Task added', self.tasks.add_task('  Report  ', '2026-11-07', ' HIGH '))
        with self.tasks._connect() as conn:
            rows = conn.execute('SELECT title,due_date,priority,done FROM tasks').fetchall()
        self.assertEqual(rows, [('Report', '2026-11-07', 'high', 0)])

    def test_filters_order_and_empty_results(self):
        for key in ('all', 'pending', 'done', 'today'):
            self.assertIn('do not have', self.tasks.list_tasks(key))
        self.tasks.add_task('Unscheduled')
        self.tasks.add_task('Tomorrow', '2026-11-07')
        self.tasks.add_task('Today', '2026-11-06')
        self.tasks.add_task('Finished', '2026-11-05')
        self.tasks.complete_task('Finished')
        all_tasks = self.tasks.list_tasks()
        self.assertLess(all_tasks.index('Today'), all_tasks.index('Tomorrow'))
        self.assertLess(all_tasks.index('Tomorrow'), all_tasks.index('Unscheduled'))
        self.assertLess(all_tasks.index('Unscheduled'), all_tasks.index('Finished'))
        pending = self.tasks.list_tasks('pending')
        self.assertNotIn('Finished', pending)
        self.assertIn('Finished', self.tasks.list_tasks('done'))
        self.assertNotIn('Tomorrow', self.tasks.list_tasks('today'))
        self.assertIn('Today', self.tasks.list_tasks('today'))
        self.assertIn('I can list', self.tasks.list_tasks('invalid'))

    def test_complete_delete_by_id_title_and_missing(self):
        self.tasks.add_task('One')
        self.tasks.add_task('Two')
        self.assertIn('complete', self.tasks.complete_task(1))
        self.assertIn('already', self.tasks.complete_task('one'))
        self.assertIn('complete', self.tasks.complete_task('Two'))
        self.assertIn('could not find', self.tasks.complete_task(100))
        self.assertIn('Deleted', self.tasks.delete_task('One'))
        self.assertIn('Deleted', self.tasks.delete_task(2))
        self.assertIn('could not find', self.tasks.delete_task('missing'))
        self.assertIn('do not have any tasks', self.tasks.list_tasks())

    def test_overdue_boundary_and_completion(self):
        self.assertIn('do not have any overdue', self.tasks.get_overdue())
        for title, due in [('Yesterday', '2026-11-05'), ('Today', '2026-11-06'), ('Tomorrow', '2026-11-07'), ('Done', '2026-11-04')]:
            self.tasks.add_task(title, due)
        self.tasks.complete_task('Done')
        result = self.tasks.get_overdue()
        self.assertIn('Yesterday', result)
        for title in ('Today', 'Tomorrow', 'Done'):
            self.assertNotIn(title, result)


class FilesystemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='friday-file-tests-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.allowed = self.root / 'allowed'
        self.allowed.mkdir()
        self.files = load('filesystem')
        self.files.ALLOWED_ROOTS = [str(self.allowed)]
        self.files.BLACKLISTED_PATHS = [str(self.allowed / 'blocked')]

    def test_path_allow_blacklist_outside_and_traversal(self):
        for path, allowed in [(self.allowed, True), (self.allowed / 'x.txt', True),
                (self.root / 'outside', False), (self.allowed / 'blocked' / 'x', False),
                (self.allowed / '..' / 'outside', False)]:
            with self.subTest(path=str(path)):
                self.assertEqual(self.files._check_path(path)[1] is None, allowed)

    def test_find_list_empty_missing_sort_and_errors(self):
        self.assertIn('empty', self.files.list_dir(self.allowed))
        folder = self.allowed / 'zFolder'
        folder.mkdir()
        (folder / 'Report.txt').write_text('hello', encoding='utf-8')
        (self.allowed / 'a.txt').write_text('hello', encoding='utf-8')
        (self.allowed / 'b.txt').write_text('hello', encoding='utf-8')
        result = self.files.list_dir(self.allowed)
        self.assertLess(result.index('zFolder'), result.index('a.txt'))
        self.assertLess(result.index('a.txt'), result.index('b.txt'))
        self.assertIn('Report.txt', self.files.find_file('REPORT'))
        self.assertIn('could not find', self.files.find_file('missing'))
        self.assertIn('could not find', self.files.list_dir(self.allowed / 'missing'))
        self.assertIn('not a folder', self.files.list_dir(self.allowed / 'a.txt'))
        with patch.object(Path, 'iterdir', side_effect=PermissionError()):
            self.assertIn('could not list', self.files.list_dir(self.allowed))

    def test_plain_read_invalid_encoding_directory_and_extension(self):
        for extension, content in [('.txt', 'hello'), ('.json', '{"a":1}'), ('.csv', 'a,b\n1,2')]:
            path = self.allowed / ('sample' + extension)
            path.write_text(content, encoding='utf-8')
            self.assertEqual(self.files.read_file(path), content)
        bad = self.allowed / 'bad.txt'
        bad.write_bytes(b'a\xffb')
        self.assertEqual(self.files.read_file(bad), 'a\ufffdb')
        other = self.allowed / 'unknown.bin'
        other.write_bytes(b'fixture')
        self.assertIn('do not know', self.files.read_file(other))
        self.assertIn('folder, not a file', self.files.read_file(self.allowed))
        self.assertIn('could not find', self.files.read_file(self.allowed / 'missing.txt'))

    def test_long_output_preserves_start_and_end(self):
        self.files.MAX_READ_CHARS = 10
        self.assertEqual(self.files._cap_output('short'), 'short')
        result = self.files._cap_output('START' + 'middle' * 10 + 'FINAL')
        self.assertIn('Start of file:\nSTART', result)
        self.assertIn('End of file:\nFINAL', result)

    def test_confirmation_prevents_mutations(self):
        source, destination = self.allowed / 'source.txt', self.allowed / 'destination.txt'
        source.write_text('original', encoding='utf-8')
        self.assertIn('confirm', self.files.write_file(source, 'changed'))
        self.assertIn('confirm', self.files.move_file(source, destination))
        self.assertIn('confirm', self.files.delete_file(source))
        self.assertEqual(source.read_text(encoding='utf-8'), 'original')
        self.assertFalse(destination.exists())

    def test_temporary_write_move_and_mutation_errors(self):
        self.files.REQUIRE_CONFIRM_ON_WRITE = False
        self.files.REQUIRE_CONFIRM_ON_DELETE = False
        source, destination = self.allowed / 'source.txt', self.allowed / 'nested' / 'dest.txt'
        self.assertIn('I wrote', self.files.write_file(source, 'content'))
        self.assertIn('I moved', self.files.move_file(source, destination))
        self.assertEqual(destination.read_text(encoding='utf-8'), 'content')
        self.assertFalse(source.exists())
        self.assertIn('could not find', self.files.move_file(source, destination))
        with patch('builtins.open', side_effect=PermissionError()):
            self.assertIn('could not write', self.files.write_file(source, 'content'))
        with patch.object(self.files.shutil, 'move', side_effect=PermissionError()):
            self.assertIn('could not move', self.files.move_file(destination, source))
        trash = types.SimpleNamespace(send2trash=Mock(side_effect=PermissionError()))
        with patch.dict(sys.modules, {'send2trash': trash}):
            self.assertIn('could not delete', self.files.delete_file(destination))
        self.assertTrue(destination.exists())

    def test_pending_confirmation_flow_executes_once_and_cancels(self):
        # write confirmation
        target = self.allowed / 'pending.txt'
        reply = self.files.write_file(target, 'content')
        self.assertIn('confirm', reply)
        self.assertTrue(self.files.has_pending())
        self.assertFalse(target.exists())
        self.assertIn('I wrote', self.files.confirm_pending())
        self.assertEqual(target.read_text(encoding='utf-8'), 'content')
        self.assertFalse(self.files.has_pending())
        self.assertIn('no action', self.files.confirm_pending().lower())
        # cancel keeps the pending write from executing
        reply = self.files.write_file(target, 'changed')
        self.assertIn('confirm', reply)
        self.assertIn('cancel', self.files.cancel_pending().lower())
        self.assertFalse(self.files.has_pending())
        self.assertEqual(target.read_text(encoding='utf-8'), 'content')
        self.assertIn('nothing to cancel', self.files.cancel_pending().lower())
        # move confirmation
        source = self.allowed / 'move-me.txt'
        source.write_text('data', encoding='utf-8')
        destination = self.allowed / 'nested' / 'moved.txt'
        self.assertIn('confirm', self.files.move_file(source, destination))
        self.assertTrue(self.files.has_pending())
        self.assertIn('I moved', self.files.confirm_pending())
        self.assertEqual(destination.read_text(encoding='utf-8'), 'data')
        self.assertFalse(source.exists())
        # delete confirmation routes through send2trash once
        source.write_text('data', encoding='utf-8')
        trash = types.SimpleNamespace(send2trash=Mock())
        with patch.dict(sys.modules, {'send2trash': trash}):
            self.assertIn('confirm', self.files.delete_file(source))
            self.assertIn('trash', self.files.confirm_pending().lower())
            trash.send2trash.assert_called_once_with(str(source))
        self.assertFalse(self.files.has_pending())

    def test_open_dispatch_platforms_and_failure(self):
        path = self.allowed / 'file.txt'
        path.write_text('fixture', encoding='utf-8')
        for platform, expected in [('Darwin', 'open'), ('Linux', 'xdg-open')]:
            with self.subTest(platform=platform), patch.object(self.files.platform, 'system', return_value=platform), patch.object(self.files.subprocess, 'Popen') as launch:
                self.assertIn('Opening', self.files.open_file(path))
                launch.assert_called_once_with([expected, str(path.resolve())])
        with patch.object(self.files.platform, 'system', return_value='Windows'), patch.object(self.files.os, 'startfile', create=True) as launch:
            self.assertIn('Opening', self.files.open_file(path))
            launch.assert_called_once_with(path.resolve())
            launch.side_effect = OSError('cannot launch')
            self.assertIn('could not open', self.files.open_file(path))


if __name__ == '__main__':
    unittest.main(verbosity=2)
