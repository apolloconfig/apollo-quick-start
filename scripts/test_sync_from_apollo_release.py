#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import sync_from_apollo_release as sync


class SyncFromApolloReleaseTest(unittest.TestCase):
    def test_inject_sample_data_before_footer_and_once(self) -> None:
        base_sql = (
            "CREATE TABLE `Sample` (`Id` int(11));\n\n"
            "INSERT INTO `Sample` VALUES (1);\n\n"
            f"{sync.FOOTER_ANCHOR}\n"
            "/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;\n"
        )
        sample_block = (
            "# Sample Data\n"
            "# ------------------------------------------------------------\n"
            "INSERT INTO `Sample` VALUES (2);\n"
        )

        rendered = sync._inject_sample_data(base_sql, sample_block, "sample.sql")
        normalized_block = sample_block.strip("\n")
        self.assertEqual(rendered.count(normalized_block), 1)
        self.assertLess(rendered.index(normalized_block), rendered.index(sync.FOOTER_ANCHOR))

    def test_enforce_portal_member_only_env_sets_dev(self) -> None:
        base_sql = (
            "INSERT INTO `ServerConfig` (`Key`, `Value`, `Comment`)\n"
            "VALUES\n"
            "    ('configView.memberOnly.envs', 'pro', 'desc');\n"
        )

        rendered = sync._enforce_portal_member_only_env(base_sql)
        self.assertIn("'configView.memberOnly.envs', 'dev',", rendered)
        self.assertNotIn("'configView.memberOnly.envs', 'pro',", rendered)

    def test_sync_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            apollo_root = root / "apollo"
            quick_start_root = root / "apollo-quick-start"
            self._seed_fake_layout(apollo_root=apollo_root, quick_start_root=quick_start_root)

            sync.sync_from_apollo_release(
                apollo_repo_root=apollo_root,
                quick_start_root=quick_start_root,
                check_only=False,
            )
            first_config = (quick_start_root / "sql/apolloconfigdb.sql").read_text(encoding="utf-8")
            first_portal = (quick_start_root / "sql/apolloportaldb.sql").read_text(encoding="utf-8")

            sync.sync_from_apollo_release(
                apollo_repo_root=apollo_root,
                quick_start_root=quick_start_root,
                check_only=False,
            )
            second_config = (quick_start_root / "sql/apolloconfigdb.sql").read_text(encoding="utf-8")
            second_portal = (quick_start_root / "sql/apolloportaldb.sql").read_text(encoding="utf-8")

            self.assertEqual(first_config, second_config)
            self.assertEqual(first_portal, second_portal)

            sync.sync_from_apollo_release(
                apollo_repo_root=apollo_root,
                quick_start_root=quick_start_root,
                check_only=True,
            )

    def test_inject_sample_data_requires_footer_anchor(self) -> None:
        with self.assertRaises(sync.SyncError):
            sync._inject_sample_data(
                "CREATE TABLE `Sample` (`Id` int(11));\n",
                "INSERT INTO `Sample` VALUES (1);\n",
                "sample.sql",
            )

    def _seed_fake_layout(self, *, apollo_root: Path, quick_start_root: Path) -> None:
        config_source = apollo_root / "scripts/sql/profiles/mysql-default/apolloconfigdb.sql"
        portal_source = apollo_root / "scripts/sql/profiles/mysql-default/apolloportaldb.sql"
        overlay_config = quick_start_root / "sql/overlays/apolloconfigdb-sample-data.sql"
        overlay_portal = quick_start_root / "sql/overlays/apolloportaldb-sample-data.sql"

        config_source.parent.mkdir(parents=True, exist_ok=True)
        portal_source.parent.mkdir(parents=True, exist_ok=True)
        overlay_config.parent.mkdir(parents=True, exist_ok=True)
        overlay_portal.parent.mkdir(parents=True, exist_ok=True)

        config_source.write_text(
            (
                "CREATE TABLE `Config` (`Id` int(11));\n"
                "INSERT INTO `Config` VALUES (1);\n\n"
                f"{sync.FOOTER_ANCHOR}\n"
                "/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;\n"
            ),
            encoding="utf-8",
        )
        portal_source.write_text(
            (
                "INSERT INTO `ServerConfig` (`Key`, `Value`, `Comment`)\n"
                "VALUES\n"
                "    ('configView.memberOnly.envs', 'pro', 'desc');\n\n"
                f"{sync.FOOTER_ANCHOR}\n"
                "/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;\n"
            ),
            encoding="utf-8",
        )
        overlay_config.write_text(
            (
                "# Sample Data\n"
                "# ------------------------------------------------------------\n"
                "INSERT INTO `Config` VALUES (2);\n"
            ),
            encoding="utf-8",
        )
        overlay_portal.write_text(
            (
                "# Sample Data\n"
                "# ------------------------------------------------------------\n"
                "INSERT INTO `ServerConfig` (`Key`, `Value`, `Comment`)\n"
                "VALUES\n"
                "    ('sample.key', 'sample.value', 'sample config');\n"
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
