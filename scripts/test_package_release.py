import hashlib
import tempfile
import unittest
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from package_release import package


class ReleasePackageTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "dist"
        self.jar = self.root / "server.jar"
        for member in ("README.md", "Dockerfile", "demo.sh", "client/log4j2.xml",
                       "client/META-INF/app.properties", "sql/apolloconfigdb.sql", "sql/apolloportaldb.sql"):
            dest = self.root / member
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(member)
        (self.root / "VERSION").write_text("3.1.0\n")
        for filename in ("docker-compose.yml", "docker-compose-arm64.yml"):
            (self.root / filename).write_text("    image: nobodyiam/apollo-quick-start\n")
        with ZipFile(self.jar, "w") as jar:
            jar.writestr("BOOT-INF/classes/", "")
        with ZipFile(self.root / "client/apollo-demo.jar", "w") as client:
            client.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0")

    def test_distributable_layout_permissions_image_versions_and_checksum(self):
        archive = package(self.root, self.jar, "3.1.0", self.output)
        prefix = "apollo-quick-start-3.1.0/"
        with ZipFile(archive) as bundle:
            self.assertEqual(bundle.read(prefix + "apollo-all-in-one.jar"), self.jar.read_bytes())
            self.assertTrue(bundle.getinfo(prefix + "demo.sh").external_attr >> 16 & 0o111)
            for name in ("docker-compose.yml", "docker-compose-arm64.yml"):
                self.assertIn(b"image: nobodyiam/apollo-quick-start:3.1.0\n", bundle.read(prefix + name))
        expected = f"{hashlib.sha256(archive.read_bytes()).hexdigest()}  {archive.name}\n"
        self.assertEqual(archive.with_suffix(".zip.sha256").read_text(), expected)

    def test_refuses_mismatched_version_and_pointer_instead_of_jar(self):
        with self.assertRaisesRegex(ValueError, "VERSION"):
            package(self.root, self.jar, "3.0.0", self.output)
        self.jar.write_text("version https://git-lfs.github.com/spec/v1\n")
        with self.assertRaises(BadZipFile):
            package(self.root, self.jar, "3.1.0", self.output)
        self.assertFalse(self.output.exists())
