#!/usr/bin/env python3
"""Generate and independently execute synthetic Azraq SQL examples."""

import argparse
import os
from pathlib import Path

from triage_sql.examples import DB_MANIFEST, OUTPUT_DIR, RELATIONSHIPS, generate_examples

DEFAULT_DSN = "postgresql://azraq:azraq_local_only@127.0.0.1:55432/azraq"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--manifest", type=Path, default=DB_MANIFEST)
    parser.add_argument("--relationships", type=Path, default=RELATIONSHIPS)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    count = generate_examples(args.dsn, args.manifest, args.relationships, args.output_dir)
    print(f"Wrote {count} validated examples across train/validation/heldout; snapshot-bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
