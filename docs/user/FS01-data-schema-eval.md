## FS-01 — Azraq Data, Schema & Evaluation

**Purpose:** Reproducible banking data and leakage-safe SQL training/evaluation.

**Requirements**
- Treat `data/raw/` as the source-data location.
  - `data/raw/azra/*.csv` - data rows
  - `data/raw/azraq-schema.sql` — 26-table DDL and inferred column types.
  - `data/raw/azraq-relationships.yaml` — external relationship metadata, evidence, confidence, subtype filters, and validation policy.
  - `data/raw/azraq.md` — source observations, if present.
- Preserve source table/column names and inferred types; do not invent generic `accounts`/`transactions` tables. The 26 tables are: `branches`, `cities`, `client_locations`, `clients`, `collateral_products`, `collaterals`, `currencies`, `delinquency_tracking`, `districts`, `economic_activities`, `exchange_rates`, `funding_lines`, `groups_members`, `loan_products`, `loan_tranches`, `loan_writeoffs`, `loans`, `manual_schedule_adjustments`, `nsg_meetings`, `regions`, `repayments`, `roles`, `savings_accounts`, `savings_products`, `savings_transactions`, `users`.
- DDL declares no PK/FK constraints. Keep inferred relationships in YAML; never treat them as database-enforced constraints. Preserve endpoints, cardinality, status, confidence, evidence/provenance, and subtype filters. Do not use `needs_review` or merely `inferred` edges for JOIN generation; require reviewed `validated` status.
- Preserve the four profiled `clients.type` ranges as evidence only: Individual 1–2,800,000; Group 2,800,001–3,200,000; NSG 3,200,001–3,400,000; Corporate 3,400,001–4,000,000. Preserve subtype-aware links: `collaterals.owner_id` → `clients.id` (any type); `groups_members.group_id` → `clients.id` (`type='Group'`); `groups_members.member_id` → `clients.id` (`type='Individual'`); `nsg_meetings.group_id` → `clients.id` (`type='NSG'`). Keep all other YAML relationships and evidence.
- Do not overstate integrity: YAML records 1,000-row randomized samples per source for these four links (seed `20261127`, zero null/nonmatch in each sample), plus manual full-file subtype counts; full null/orphan validation is explicitly `not_performed`. Promote relationships only after checking target-key uniqueness, nulls, orphans, subtype mismatches, and semantics.
- Use synthetic/anonymized data only. Exclude secrets, especially `users.password`, from prompts, indexes, and generated examples; use safe placeholders only if needed for loading.
- Initialize reproducibly from versioned DDL, raw data/import scripts, and relationship metadata. Record dataset/schema versions, row counts, and sampling/subsetting.
- Create ~100–200 NL evaluation queries with reference SQL and expected results, covering filters, joins (including subtype-aware), aggregations, dates, and supported multi-table questions. Label unsupported/ambiguous questions; do not fabricate SQL.
- Generate separate synthetic Text-to-SQL and SQL-correction examples from the actual schema/validated relationships. Parse and execute generated SQL. Keep train/validation/held-out sets separate; split by query/template pattern where practical and prevent held-out question, SQL, or result leakage.

**Acceptance criteria**
- Reproducible database initialization; all 26 tables/columns represented or exclusions documented.
- Relationship metadata remains separate from DDL; only `validated` edges reach JOIN generation. Subtype predicates are correct.
- Validation reports target uniqueness, null, matched, orphan, and (where applicable) subtype-mismatch counts; no full-integrity claim without full coverage.
- Every evaluation item has reference SQL and execution outcome on a fixed DB snapshot, or an explicit unsupported/ambiguous label.
- Training/correction examples are independently validated; automated checks detect held-out leakage.
