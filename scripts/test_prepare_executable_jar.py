import os
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from prepare_executable_jar import prepare_executable_jar, read_launcher


LAUNCHER = b"#!/bin/bash\nexec java -jar \"$0\" \"$@\"\n"


class PrepareExecutableJarTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def jar(self, name, version, prefix=b""):
        path = self.root / name
        path.write_bytes(prefix)
        with ZipFile(path, "a") as archive:
            archive.writestr("META-INF/MANIFEST.MF", f"Implementation-Version: {version}\n")
            archive.writestr("BOOT-INF/classes/app.class", b"class bytes")
        return path

    def test_plain_jar_keeps_previous_launcher_and_new_payload(self):
        source = self.jar("source.jar", "3.0.0")
        target = self.jar("target.jar", "2.5.0", LAUNCHER)
        original_source = source.read_bytes()
        prepare_executable_jar(source, target)
        self.assertEqual(target.read_bytes(), LAUNCHER + original_source)
        self.assertEqual(source.read_bytes(), original_source)
        self.assertTrue(os.access(target, os.X_OK))
        with ZipFile(target) as archive:
            self.assertIn(b"3.0.0", archive.read("META-INF/MANIFEST.MF"))
            self.assertEqual(archive.read("BOOT-INF/classes/app.class"), b"class bytes")

    def test_executable_source_is_copied_without_a_duplicate_launcher(self):
        source = self.jar("source.jar", "3.0.0", LAUNCHER)
        target = self.root / "target.jar"
        prepare_executable_jar(source, target)
        self.assertEqual(target.read_bytes(), source.read_bytes())
        self.assertEqual(read_launcher(target), LAUNCHER)

    def test_missing_launcher_leaves_existing_target_unchanged(self):
        source = self.jar("source.jar", "3.0.0")
        target = self.jar("target.jar", "2.5.0")
        original_target = target.read_bytes()
        with self.assertRaisesRegex(ValueError, "does not contain a shell launcher"):
            prepare_executable_jar(source, target)
        self.assertEqual(target.read_bytes(), original_target)
        self.assertFalse(list(self.root.glob(".apollo-jar-*")))

    def test_source_and_target_can_be_the_same_file(self):
        target = self.jar("target.jar", "3.0.0")
        previous = self.jar("previous.jar", "2.5.0", LAUNCHER)
        original_target = target.read_bytes()
        prepare_executable_jar(target, target, previous)
        self.assertEqual(target.read_bytes(), LAUNCHER + original_target)


if __name__ == "__main__":
    unittest.main()
