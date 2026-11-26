#!/usr/bin/env python3
"""Build the Quick Start distribution from a release checkout and its assembly JAR."""

import argparse
import hashlib
from pathlib import Path
import re
import shutil
import tempfile
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


FILES = (
    "README.md", "Dockerfile", "demo.sh",
    "docker-compose.yml", "docker-compose-arm64.yml",
    "client/apollo-demo.jar", "client/log4j2.xml", "client/META-INF/app.properties",
    "sql/apolloconfigdb.sql", "sql/apolloportaldb.sql",
)


def check_jar(path, required_entry):
    with ZipFile(path) as jar:
        jar.getinfo(required_entry)
        corrupt = jar.testzip()
        if corrupt:
            raise ValueError(f"Corrupt JAR member in {path}: {corrupt}")


def package(root, jar, version, output):
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError(f"Invalid release version: {version}")
    if (root / "VERSION").read_text().strip() != version:
        raise ValueError(f"VERSION does not match {version}")
    check_jar(jar, "BOOT-INF/classes/")
    check_jar(root / "client/apollo-demo.jar", "META-INF/MANIFEST.MF")
    name = f"apollo-quick-start-{version}"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as tmp:
        archive = Path(tmp) / f"{name}.zip"
        with ZipFile(archive, "w") as bundle:
            for member in (*FILES, "VERSION", "apollo-all-in-one.jar"):
                source = jar if member == "apollo-all-in-one.jar" else root / member
                info = ZipInfo(f"{name}/{member}")
                info.create_system = 3
                info.external_attr = (0o100755 if member == "demo.sh" else 0o100644) << 16
                info.compress_type = ZIP_DEFLATED
                with bundle.open(info, "w") as dest:
                    if member.startswith("docker-compose"):
                        content, count = re.subn(
                            r"(?m)^(\s*image: nobodyiam/apollo-quick-start)$",
                            rf"\g<1>:{version}", source.read_text(),
                        )
                        if count != 1:
                            raise ValueError(f"Expected one Quick Start image in {member}")
                        dest.write(content.encode())
                    else:
                        with source.open("rb") as src:
                            shutil.copyfileobj(src, dest)
        digest = hashlib.sha256()
        with archive.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        checksum = archive.with_suffix(".zip.sha256")
        checksum.write_text(f"{digest.hexdigest()}  {archive.name}\n")
        archive.replace(output / archive.name)
        checksum.replace(output / checksum.name)
    return output / archive.name


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    print(package(args.root, args.jar, args.version, args.output))
