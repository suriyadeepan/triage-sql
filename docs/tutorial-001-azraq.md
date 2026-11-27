# Azraq PostgreSQL Data and SQL Evaluation Tutorial

This guide initializes the versioned Azraq schema and regenerates the fixed-snapshot evaluation and synthetic SQL examples.

## Prerequisites and source files

- Python 3.14 managed by `uv`.
- Docker Engine and the pinned PostgreSQL 18.7 image.
- The approved, user-confirmed anonymized CSV snapshot in `data/raw/azraq/`. The large CSVs are not distributed in Git; the manifests record per-file checksums and row counts, and initialization rejects files that do not match.
- Versioned DDL, relationship metadata and source observations in `data/raw/azraq-schema.sql`, `data/raw/azraq-relationships.yaml` and `data/raw/azraq.md`.

The snapshot manifest is `data/manifest/azraq-snapshot.json`; the PostgreSQL manifest is `data/manifest/azraq-postgres.json`. Snapshot ID `ba058d581b04d1d75f63ac0a4705d98ea0d8ea54dcf577ee90b58222d082dddc` identifies the loaded DDL and CSV inputs. Schema `azraq_ba058d581b04d1d7` contains all 26 source tables and has no database-enforced PK/FK constraints.

## Start and initialize PostgreSQL

```sh
uv sync --all-groups
./scripts/azraq_postgres.sh start
uv run python -m scripts.azraq_init
```

PostgreSQL binds to loopback port 55432. The default local password is disposable; set `POSTGRES_PASSWORD` on first startup and `DATABASE_URL` for clients if you use another credential. The initializer streams the source CSVs, replaces `users.password` with NULL, verifies the source checksums, and records row counts. Re-running it verifies the existing snapshot without loading duplicate rows.

Run the deployment smoke sequence with:

```sh
./scripts/azraq_smoke.sh
```

It starts the pinned service, runs the idempotent initializer, and checks Python/PostgreSQL versions, table and client counts, the password-column safeguard, and a read-only query.

## Relationship and JOIN policy

`data/raw/azraq-relationships.yaml` stores inferred relationships separately from the DDL. Only edges with reviewed `validated` status are eligible for generated joins. In particular, the group, individual-member, and NSG joins filter the target `clients.type`; `collaterals.owner_id` accepts any client type. The officer-to-user relationships remain `needs_review` and must not be used to generate joins.

Full validation evidence is in `data/manifest/azraq-relationships-validation.json` and `.md`. Those reports record full-coverage counts; the original 1,000-row randomized samples and initial `not_performed` status remain separate provenance in YAML. Client ID ranges are evidence only, not inferred constraints.

## Evaluation questions

The generated set is `data/evaluation/azraq-evaluation.jsonl` (120 items). Each JSONL row has a natural-language question, category, reference SQL, expected result, execution status and row count, provenance, and immutable snapshot ID. It covers filters, dates, aggregations, validated joins, subtype joins, and multi-table queries. No current item is unsupported or ambiguous; when adding one, set its status to `unsupported` or `ambiguous` and leave `reference_sql` null rather than inventing a query.

Regenerate against the fixed PostgreSQL snapshot with:

```sh
uv run python -m scripts.generate_azraq_evaluation
```

The generator executes statements in a read-only transaction. It refuses a bad snapshot identity and SQL that refers to `users.password`.

## Text-to-SQL and correction examples

Generate both corpora and their independent splits with:

```sh
uv run python -m scripts.generate_azraq_examples
```

Files are stored under `data/examples/azraq/text_to_sql/` and `data/examples/azraq/sql_correction/`, each with `train.jsonl`, `validation.jsonl`, and `heldout.jsonl`. Splits are assigned by query pattern (15/5/4 patterns per split), so template variants do not cross partitions. Every item records the fixed snapshot, validated relationship IDs, expected result, and parse/execution status. Correction items also record how the flawed candidate behaved.

The generator executes SQL read-only, accepts only actual schema references and validated JOIN metadata, and checks normalized question, SQL, result, and pattern fingerprints across partitions. To run the full automated and PostgreSQL integration suite:

```sh
AZRAQ_TEST_DSN='postgresql://azraq:azraq_local_only@127.0.0.1:55432/azraq' uv run pytest
```

Do not include source credential fields or raw, non-anonymized values in new questions, generated examples, logs, or indexes.
