"""Run offline tests and save machine-readable results without live integrations.

Usage: python -B tests/run_tests.py
The nonzero exit status intentionally preserves unresolved regression failures.
"""
import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True


def deny_external_actions(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'subprocess.Popen',
                 'os.system', 'os.startfile', 'os.startfile/2'}:
        raise RuntimeError('Offline tests blocked external action: ' + event)


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({'test': test.id(), 'status': 'passed'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append({'test': test.id(), 'status': 'failed',
                             'detail': self._exc_info_to_string(err, test)})

    def addError(self, test, err):
        super().addError(test, err)
        self.records.append({'test': test.id(), 'status': 'error',
                             'detail': self._exc_info_to_string(err, test)})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.records.append({'test': test.id(), 'status': 'skipped', 'detail': reason})

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err:
            status = 'failed' if issubclass(err[0], test.failureException) else 'error'
            self.records.append({'test': subtest.id(), 'parent_test': test.id(), 'status': status,
                                 'detail': self._exc_info_to_string(err, test)})


def write_markdown_report(report):
    lines = [f"# Offline test results — {report['run_at']}", '',
             f"**{report['tests_run']} methods: {report['passed_test_methods']} passed, "
             f"{report['failed_test_methods']} failed; {report['errors']} errors, "
             f"{report['skipped']} skipped.**", '',
             f"Python: `{sys.executable}` ({sys.version.split()[0]}).", '',
             'Run from the project directory: `python -B tests/run_tests.py`', '',
             'External services, OAuth, audio, desktop actions, and Chroma are mocked. '
             'SQLite and plain-file tests use temporary fixtures. No live integration readiness is implied.', '',
             '## Results by suite', '', '| Suite | Passed methods | Failed/error methods |',
             '| --- | ---: | ---: |']
    suites = sorted({r['test'].split('.')[1] for r in report['records']})
    for suite in suites:
        records = [r for r in report['records'] if r['test'].split('.')[1] == suite]
        passed = sum(r['status'] == 'passed' for r in records)
        failed = len({r.get('parent_test', r['test']) for r in records
                      if r['status'] in {'failed', 'error'}})
        lines.append(f'| {suite}.py | {passed} | {failed} |')
    lines += ['', '## Failures', '']
    failures = [r for r in report['records'] if r['status'] in {'failed', 'error'}]
    if not failures:
        lines.append('None. All executed cases passed; unchecked README acceptance items remain unverified or only partly covered.')
    else:
        lines += ['- `' + r['test'] + '`' for r in failures]
    lines += ['', '## Passing cases', '']
    lines += ['- [x] `' + r['test'] + '`' for r in report['records'] if r['status'] == 'passed']
    lines += ['', '## Limits', '',
              'Live authentication/delivery, actual hardware, browser rendering, real Chroma persistence, '
              'clean installation, and full concurrency behavior are not established by this run.', '',
              'Full traces: [latest.txt](results/latest.txt). Structured results: [latest.json](results/latest.json).', '']
    (ROOT / 'tests' / 'RESULTS.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    sys.addaudithook(deny_external_actions)
    stream = io.StringIO()
    original_cwd = Path.cwd()
    try:
        with tempfile.TemporaryDirectory(prefix='friday-offline-') as sandbox:
            os.chdir(sandbox)
            suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), top_level_dir=str(ROOT))
            # Suppress app debug output; the test runner records names and assertions.
            with contextlib.redirect_stdout(io.StringIO()):
                result = unittest.TextTestRunner(stream=stream, verbosity=2,
                                                resultclass=RecordedResult).run(suite)
            os.chdir(original_cwd)
    finally:
        os.chdir(original_cwd)
    report_dir = ROOT / 'tests' / 'results'
    report_dir.mkdir(exist_ok=True)
    failed_methods = {r.get('parent_test', r['test']) for r in result.records if r['status'] == 'failed'}
    report = {'python': sys.version,
              'run_at': datetime.now(timezone(timedelta(hours=5, minutes=30))).isoformat(timespec='seconds'),
              'mode': 'offline, mocked external services and desktop actions',
              'tests_run': result.testsRun, 'failures': len(result.failures),
              'passed_test_methods': sum(r['status'] == 'passed' for r in result.records),
              'failed_test_methods': len(failed_methods),
              'errors': len(result.errors), 'skipped': len(result.skipped),
              'records': result.records}
    (report_dir / 'latest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    (report_dir / 'latest.txt').write_text(stream.getvalue(), encoding='utf-8')
    write_markdown_report(report)
    print(f"Ran {result.testsRun} test methods: {report['passed_test_methods']} passed, "
          f"{len(failed_methods)} failed, {len(result.errors)} errors, {len(result.skipped)} skipped.")
    print(f"Failure assertions (including subtests): {len(result.failures)}")
    for name in sorted(failed_methods):
        print('FAIL: ' + name)
    print('Results saved in tests/results/latest.json and latest.txt')
    sys.exit(0 if result.wasSuccessful() else 1)
