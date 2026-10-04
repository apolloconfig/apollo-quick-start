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
    time.sleep(float(os.environ.get('STUB_JAVA_STOP_DELAY', '0')))
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
                        LOG_APPENDERS='CONSOLE', RUN_ARGS='--example=value --enabled',
                        JAVA_OPTS='-Xmx128m -Dexample=value',
                        APOLLO_CONFIG_DB_PASSWORD='password with spaces')
        result = self.invoke('start')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        args = self.wait_for_call()['args']
        self.assertIn('-Dspring.config-datasource.password=password with spaces', args)
        self.assertIn('-Xmx128m', args)
        self.assertIn('-Dexample=value', args)
        self.assertEqual(args[-2:], ['--example=value', '--enabled'])
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

    def test_stop_does_not_signal_an_unrelated_live_pid(self) -> None:
        for command in (['sleep', '60'],
                        [str(self.bin / 'java'), '-jar', str(self.root / 'apollo-all-in-one.jar.backup')]):
            with self.subTest(command=command):
                unrelated = subprocess.Popen(command, env=self.env, stdout=subprocess.DEVNULL)
                self.processes.append(unrelated)
                if command[0] != 'sleep':
                    self.wait_for_call()
                self.pid_file.parent.mkdir(exist_ok=True)
                self.pid_file.write_text(str(unrelated.pid) + '\n')
                self.env['STOP_WAIT_TIME'] = '2'
                result = self.invoke('stop')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIsNone(unrelated.poll())
                self.assertFalse(self.pid_file.exists())
                unrelated.terminate()
                unrelated.wait(timeout=5)

    def test_start_replaces_an_unrelated_live_pid(self) -> None:
        unrelated = subprocess.Popen(['sleep', '60'])
        self.processes.append(unrelated)
        self.pid_file.parent.mkdir()
        self.pid_file.write_text(str(unrelated.pid) + '\n')
        # Avoid the legacy HTTP wait if the old PID-only check regresses.
        self.write_executable('curl', '#!/bin/bash\necho "HTTP/1.1 200 OK"\n')
        result = self.invoke('start')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn('Already running', result.stdout)
        self.assertEqual(int(self.pid_file.read_text()), self.wait_for_call()['pid'])
        self.assertIsNone(unrelated.poll())
        self.assertEqual(self.invoke('stop').returncode, 0)

    def test_stop_timeout_with_leading_zeros_is_decimal(self) -> None:
        for timeout, delay in [('010', '8.25'), ('08', '0.1'), ('09', '0.1')]:
            with self.subTest(timeout=timeout):
                self.env.update(STOP_WAIT_TIME=timeout, STUB_JAVA_STOP_DELAY=delay)
                self.assertEqual(self.invoke('start').returncode, 0)
                result = self.invoke('stop')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(self.pid_file.exists())

    def test_stop_without_pid_is_successful(self) -> None:
        self.assertEqual(self.invoke('stop').returncode, 0)

    def test_mingw_uses_pid_only_process_checks(self) -> None:
        self.write_executable('uname', '#!/bin/bash\necho MINGW64_NT\n')
        self.write_executable('cygpath', '#!/bin/bash\nprintf "%s\\n" "${@: -1}"\n')
        actual_ps = shutil.which('ps')
        self.write_executable('ps', f'''#!/usr/bin/env python3
import os, pathlib, subprocess, sys
assert sys.argv[1] == '-p' and len(sys.argv) == 3, sys.argv
pathlib.Path(os.environ['STUB_STATE_DIR'], 'pid-only-check').touch()
raise SystemExit(subprocess.call([{actual_ps!r}, *sys.argv[1:]]))
''')
        self.assertEqual(self.invoke('start').returncode, 0)
        self.assertEqual(self.invoke('stop').returncode, 0)
        self.assertTrue((self.root / 'pid-only-check').exists())
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

    def test_linux_privilege_drop_requires_setpriv_before_launch(self) -> None:
        self.env.update(PATH=str(self.bin), RUN_AS_USER='apollo-run')
        (self.bin / 'dirname').symlink_to(shutil.which('dirname'))
        self.write_executable('uname', '#!/bin/bash\necho Linux\n')
        self.write_executable('id', '#!/bin/bash\nif [[ $# == 1 ]]; then echo 0; else echo 1000; fi\n')
        result = self.invoke('run')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('Required command not found: setpriv', result.stdout)
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

    def test_start_uses_legacy_http_timeout_and_retains_pid_until_stop(self) -> None:
        self.env['STUB_CURL_FAIL'] = '1'
        self.write_executable('sleep', '#!/bin/bash\nexit 0\n')
        result = self.invoke('start')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('Service failed to start in 120 seconds', result.stdout)
        self.assertIn('Waiting for service startup' + '.' * 24, result.stdout)
        self.assertTrue(self.pid_file.exists())
        # Restore real sleep so graceful-stop polling allows the mock JVM to exit.
        (self.bin / 'sleep').unlink()
        self.assertEqual(self.invoke('stop').returncode, 0)
        self.assertFalse(self.pid_file.exists())

    def test_user_options_retain_legacy_whitespace_splitting(self) -> None:
        self.env.update(STUB_JAVA_FAIL='1', JAVA_OPTS='-Xmx128m -Dexample="two words"',
                        RUN_ARGS='--example "" --literal=$(echo_example)')
        result = self.invoke('run')
        self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
        args = self.calls()[0]['args']
        self.assertIn('-Dexample="two', args)
        self.assertIn('words"', args)
        self.assertEqual(args[-3:], ['--example', '""', '--literal=$(echo_example)'])

    def test_abandoned_lock_directory_does_not_block_start(self) -> None:
        (self.pid_file.parent / '.lock').mkdir(parents=True)
        self.test_plain_jar_start_duplicate_start_and_graceful_stop()

    def test_stop_discards_invalid_pid(self) -> None:
        self.pid_file.parent.mkdir()
        self.pid_file.write_text('invalid\n')
        self.assertEqual(self.invoke('stop').returncode, 0)
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
