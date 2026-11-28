import unittest

from docker_tags import IMAGE, image_tags


class DockerTagsTest(unittest.TestCase):
    def test_old_release_retry_cannot_promote_latest(self):
        for alias, expected in (("archive", ["3.9.0", "archive"]), ("latest", ["3.9.0"]),
                                ("3.9.0", ["3.9.0"]), ("", ["3.9.0"])):
            with self.subTest(alias=alias):
                actual = image_tags("3.9.0", alias, "3.10.0", ["v3.9.0", "v3.10.0"])
                self.assertEqual(actual.split(","), [f"{IMAGE}:{tag}" for tag in expected])

    def test_current_release_promotes_latest_only_for_standard_publish(self):
        for alias in ("", "latest", "3.10.0"):
            with self.subTest(alias=alias):
                tags = image_tags("3.10.0", alias, "3.10.0", ["v3.9.0", "v3.11.0-rc1"])
                self.assertEqual(tags, f"{IMAGE}:3.10.0,{IMAGE}:latest")
        self.assertEqual(image_tags("3.10.0", "archive", "3.10.0", []),
                         f"{IMAGE}:3.10.0,{IMAGE}:archive")

    def test_newer_stable_tag_blocks_rollback_even_if_version_file_was_reverted(self):
        self.assertEqual(image_tags("3.9.0", "latest", "3.9.0", ["v3.10.0"]), f"{IMAGE}:3.9.0")

    def test_rejects_other_version_as_alias(self):
        with self.assertRaises(ValueError):
            image_tags("3.10.0", "3.9.0", "3.10.0", [])
