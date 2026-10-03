#!/usr/bin/env python3
"""Keep the quick-start JAR's shell launcher when upstream builds a plain JAR."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import tempfile
from zipfile import ZipFile


def read_launcher(path: Path) -> bytes:
    with path.open("rb") as stream:
        if stream.read(2) != b"#!":
            return b""
        with ZipFile(path) as archive:
            offset = min(entry.header_offset for entry in archive.infolist())
        stream.seek(0)
        return stream.read(offset)


def prepare_executable_jar(source: Path, target: Path, launcher_from: Path | None = None) -> None:
    # Validate the source before touching the existing target.
    with ZipFile(source) as archive:
        archive.getinfo("META-INF/MANIFEST.MF")

    prefix = b""
    if not read_launcher(source):
        launcher_source = launcher_from or target
        if not launcher_source.is_file():
            raise ValueError(f"No existing executable JAR to supply the shell launcher: {launcher_source}")
        prefix = read_launcher(launcher_source)
        if not prefix:
            raise ValueError(f"JAR does not contain a shell launcher: {launcher_source}")

    mode = (target.stat().st_mode if target.exists() else source.stat().st_mode) & 0o777
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".apollo-jar-", delete=False) as output:
            temporary_path = Path(output.name)
            output.write(prefix)
            with source.open("rb") as input_stream:
                shutil.copyfileobj(input_stream, output)
            output.flush()
            os.fsync(output.fileno())
        with ZipFile(temporary_path) as archive:
            archive.getinfo("META-INF/MANIFEST.MF")
        temporary_path.chmod(mode | 0o111)
        temporary_path.replace(target)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--launcher-from", type=Path)
    args = parser.parse_args()
    prepare_executable_jar(args.source, args.target, args.launcher_from)
    print(f"Prepared executable JAR: {args.target}")


if __name__ == "__main__":
    main()
