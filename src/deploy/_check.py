#!/usr/bin/python3.6
"""This script is meant to run standalone on the cluster which uses RHEL8 and
only has Python 3.6"""

import sys
from typing import List, Sequence, Dict, Any
from pathlib import Path
import json
import argparse


def get_unused_store_paths(store: Path, versions: Sequence[Path]) -> List[str]:
    used = {
        path.replace("/prog/replace", "/prog/cirrus")
        for vpath in versions
        for manifest in vpath.glob("*/manifest")
        for path in manifest.read_text().splitlines()
    }

    available = {str(p) for p in store.glob("*")}
    return list(sorted(available - used))


def details(store: Path, versions: Sequence[Path]) -> Dict[str, Any]:
    return {
        "unused_store_paths": get_unused_store_paths(store, versions),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", help="Location of the store", required=True)
    ap.add_argument(
        "--versions",
        nargs="+",
        help="Locations of 'versions' directories",
        required=True,
    )
    args = ap.parse_args()

    store = Path(args.store)
    versions = [Path(p) for p in args.versions]

    json.dump(details(store, versions), sys.stdout)


if __name__ == "__main__":
    main()
