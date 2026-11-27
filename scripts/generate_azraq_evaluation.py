#!/usr/bin/env python3
"""Create the reproducible fixed-snapshot Azraq evaluation JSONL."""

import argparse
import json
import os
from pathlib import Path

from triage_sql.evaluation import OUTPUT, SNAPSHOT_MANIFEST, _load_snapshot, generate, validate_items


DEFAULT_DSN = "postgresql://azraq:azraq_local_only@127.0.0.1:55432/azraq"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=os.environ.get("DATABASE_URL", DEFAULT_DSN))
    parser.add_argument("--manifest", type=Path, default=SNAPSHOT_MANIFEST)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    count = generate(args.dsn, args.manifest, args.output)
    snapshot, _ = _load_snapshot(args.manifest)
    items = [json.loads(line) for line in args.output.read_text(encoding="utf-8").splitlines()]
    validate_items(items, snapshot)
    print(f"Wrote {count} fixed-snapshot evaluation questions; snapshot {snapshot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
