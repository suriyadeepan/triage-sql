#!/usr/bin/env python3
"""Sample-check Azraq relationship metadata against the CSV files.

Requires PyYAML, installed as a project dependency with ``uv add pyyaml``.
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELATIONSHIPS = ROOT / "data/raw/azraq-relationships.yaml"
DEFAULT_DATA_DIR = ROOT / "data/raw/azraq"


@dataclass(frozen=True)
class Endpoint:
    table: str
    column: str


@dataclass(frozen=True)
class Relationship:
    name: str
    source: Endpoint
    targets: tuple[Endpoint, ...]
    candidate: bool = False
    target_filter: tuple[str, str] | None = None
    status: str = "inferred"
    evidence: tuple[str, ...] = ()


def parse_relationships(path: Path) -> list[Relationship]:
    """Load declared and unresolved candidate relationships from YAML."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("YAML document must be a mapping")
    relationships: list[Relationship] = []
    for section, is_candidate in (("relationships", False), ("unresolved_candidates", True)):
        entries = document.get(section, [])
        if not isinstance(entries, list):
            raise ValueError(f"{section} must be a list")
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                raise ValueError(f"invalid entry in {section}: expected mapping with id")
            name = entry["id"]
            source_data = entry.get("from")
            if not isinstance(source_data, dict) or not source_data.get("table") or not source_data.get("column"):
                raise ValueError(f"{name}: missing or malformed from endpoint")
            source = Endpoint(str(source_data["table"]), str(source_data["column"]))
            if not is_candidate:
                target_data = entry.get("to")
                if not isinstance(target_data, dict) or not target_data.get("table") or not target_data.get("column"):
                    raise ValueError(f"{name}: missing or malformed to endpoint")
                targets = (Endpoint(str(target_data["table"]), str(target_data["column"])),)
            else:
                targets = tuple(
                    Endpoint(*item.split(".", 1))
                    for item in entry.get("possible_targets", [])
                    if isinstance(item, str) and item.count(".") == 1
                )
            target_filter = entry.get("target_filter")
            parsed_filter = None
            if target_filter is not None:
                if not isinstance(target_filter, dict) or not target_filter.get("column") or "equals" not in target_filter:
                    raise ValueError(f"{name}: malformed target_filter")
                parsed_filter = (str(target_filter["column"]), str(target_filter["equals"]))
            relationships.append(Relationship(
                name=name,
                source=source,
                targets=targets,
                candidate=is_candidate,
                target_filter=parsed_filter,
                status=str(entry.get("status", "inferred")),
                evidence=tuple(entry.get("evidence", [])),
            ))
    return relationships


def csv_path(data_dir: Path, table: str) -> Path:
    return data_dir / f"{table}.csv"


def read_header(path: Path) -> list[str]:
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.reader(stream)
        return next(reader, [])


def sample_rows(path: Path, size: int, rng: random.Random) -> tuple[list[dict[str, str]], int | None]:
    """Read random physical CSV records without scanning a huge source file.

    Offsets are sampled across the file, then the partial line at each offset
    is discarded and the following CSV record is parsed. This assumes records
    occupy one physical line, as in the supplied Azraq CSVs.
    """
    with path.open("rb") as binary:
        first_line = binary.readline()
        header = next(csv.reader([first_line.decode("utf-8-sig")]), [])
        data_start = binary.tell()
        file_size = path.stat().st_size
        if data_start >= file_size:
            return [], 0

        # Tiny lookup tables are cheap to read completely and can have fewer
        # physical records than the requested sample size.
        if file_size - data_start < 1_000_000:
            binary.seek(data_start)
            rows = list(csv.DictReader(io.TextIOWrapper(binary, encoding="utf-8", newline=""), fieldnames=header))
            return rows[:size], len(rows)

        sampled: list[dict[str, str]] = []
        seen: set[int] = set()
        attempts = 0
        max_attempts = size * 10
        while len(sampled) < size and attempts < max_attempts:
            attempts += 1
            offset = rng.randrange(data_start, file_size)
            if offset in seen:
                continue
            seen.add(offset)
            binary.seek(offset)
            binary.readline()  # Discard the partial record at the random offset.
            line = binary.readline()
            if not line:
                continue
            try:
                fields = next(csv.reader([line.decode("utf-8")]))
            except (UnicodeDecodeError, csv.Error):
                continue
            if len(fields) == len(header):
                sampled.append(dict(zip(header, fields)))
        return sampled, None


def referenced_values(
    path: Path, column: str, target_filter: tuple[str, str] | None = None
) -> tuple[set[str], int, int]:
    values: set[str] = set()
    duplicates: set[str] = set()
    nulls = 0
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            if target_filter and (row.get(target_filter[0]) or "").strip() != target_filter[1]:
                continue
            value = (row.get(column) or "").strip()
            if not value:
                nulls += 1
            else:
                if value in values:
                    duplicates.add(value)
                values.add(value)
    return values, nulls, len(duplicates)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--relationships", type=Path, default=DEFAULT_RELATIONSHIPS)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--sample-size", type=int, default=1000, help="source rows sampled per source table (default: 1000)")
    parser.add_argument("--seed", type=int, default=20261127, help="random seed for reproducible sampling")
    args = parser.parse_args()
    if args.sample_size < 1:
        parser.error("--sample-size must be positive")

    try:
        relationships = parse_relationships(args.relationships)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"ERROR: cannot read relationships: {exc}", file=sys.stderr)
        return 2

    # Sample each source table once so all its relationships use the same rows.
    source_samples: dict[str, tuple[list[dict[str, str]], int | None]] = {}
    target_cache: dict[tuple[str, str, tuple[str, str] | None], tuple[set[str], int, int]] = {}
    failures = 0
    warnings = 0
    print(f"Random source sample size per table: {args.sample_size}; seed: {args.seed}")

    for relation in relationships:
        source_file = csv_path(args.data_dir, relation.source.table)
        if not source_file.is_file():
            print(f"ERROR {relation.name}: source CSV not found: {source_file}")
            failures += not relation.candidate
            warnings += relation.candidate
            continue
        try:
            source_header = read_header(source_file)
        except OSError as exc:
            print(f"ERROR {relation.name}: cannot read source CSV: {exc}")
            failures += not relation.candidate
            warnings += relation.candidate
            continue
        if relation.source.column not in source_header:
            print(f"ERROR {relation.name}: source column {relation.source.column!r} is missing")
            failures += not relation.candidate
            warnings += relation.candidate
            continue

        if relation.source.table not in source_samples:
            # A stable table-specific seed avoids depending on Python hash randomization.
            table_seed = args.seed + sum(map(ord, relation.source.table))
            try:
                source_samples[relation.source.table] = sample_rows(
                    source_file, args.sample_size, random.Random(table_seed)
                )
            except (OSError, csv.Error) as exc:
                print(f"ERROR {relation.name}: cannot sample source CSV: {exc}")
                failures += not relation.candidate
                warnings += relation.candidate
                continue
        rows, total_rows = source_samples[relation.source.table]
        sampled_values = [(row.get(relation.source.column) or "").strip() for row in rows]
        source_nulls = sum(not value for value in sampled_values)
        values = [value for value in sampled_values if value]

        if not relation.targets:
            print(f"SKIP {relation.name}: unresolved candidate has no possible target ({len(values)} non-null sampled values)")
            continue

        for target in relation.targets:
            label = "CANDIDATE" if relation.candidate else "CHECK"
            target_file = csv_path(args.data_dir, target.table)
            if not target_file.is_file():
                message = f"{label} {relation.name} -> {target.table}.{target.column}: target CSV not found"
                print(message)
                failures += not relation.candidate
                warnings += relation.candidate
                continue
            try:
                target_header = read_header(target_file)
                if target.column not in target_header:
                    raise ValueError(f"target column {target.column!r} is missing")
                target_filter = relation.target_filter
                if target_filter and target_filter[0] not in target_header:
                    raise ValueError(f"target filter column {target_filter[0]!r} is missing")
                cache_key = (target.table, target.column, target_filter)
                if cache_key not in target_cache:
                    target_cache[cache_key] = referenced_values(target_file, target.column, target_filter)
                key_values, target_nulls, duplicate_keys = target_cache[cache_key]
            except (OSError, csv.Error, ValueError) as exc:
                print(f"ERROR {relation.name}: cannot inspect target: {exc}")
                failures += not relation.candidate
                warnings += relation.candidate
                continue

            missing = [value for value in values if value not in key_values]
            status = "SAMPLED PASS" if not missing and not duplicate_keys else "SAMPLED FAIL"
            if relation.candidate:
                status = "CANDIDATE " + ("matches" if not missing else "has nonmatching values")
            print(
                f"{status} {relation.name} -> {target.table}.{target.column}: "
                f"sampled {len(rows)}" + (f"/{total_rows}" if total_rows is not None else "") +
                f" source rows, checked {len(values)} non-null values, source nulls {source_nulls}, "
                f"missing {len(missing)}, target distinct values {len(key_values)}, "
                f"target nulls {target_nulls}, duplicate target keys {duplicate_keys}"
            )
            if missing:
                print("  examples missing from target: " + ", ".join(repr(value) for value in missing[:5]))
            if not relation.candidate and (missing or duplicate_keys):
                failures += 1
            if relation.candidate and (missing or duplicate_keys):
                warnings += 1

    print(f"Summary: {len(relationships)} metadata entries; {failures} declared relationship failure(s); {warnings} candidate warning(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
