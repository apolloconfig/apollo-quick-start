"""Select Docker tags for a Quick Start release."""

import re
import subprocess
import sys


VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
IMAGE = "nobodyiam/apollo-quick-start"


def image_tags(version, alias, current_version, git_tags):
    if not VERSION.fullmatch(version) or not VERSION.fullmatch(current_version):
        raise ValueError("Expected x.y.z for the release and the default branch VERSION")
    if alias and not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}", alias):
        raise ValueError("Invalid Docker tag")
    if VERSION.fullmatch(alias) and alias != version:
        raise ValueError("A versioned image tag must match the release version")

    tags = [version]
    if alias not in ("", version, "latest"):
        tags.append(alias)
    elif version == current_version:
        # An older workflow rerun must never roll latest back, even on a maintenance branch.
        candidate = tuple(map(int, version.split(".")))
        stable_versions = (tag[1:] for tag in git_tags if tag.startswith("v") and VERSION.fullmatch(tag[1:]))
        if all(tuple(map(int, release.split("."))) <= candidate for release in stable_versions):
            tags.append("latest")
    return ",".join(f"{IMAGE}:{tag}" for tag in tags)


if __name__ == "__main__":
    git_tags = subprocess.check_output(["git", "tag", "--list", "v*"], text=True).splitlines()
    version, alias, current_version = sys.argv[1:]
    print(image_tags(version, alias, current_version, git_tags))
