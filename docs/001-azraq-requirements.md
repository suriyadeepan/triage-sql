# FS-01 — Azraq Data, Schema & Evaluation Requirements

**Purpose:** Reproducible banking data and leakage-safe SQL training/evaluation.

## Requirements

### R001 — Source data and schema

- **R001.1** Treat `data/raw/` as the source-data location:
  - `data/raw/azraq/*.csv` — data rows (confirmed to match the existing repository layout)
  - `data/raw/azraq-schema.sql` — 26-table DDL and inferred column types
  - `data/raw/azraq-relationships.yaml` — external relationship metadata, evidence, confidence, subtype filters, and validation policy
  - `data/raw/azraq.md` — source observations, if present
- **R001.2** Preserve source table/column names and inferred types; do not invent generic `accounts`/`transactions` tables. The 26 tables are: `branches`, `cities`, `client_locations`, `clients`, `collateral_products`, `collaterals`, `currencies`, `delinquency_tracking`, `districts`, `economic_activities`, `exchange_rates`, `funding_lines`, `groups_members`, `loan_products`, `loan_tranches`, `loan_writeoffs`, `loans`, `manual_schedule_adjustments`, `nsg_meetings`, `regions`, `repayments`, `roles`, `savings_accounts`, `savings_products`, `savings_transactions`, `users`.

### R002 — Relationship metadata and validation

- **R002.1** DDL declares no PK/FK constraints. Keep inferred relationships in YAML; never treat them as database-enforced constraints.
- **R002.2** Preserve relationship endpoints, cardinality, status, confidence, evidence/provenance, and subtype filters.
- **R002.3** Do not use `needs_review` or merely `inferred` edges for JOIN generation; require reviewed `validated` status.
- **R002.4** Preserve the four profiled `clients.type` ranges as evidence only: Individual 1–2,800,000; Group 2,800,001–3,200,000; NSG 3,200,001–3,400,000; Corporate 3,400,001–4,000,000.
- **R002.5** Preserve subtype-aware links: `collaterals.owner_id` → `clients.id` (any type); `groups_members.group_id` → `clients.id` (`type='Group'`); `groups_members.member_id` → `clients.id` (`type='Individual'`); `nsg_meetings.group_id` → `clients.id` (`type='NSG'`). Keep all other YAML relationships and evidence.
- **R002.6** Preserve the original 1,000-row randomized samples per source for these four links (seed `20261127`, zero null/nonmatch in each sample) and manual full-file subtype counts as distinct evidence. The original full null/orphan state was `not_performed`; update current status only when a separate full-coverage report supports it, retaining the initial state for provenance.
- **R002.7** Promote relationships only after checking target-key uniqueness, nulls, orphans, subtype mismatches, and semantics.

### R003 — Data safety and reproducibility

- **R003.1** Use synthetic/anonymized data only.
- **R003.2** Exclude secrets, especially `users.password`, from prompts, indexes, and generated examples; use safe placeholders only if needed for loading.
- **R003.3** Initialize reproducibly from versioned DDL, raw data/import scripts, and relationship metadata.
- **R003.4** Record dataset/schema versions, row counts, and sampling/subsetting.

### R004 — Evaluation set

- **R004.1** Create approximately 100–200 NL evaluation queries with reference SQL and expected results, covering filters, joins (including subtype-aware), aggregations, dates, and supported multi-table questions.
- **R004.2** Label unsupported/ambiguous questions; do not fabricate SQL.
- **R004.3** Every evaluation item has reference SQL and execution outcome on a fixed DB snapshot, or an explicit unsupported/ambiguous label.

### R005 — Training and correction data

- **R005.1** Generate separate synthetic Text-to-SQL and SQL-correction examples from the actual schema/validated relationships.
- **R005.2** Parse and execute generated SQL.
- **R005.3** Keep train/validation/held-out sets separate; split by query/template pattern where practical and prevent held-out question, SQL, or result leakage.
- **R005.4** Independently validate training/correction examples; automated checks detect held-out leakage.

## Acceptance criteria

- **A001** Reproducible database initialization; all 26 tables/columns represented or exclusions documented.
- **A002** Relationship metadata remains separate from DDL; only `validated` edges reach JOIN generation. Subtype predicates are correct.
- **A003** Validation reports target uniqueness, null, matched, orphan, and (where applicable) subtype-mismatch counts; no full-integrity claim without full coverage.
- **A004** Every evaluation item has reference SQL and execution outcome on a fixed DB snapshot, or an explicit unsupported/ambiguous label.
- **A005** Training/correction examples are independently validated; automated checks detect held-out leakage.

## Planning context and observed gaps

- The repository contains all 26 CSV files, a 26-table inferred schema, relationship metadata, source observations, and initial relationship scripts in ignored local `data/raw/` content. These artifacts are not tracked by Git because `.gitignore` excludes `data/raw/`.
- No database importer/initializer, PostgreSQL integration, evaluation set, or training split is present.
- The CSV set is large (approximately 99 million lines including headers across the 26 CSVs); full row contents have not been inspected during planning. The user confirms the current CSV data is anonymized; this is user-provided assurance and was not independently audited during planning.
- The target database is PostgreSQL (user-selected). The input CSV directory is `data/raw/azraq/` (user-confirmed to match the repository). PostgreSQL version and local runtime availability remain unknown.
