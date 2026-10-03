#!/usr/bin/env python3
"""Exercise demo.sh's process lifecycle without a database or installed JDK."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]


class DemoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="apollo demo ")
        self.root = Path(self.temp.name)
        shutil.copy2(ROOT / "demo.sh", self.root / "demo.sh")
        with ZipFile(self.root / "apollo-all-in-one.jar", "w") as jar:
            jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
        (self.root / "apollo-all-in-one.jar").chmod(0o644)
        self.bin = self.root / "jdk/bin"
        self.bin.mkdir(parents=True)
        self.write_executable("java", '''#!/usr/bin/env python3
import json, os, pathlib, signal, sys, time
if sys.argv[1:] == ['-version']:
    print('openjdk version "' + os.environ.get('STUB_JAVA_VERSION', '17.0.20') + '"', file=sys.stderr)
    sys.exit(0)
root = pathlib.Path(os.environ['STUB_STATE_DIR'])
def stop(signum, frame):
    (root / 'terminated').write_text(str(os.getpid()))
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
with (root / 'calls.jsonl').open('a') as stream:
    stream.write(json.dumps({'pid': os.getpid(), 'args': sys.argv[1:], 'appenders': os.environ.get('LOG_APPENDERS')}) + '\\n')
print('stub console output', flush=True)
if os.environ.get('STUB_JAVA_FAIL'):
    sys.exit(7)
if 'com.ctrip.framework.apollo.demo.api.SimpleApolloConfigDemo' in sys.argv:
    sys.exit(0)
while True:
    time.sleep(0.05)
''')
        self.write_executable("curl", '''#!/usr/bin/env python3
import os, pathlib, time
if os.environ.get('STUB_CURL_FAIL'):
    raise SystemExit(1)
for _ in range(100):
    if (pathlib.Path(os.environ['STUB_STATE_DIR']) / 'calls.jsonl').exists():
        print('HTTP/1.1 200 OK')
        raise SystemExit(0)
    time.sleep(0.01)
raise SystemExit(1)
''')
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(('APOLLO_', 'JAVA_', 'STUB_'))
                    and key not in ('PID_FOLDER', 'LOG_FOLDER', 'LOG_FILENAME', 'RUN_ARGS', 'RUN_AS_USER', 'STOP_WAIT_TIME', 'LOG_APPENDERS')}
        self.env.update(JAVA_HOME=str(self.bin.parent), PATH=str(self.bin) + os.pathsep + os.environ['PATH'],
                        STUB_STATE_DIR=str(self.root))
        self.processes: list[subprocess.Popen] = []

    def tearDown(self) -> None:
        calls = self.calls()
        for call in calls:
            command = subprocess.run(['ps', '-p', str(call['pid']), '-o', 'args='],
                                     capture_output=True, text=True).stdout
            if str(self.root) not in command:
                continue
            try:
                os.kill(call['pid'], signal.SIGTERM)
            except ProcessLookupError:
                pass
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                command = subprocess.run(['ps', '-p', str(call['pid']), '-o', 'args='],
                                         capture_output=True, text=True).stdout
                if str(self.root) not in command:
                    break
                time.sleep(0.05)
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
        self.temp.cleanup()

    def write_executable(self, name: str, contents: str) -> None:
        path = self.bin / name
        path.write_text(contents)
        path.chmod(0o755)

    def invoke(self, command: str) -> subprocess.CompletedProcess:
        return subprocess.run([str(self.root / 'demo.sh'), command], cwd='/', env=self.env,
                              capture_output=True, text=True, timeout=15)

    def calls(self) -> list[dict]:
        path = self.root / 'calls.jsonl'
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def wait_for_call(self) -> dict:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self.calls():
                return self.calls()[-1]
            time.sleep(0.05)
        self.fail('Java was not launched')

    @property
    def pid_file(self) -> Path:
        return self.root / 'apollo-service/apollo-service.pid'

    def test_plain_jar_start_duplicate_start_and_graceful_stop(self) -> None:
        result = self.invoke('start')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        call = self.wait_for_call()
        self.assertEqual(int(self.pid_file.read_text()), call['pid'])
        self.assertEqual(call['args'][-2:], ['-jar', str(self.root / 'apollo-all-in-one.jar')])
        self.assertEqual(call['appenders'], 'FILE')
        self.assertIn('stub console output', (self.root / 'console.log').read_text())
        result = self.invoke('start')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Already running', result.stdout)
        self.assertEqual(len(self.calls()), 1)
        # Stopping does not require a usable JDK.
        self.env['STUB_JAVA_VERSION'] = '1.8.0_492'
        result = self.invoke('stop')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.pid_file.exists())
        self.assertEqual(int((self.root / 'terminated').read_text()), call['pid'])

    def test_config_paths_run_args_and_database_password_with_spaces(self) -> None:
        self.env.update(PID_FOLDER='pid files', LOG_FOLDER='log files', LOG_FILENAME='output.log',
                        LOG_APPENDERS='CONSOLE', RUN_ARGS='--example="value with spaces"',
                        JAVA_OPTS='-Xmx128m -Dpattern=* -DtrustStore="/tmp/my cert" -Dliteral="$(echo example)"',
                        APOLLO_CONFIG_DB_PASSWORD='password with spaces')
        result = self.invoke('start')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args = self.wait_for_call()['args']
        self.assertIn('-Dspring.config-datasource.password=password with spaces', args)
        self.assertIn('-Dpattern=*', args)
        self.assertIn('-DtrustStore=/tmp/my cert', args)
        self.assertIn('-Dliteral=$(echo example)', args)
        self.assertEqual(args[-1], '--example=value with spaces')
        self.assertEqual(self.calls()[0]['appenders'], 'CONSOLE')
        self.assertTrue((self.root / 'pid files/apollo-service/apollo-service.pid').exists())
        self.assertTrue((self.root / 'log files/output.log').exists())
        self.assertEqual(self.invoke('stop').returncode, 0)

    def test_stale_pid_is_replaced(self) -> None:
        self.pid_file.parent.mkdir()
        self.pid_file.write_text('99999999\n')
        result = self.invoke('start')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(int(self.pid_file.read_text()), self.wait_for_call()['pid'])
        self.assertEqual(self.invoke('stop').returncode, 0)

    def test_concurrent_starts_launch_one_java_process(self) -> None:
        processes = [subprocess.Popen([str(self.root / 'demo.sh'), 'start'], env=self.env,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                     for _ in range(8)]
        self.processes.extend(processes)
        for process in processes:
            stdout, stderr = process.communicate(timeout=15)
            self.assertEqual(process.returncode, 0, stdout + stderr)
        self.assertEqual(len(self.calls()), 1)
        self.assertEqual(int(self.pid_file.read_text()), self.calls()[0]['pid'])
        self.assertEqual(self.invoke('stop').returncode, 0)

    def test_invalid_option_quoting_is_rejected(self) -> None:
        self.env['JAVA_OPTS'] = '-Dexample="unterminated'
        result = self.invoke('run')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertFalse(self.calls())

    def test_run_args_preserve_empty_values(self) -> None:
        self.env.update(STUB_JAVA_FAIL='1', RUN_ARGS='--example "" --trailing ""')
        result = self.invoke('run')
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        self.assertEqual(self.calls()[0]['args'][-4:], ['--example', '', '--trailing', ''])

    def test_stop_does_not_signal_unrelated_process(self) -> None:
        process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])
        self.processes.append(process)
        self.pid_file.parent.mkdir()
        self.pid_file.write_text(str(process.pid) + '\n')
        result = self.invoke('stop')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIsNone(process.poll())
        self.assertFalse(self.pid_file.exists())

    def test_stop_without_pid_is_successful(self) -> None:
        self.assertEqual(self.invoke('stop').returncode, 0)

    def test_mingw_uses_windows_pid_and_powershell_command_line(self) -> None:
        self.write_executable('uname', '#!/bin/bash\necho MINGW64_NT\n')
        self.write_executable('cygpath', '#!/bin/bash\nprintf "%s\\n" "${@: -1}"\n')
        actual_ps = shutil.which('ps')
        self.write_executable('ps', f'''#!/usr/bin/env python3
import os, pathlib, subprocess, sys
assert sys.argv[-1] == '-l', sys.argv
pathlib.Path(os.environ['STUB_STATE_DIR'], 'ps-long').touch()
print('PID PPID PGID WINPID TTY UID STIME COMMAND')
print(sys.argv[2] + ' 1 1 ' + str(int(sys.argv[2]) + 1000000) + ' ? 1000 00:00 /java')
''')
        self.write_executable('powershell.exe', f'''#!/usr/bin/env python3
import os, pathlib, re, subprocess, sys
pathlib.Path(os.environ['STUB_STATE_DIR'], 'powershell-used').touch()
win_pid = int(re.search(r'ProcessId = (\\d+)', sys.argv[-1]).group(1))
raise SystemExit(subprocess.call([{actual_ps!r}, '-p', str(win_pid - 1000000), '-o', 'args=']))
''')
        result = self.invoke('start')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        result = self.invoke('stop')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / 'ps-long').exists())
        self.assertTrue((self.root / 'powershell-used').exists())
        self.assertEqual(self.invoke('client').returncode, 0)
        self.assertEqual(self.calls()[-1]['args'][1], str(self.root / 'client') + ';' + str(self.root / 'client/apollo-demo.jar'))

    def test_missing_ps_is_rejected_before_starting_java(self) -> None:
        # A non-executable directory named ps also makes command -v fail.
        self.env['PATH'] = str(self.bin)
        for name in ('dirname', 'uname'):
            (self.bin / name).symlink_to(shutil.which(name))
        result = self.invoke('start')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('Required command not found: ps', result.stdout)
        self.assertFalse(self.calls())

    def test_run_execs_java_and_forwards_sigterm(self) -> None:
        process = subprocess.Popen([str(self.root / 'demo.sh'), 'run'], env=self.env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.processes.append(process)
        call = self.wait_for_call()
        self.assertEqual(process.pid, call['pid'])
        self.assertFalse(self.pid_file.exists())
        process.terminate()
        self.assertEqual(process.wait(timeout=5), 0)
        self.assertEqual(int((self.root / 'terminated').read_text()), call['pid'])

    def test_run_preserves_java_exit_code(self) -> None:
        self.env['STUB_JAVA_FAIL'] = '1'
        self.assertEqual(self.invoke('run').returncode, 7)

    def test_start_reports_early_java_failure(self) -> None:
        self.env.update(STUB_JAVA_FAIL='1', STUB_CURL_FAIL='1')
        result = self.invoke('start')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('Service failed to start', result.stdout)
        self.assertFalse(self.pid_file.exists())

    def test_client_uses_selected_java_and_quoted_classpath(self) -> None:
        self.env['JAVA_OPTS'] = '-Xmx128m'
        result = self.invoke('client')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args = self.calls()[0]['args']
        self.assertEqual(args[:2], ['-classpath', str(self.root / 'client') + ':' + str(self.root / 'client/apollo-demo.jar')])
        self.assertIn('-Xmx128m', args)

    def test_java_before_17_is_rejected(self) -> None:
        for version in ('1.8.0_492', '11.0.29', '16.0.2'):
            with self.subTest(version=version):
                self.env['STUB_JAVA_VERSION'] = version
                result = self.invoke('start')
                self.assertEqual(result.returncode, 1)
                self.assertIn('Java 17+', result.stdout)
                self.assertFalse(self.calls())


if __name__ == '__main__':
    unittest.main()
