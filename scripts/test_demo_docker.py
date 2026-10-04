#!/usr/bin/env python3
"""Opt-in container signal tests: APOLLO_TEST_DOCKER_IMAGE=<local image> python3 -m unittest discover -s scripts."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid


IMAGE = os.environ.get('APOLLO_TEST_DOCKER_IMAGE')


@unittest.skipUnless(IMAGE and shutil.which('docker'), 'set APOLLO_TEST_DOCKER_IMAGE to a locally built image')
class DemoDockerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix='apollo-signal-')
        root = Path(self.temp.name)
        root.chmod(0o755)
        java = root / 'bin/java'
        java.parent.mkdir()
        java.write_text('''#!/bin/bash
if [[ "$1" == -version ]]; then
  echo 'openjdk version "17.0.20"' >&2
  exit 0
fi
shutdown() {
  echo SHUTDOWN_STARTED
  sleep 5
  echo SHUTDOWN_COMPLETED
  exit 0
}
trap shutdown TERM
echo "READY pid=$$ uid=$(id -u)"
while :; do sleep .1; done
''')
        java.chmod(0o755)
        self.root = root
        self.container = 'apollo-signal-' + uuid.uuid4().hex[:12]

    def tearDown(self) -> None:
        self.docker('rm', '-f', self.container, check=False)
        self.temp.cleanup()

    def docker(self, *args: str, check: bool = True) -> str:
        result = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=30)
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def assert_graceful_stop(self, uid: int, *options: str, command: tuple[str, ...] = ()) -> None:
        self.docker('run', '-d', '--name', self.container, '--network', 'none',
                    '-v', f'{self.root}:/signal-test:ro', '-e', 'JAVA_HOME=/signal-test',
                    *options, IMAGE, *command)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if f'READY pid=1 uid={uid}' in self.docker('logs', self.container):
                break
            time.sleep(0.1)
        else:
            self.fail(self.docker('logs', self.container))
        self.docker('stop', '--time', '15', self.container)
        self.assertIn('SHUTDOWN_COMPLETED', self.docker('logs', self.container))
        state = json.loads(self.docker('inspect', self.container, '--format', '{{json .State}}'))
        self.assertEqual(state['ExitCode'], 0)
        self.assertFalse(state['OOMKilled'])

    def test_default_foreground_process_remains_pid_one(self) -> None:
        self.assert_graceful_stop(0)

    def test_run_as_user_remains_pid_one_and_finishes_slow_shutdown(self) -> None:
        self.assert_graceful_stop(65534, '-e', 'RUN_AS_USER=nobody')

    def test_jar_owner_remains_pid_one_and_finishes_slow_shutdown(self) -> None:
        self.assert_graceful_stop(65534, '--entrypoint', '/bin/bash', command=(
            '-c', 'chown nobody /apollo-quick-start/apollo-all-in-one.jar; exec /apollo-quick-start/demo.sh run'))


if __name__ == '__main__':
    unittest.main()
