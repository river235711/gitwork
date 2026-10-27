#!/usr/bin/env python3
"""Recursively extract .zip, .tar.gz, and .tgz archives.

Each archive is extracted into a sibling directory named after the archive.
For example, ``backup.tar.gz`` is extracted to ``backup/``.
"""

import argparse
from pathlib import Path
import tarfile
import zipfile


ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".zip")


def archive_stem(path):
    """Return the filename without its supported archive suffix."""
    lower_name = path.name.lower()
    for suffix in ARCHIVE_SUFFIXES:
        if lower_name.endswith(suffix):
            return path.name[: -len(suffix)]
    raise ValueError("Unsupported archive type: {}".format(path))


def is_archive(path):
    return path.is_file() and path.name.lower().endswith(ARCHIVE_SUFFIXES)


def safe_target(destination, member_name):
    """Reject archive entries that would write outside *destination*."""
    target = (destination / member_name).resolve()
    destination = destination.resolve()
    if target != destination and destination not in target.parents:
        raise ValueError("Unsafe archive member path: {}".format(member_name))
    return target


def extract_zip(archive, destination):
    with zipfile.ZipFile(archive) as contents:
        for member in contents.infolist():
            safe_target(destination, member.filename)
        contents.extractall(destination)


def extract_tar(archive, destination):
    with tarfile.open(archive, "r:gz") as contents:
        for member in contents.getmembers():
            safe_target(destination, member.name)
            if member.issym() or member.islnk():
                raise ValueError("Links are not allowed in tar archives: {}".format(member.name))
        # ``filter=\"data\"`` is available only in recent Python versions.
        # The checks above provide the equivalent protection here.
        contents.extractall(destination)


def extract_archive(archive, overwrite):
    destination = archive.with_name(archive_stem(archive))
    if destination.exists() and any(destination.iterdir()) and not overwrite:
        print("Skipping (destination exists): {}".format(archive))
        return destination

    destination.mkdir(parents=True, exist_ok=True)
    print("Extracting: {} -> {}".format(archive, destination))
    if archive.name.lower().endswith(".zip"):
        extract_zip(archive, destination)
    else:
        extract_tar(archive, destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description="Recursively extract ZIP and tar.gz archives.")
    parser.add_argument("directory", nargs="?", default=".", type=Path,
                        help="Directory to search (default: current directory)")
    parser.add_argument("--overwrite", action="store_true",
                        help="Allow extraction into an existing destination directory")
    args = parser.parse_args()

    root = args.directory.resolve()
    if not root.is_dir():
        parser.error("Not a directory: {}".format(root))

    processed = set()
    while True:
        archives = [path for path in root.rglob("*") if is_archive(path) and path not in processed]
        if not archives:
            break
        for archive in archives:
            processed.add(archive)
            try:
                extract_archive(archive, args.overwrite)
            except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile) as error:
                print("Failed: {}: {}".format(archive, error))

    print("Done. Processed {} archive(s).".format(len(processed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
