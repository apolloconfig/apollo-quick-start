#!/usr/bin/env python3
"""Sync quick-start SQL files from an Apollo release and apply local overlays."""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

FOOTER_ANCHOR = "/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;"

APOLLO_CONFIG_SQL_REL = Path("scripts/sql/profiles/mysql-default/apolloconfigdb.sql")
APOLLO_PORTAL_SQL_REL = Path("scripts/sql/profiles/mysql-default/apolloportaldb.sql")

QUICK_START_CONFIG_SQL_REL = Path("sql/apolloconfigdb.sql")
QUICK_START_PORTAL_SQL_REL = Path("sql/apolloportaldb.sql")

OVERLAY_CONFIG_SAMPLE_REL = Path("sql/overlays/apolloconfigdb-sample-data.sql")
OVERLAY_PORTAL_SAMPLE_REL = Path("sql/overlays/apolloportaldb-sample-data.sql")


class SyncError(RuntimeError):
    """Raised when sync validation or file operations fail."""


@dataclass
class RenderResult:
    outputs: dict[Path, str]
    sample_blocks: dict[Path, str]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SyncError(f"Unable to read file: {path}") from exc


def _write_text(path: Path, content: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise SyncError(f"Unable to write file: {path}") from exc


def _must_exist(path: Path, label: str) -> None:
    if not path.exists():
        raise SyncError(f"{label} does not exist: {path}")


def _inject_sample_data(base_sql: str, sample_block: str, sql_name: str) -> str:
    anchor_count = base_sql.count(FOOTER_ANCHOR)
    if anchor_count != 1:
        raise SyncError(
            f"{sql_name} must contain exactly one footer anchor '{FOOTER_ANCHOR}', found {anchor_count}."
        )

    normalized_block = sample_block.strip("\n")
    if not normalized_block:
        raise SyncError(f"{sql_name} sample overlay is empty.")

    anchor_pos = base_sql.index(FOOTER_ANCHOR)
    prefix = base_sql[:anchor_pos].rstrip("\n")
    suffix = base_sql[anchor_pos:].lstrip("\n")
    return f"{prefix}\n\n{normalized_block}\n\n{suffix}"


def _enforce_portal_member_only_env(sql_text: str) -> str:
    pattern = re.compile(r"('configView\.memberOnly\.envs'\s*,\s*)'[^']*'(\s*,)")
    replaced, count = pattern.subn(r"\1'dev'\2", sql_text, count=1)
    if count != 1:
        raise SyncError("Failed to enforce configView.memberOnly.envs='dev' in apolloportaldb.sql")
    return replaced


def _validate_sql_output(
    output_sql: str,
    sample_block: str,
    sql_name: str,
    *,
    require_member_only_env_dev: bool = False,
) -> None:
    anchor_count = output_sql.count(FOOTER_ANCHOR)
    if anchor_count != 1:
        raise SyncError(
            f"{sql_name} must contain exactly one footer anchor '{FOOTER_ANCHOR}', found {anchor_count}."
        )

    normalized_block = sample_block.strip("\n")
    block_count = output_sql.count(normalized_block)
    if block_count != 1:
        raise SyncError(f"{sql_name} sample overlay block must appear exactly once, found {block_count}.")

    if output_sql.index(normalized_block) > output_sql.index(FOOTER_ANCHOR):
        raise SyncError(f"{sql_name} sample overlay must be inserted before SQL footer.")

    if require_member_only_env_dev:
        values = re.findall(r"'configView\.memberOnly\.envs'\s*,\s*'([^']+)'\s*,", output_sql)
        if len(values) != 1:
            raise SyncError(
                "apolloportaldb.sql must contain exactly one configView.memberOnly.envs entry, "
                f"found {len(values)}."
            )
        if values[0] != "dev":
            raise SyncError(
                "apolloportaldb.sql configView.memberOnly.envs must be 'dev', "
                f"found '{values[0]}'."
            )


def _assert_same_content(path: Path, expected: str, actual: str) -> None:
    if actual == expected:
        return

    diff_lines = list(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile=f"{path} (expected)",
            tofile=f"{path} (actual)",
            lineterm="",
        )
    )
    preview = "\n".join(diff_lines[:80])
    raise SyncError(f"{path} does not match expected synced content.\n{preview}")


def _render_release_sql(apollo_repo_root: Path, quick_start_root: Path) -> RenderResult:
    source_config_path = apollo_repo_root / APOLLO_CONFIG_SQL_REL
    source_portal_path = apollo_repo_root / APOLLO_PORTAL_SQL_REL
    overlay_config_path = quick_start_root / OVERLAY_CONFIG_SAMPLE_REL
    overlay_portal_path = quick_start_root / OVERLAY_PORTAL_SAMPLE_REL

    _must_exist(source_config_path, "Apollo config SQL")
    _must_exist(source_portal_path, "Apollo portal SQL")
    _must_exist(overlay_config_path, "Quick-start config sample overlay")
    _must_exist(overlay_portal_path, "Quick-start portal sample overlay")

    source_config_sql = _read_text(source_config_path)
    source_portal_sql = _read_text(source_portal_path)
    config_sample_block = _read_text(overlay_config_path)
    portal_sample_block = _read_text(overlay_portal_path)

    rendered_config_sql = _inject_sample_data(
        source_config_sql,
        config_sample_block,
        "apolloconfigdb.sql",
    )
    rendered_portal_sql = _enforce_portal_member_only_env(
        _inject_sample_data(
            source_portal_sql,
            portal_sample_block,
            "apolloportaldb.sql",
        )
    )

    config_output_path = quick_start_root / QUICK_START_CONFIG_SQL_REL
    portal_output_path = quick_start_root / QUICK_START_PORTAL_SQL_REL
    return RenderResult(
        outputs={
            config_output_path: rendered_config_sql,
            portal_output_path: rendered_portal_sql,
        },
        sample_blocks={
            config_output_path: config_sample_block,
            portal_output_path: portal_sample_block,
        },
    )


def sync_from_apollo_release(
    apollo_repo_root: Path,
    quick_start_root: Path,
    *,
    check_only: bool,
) -> list[Path]:
    render_result = _render_release_sql(apollo_repo_root=apollo_repo_root, quick_start_root=quick_start_root)
    output_paths = sorted(render_result.outputs.keys())

    if not check_only:
        for output_path in output_paths:
            _write_text(output_path, render_result.outputs[output_path])

    for output_path in output_paths:
        _must_exist(output_path, "Synced SQL output")
        actual_content = _read_text(output_path)
        expected_content = render_result.outputs[output_path]
        _assert_same_content(output_path, expected_content, actual_content)

        _validate_sql_output(
            output_sql=actual_content,
            sample_block=render_result.sample_blocks[output_path],
            sql_name=output_path.name,
            require_member_only_env_dev=output_path.name == "apolloportaldb.sql",
        )

    return output_paths


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync quick-start SQL files from Apollo release SQL and local overlays."
    )
    parser.add_argument(
        "--apollo-repo-root",
        required=True,
        help="Path to the checked-out apollo repository at target tag.",
    )
    parser.add_argument(
        "--quick-start-root",
        default=".",
        help="Path to apollo-quick-start repository root (default: current directory).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate that outputs match expected synced content without writing files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    apollo_repo_root = Path(args.apollo_repo_root).resolve()
    quick_start_root = Path(args.quick_start_root).resolve()

    try:
        output_paths = sync_from_apollo_release(
            apollo_repo_root=apollo_repo_root,
            quick_start_root=quick_start_root,
            check_only=args.check,
        )
    except SyncError as exc:
        print(f"[sync_from_apollo_release] ERROR: {exc}", file=sys.stderr)
        return 1

    action = "Validated" if args.check else "Synced"
    formatted_paths = ", ".join(str(path.relative_to(quick_start_root)) for path in output_paths)
    print(f"[sync_from_apollo_release] {action}: {formatted_paths}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
