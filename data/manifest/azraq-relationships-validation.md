# Azraq relationship validation

- Snapshot: `ba058d581b04d1d75f63ac0a4705d98ea0d8ea54dcf577ee90b58222d082dddc`
- PostgreSQL: `18.7`
- Coverage: **full** over the loaded source and target tables
- Relationship metadata SHA-256: `23f2a0ca888442ac5c35700e3a90f282d4ef5cae4190c3521a3aa9dc94f83865`

All counts are exact for this fixed snapshot. Sample evidence recorded in the YAML remains separate.

| Relationship | Coverage | Source rows | Source nulls | Matched | Orphans | Subtype mismatches | Target rows | Target nulls | Duplicate target keys | Filtered duplicate keys | Status | JOIN eligible |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|
| `client_locations.client_id__clients.id` | full | 13999691 | 0 | 13999691 | 0 | 0 | 4000000 | 0 | 0 | 0 | validated | yes |
| `clients.economic_activity_id__economic_activities.id` | full | 4000000 | 0 | 4000000 | 0 | 0 | 23 | 0 | 0 | 0 | validated | yes |
| `clients.branch_id__branches.id` | full | 4000000 | 0 | 4000000 | 0 | 0 | 35 | 0 | 0 | 0 | validated | yes |
| `clients.city_id__cities.id` | full | 4000000 | 0 | 4000000 | 0 | 0 | 11 | 0 | 0 | 0 | validated | yes |
| `cities.district_id__districts.id` | full | 11 | 0 | 11 | 0 | 0 | 11 | 0 | 0 | 0 | validated | yes |
| `districts.region_id__regions.id` | full | 11 | 0 | 11 | 0 | 0 | 14 | 0 | 0 | 0 | validated | yes |
| `loans.client_id__clients.id` | full | 1540000 | 0 | 1540000 | 0 | 0 | 4000000 | 0 | 0 | 0 | validated | yes |
| `loans.product_id__loan_products.id` | full | 1540000 | 0 | 1540000 | 0 | 0 | 38 | 0 | 0 | 0 | validated | yes |
| `loans.officer_id__users.id` | full | 1540000 | 0 | 1540000 | 0 | 0 | 11000 | 0 | 0 | 0 | needs_review | no |
| `loans.funding_line_id__funding_lines.id` | full | 1540000 | 0 | 1540000 | 0 | 0 | 19 | 0 | 0 | 0 | validated | yes |
| `loan_products.funding_line_id__funding_lines.id` | full | 38 | 0 | 38 | 0 | 0 | 19 | 0 | 0 | 0 | validated | yes |
| `loan_tranches.loan_id__loans.id` | full | 4452238 | 0 | 4452238 | 0 | 0 | 1540000 | 0 | 0 | 0 | validated | yes |
| `loan_writeoffs.loan_id__loans.id` | full | 30000 | 0 | 30000 | 0 | 0 | 1540000 | 0 | 0 | 0 | validated | yes |
| `manual_schedule_adjustments.loan_id__loans.id` | full | 92634 | 0 | 92634 | 0 | 0 | 1540000 | 0 | 0 | 0 | validated | yes |
| `delinquency_tracking.loan_id__loans.id` | full | 1153612 | 0 | 1153612 | 0 | 0 | 1540000 | 0 | 0 | 0 | validated | yes |
| `delinquency_tracking.responsible_user_id__users.id` | full | 1153612 | 0 | 1153612 | 0 | 0 | 11000 | 0 | 0 | 0 | validated | yes |
| `collaterals.product_id__collateral_products.id` | full | 23626291 | 0 | 23626291 | 0 | 0 | 28 | 0 | 0 | 0 | validated | yes |
| `collaterals.owner_id__clients.id` | full | 23626291 | 0 | 23626291 | 0 | 0 | 4000000 | 0 | 0 | 0 | validated | yes |
| `savings_accounts.client_id__clients.id` | full | 2760000 | 0 | 2760000 | 0 | 0 | 4000000 | 0 | 0 | 0 | validated | yes |
| `savings_accounts.product_id__savings_products.id` | full | 2760000 | 0 | 2760000 | 0 | 0 | 25 | 0 | 0 | 0 | validated | yes |
| `savings_accounts.officer_id__users.id` | full | 2760000 | 0 | 2760000 | 0 | 0 | 11000 | 0 | 0 | 0 | needs_review | no |
| `savings_transactions.savings_account_id__savings_accounts.id` | full | 21998 | 0 | 21998 | 0 | 0 | 2760000 | 0 | 0 | 0 | validated | yes |
| `groups_members.group_id__clients.id` | full | 3200000 | 0 | 3200000 | 0 | 0 | 4000000 | 0 | 0 | 0 | validated | yes |
| `groups_members.member_id__clients.id` | full | 3200000 | 0 | 3200000 | 0 | 0 | 4000000 | 0 | 0 | 0 | validated | yes |
| `nsg_meetings.group_id__clients.id` | full | 2399988 | 0 | 2399988 | 0 | 0 | 4000000 | 0 | 0 | 0 | validated | yes |
| `users.role_id__roles.id` | full | 11000 | 0 | 11000 | 0 | 0 | 30 | 0 | 0 | 0 | validated | yes |
| `users.branch_id__branches.id` | full | 11000 | 0 | 11000 | 0 | 0 | 35 | 0 | 0 | 0 | validated | yes |
| `exchange_rates.from_currency_id__currencies.id` | full | 50 | 0 | 50 | 0 | 0 | 50 | 0 | 0 | 0 | validated | yes |
| `exchange_rates.to_currency_id__currencies.id` | full | 50 | 0 | 50 | 0 | 0 | 50 | 0 | 0 | 0 | validated | yes |

A `validated` status controls JOIN generation; metadata still does not create database constraints.
