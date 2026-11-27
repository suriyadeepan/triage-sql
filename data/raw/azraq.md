# azraq raw data samples and observations

This document summarizes the CSV files under `data/raw/azraq/`. Each table section includes its columns, types inferred from the first 10 data rows, and up to 10 sample records. Types are indicative of these samples and may not capture values elsewhere in a file.

The SQL schema is `azraq-schema.sql`. It contains no declared primary keys or foreign keys. Relationship notes below are candidates based on column names and should be checked against the full data before being treated as constraints.

The `users.password` values are redacted in these samples because they resemble credentials. Other sample values are shown as stored in the CSVs.

## Dataset overview

- Tables / CSV files: 26
- Samples: first 10 data records per CSV (or all records when fewer are available).
- Empty fields, when present, are represented as empty cells.

## Tentative relationship patterns

- Location and organization: `client_locations.client_id` appears to refer to `clients.id`; `clients.economic_activity_id` → `economic_activities.id`; `clients.branch_id` → `branches.id`; `clients.city_id` → `cities.id`; `cities.district_id` → `districts.id`; `districts.region_id` → `regions.id`.
- Loan records: `loans.client_id` → `clients.id`; `loans.product_id` → `loan_products.id`; `loans.officer_id` → `users.id`; `loans.funding_line_id` → `funding_lines.id`.
- Loan details: `repayments.loan_id`, `loan_tranches.loan_id`, `loan_writeoffs.loan_id`, `manual_schedule_adjustments.loan_id`, and `delinquency_tracking.loan_id` appear to refer to `loans.id`; `delinquency_tracking.responsible_user_id` appears to refer to `users.id`.
- Collateral: `collaterals.product_id` appears to refer to `collateral_products.id`; the meaning and target of `collaterals.owner_id` are unclear from the column name and samples.
- Savings: `savings_accounts.client_id` appears to refer to `clients.id`, `product_id` to `savings_products.id`, and `officer_id` to `users.id`; `savings_transactions.savings_account_id` appears to refer to `savings_accounts.id`.
- User lookup fields: `users.role_id` appears to refer to `roles.id`, and `users.branch_id` to `branches.id`.
- Currency lookup fields: `exchange_rates.from_currency_id` and `to_currency_id` appear to refer to `currencies.id`.
- Group-related fields: `nsg_meetings.group_id` and `groups_members.group_id` suggest a group entity, but no standalone group table appears in these CSVs. `groups_members.member_id` may identify clients; this is unverified.

## Tables and samples

### `branches`

**Columns and inferred types:**

`id` (BIGINT), `name` (TEXT)

**Sample records (10):**

| id | name |
| --- | --- |
| 1 | azraq Bank – Abu Dhabi Main Branch, Blue Tower, Khalifa St., Corniche Road, Abu Dhabi |
| 2 | azraq Bank – Al Ain Main Branch, Al Ain Mall area, Al Ain |
| 3 | azraq Bank – Mussaffah Branch, Musaffah Industrial Area, Abu Dhabi |
| 4 | azraq Bank – Al Aweer Express Banking, Ras Al Khor, Dubai |
| 5 | azraq Bank – Burjuman Branch, Bur Dubai (Near Burjuman Metro) |
| 6 | azraq Bank – Dubai Internet City Branch, Sheikh Zayed Road, Dubai |
| 7 | azraq Bank – Ghusais Branch, Amman Street, Dubai |
| 8 | azraq Bank – Muraqqabat Branch, Abu Bakr Al Siddique Road, Dubai |
| 9 | azraq Bank – Sheikh Zayed Road Branch (Al Hawai Tower), DIFC, Dubai |
| 10 | azraq Bank – Ajman Main Branch, near Ajman Gold Souq, Ajman |

### `cities`

**Columns and inferred types:**

`id` (BIGINT), `name` (TEXT), `district_id` (BIGINT)

**Sample records (10):**

| id | name | district_id |
| --- | --- | --- |
| 1 | Abu Dhabi | 1 |
| 2 | Al Ain | 2 |
| 3 | Dubai | 3 |
| 4 | Sharjah | 4 |
| 5 | Ajman | 5 |
| 6 | Ras Al Khaimah | 6 |
| 7 | Doha | 7 |
| 8 | Cairo | 8 |
| 9 | Alexandria | 9 |
| 10 | Giza | 10 |

### `client_locations`

**Columns and inferred types:**

`id` (BIGINT), `client_id` (BIGINT), `latitude` (NUMERIC), `longitude` (NUMERIC), `recorded_at` (TIMESTAMP)

**Sample records (10):**

| id | client_id | latitude | longitude | recorded_at |
| --- | --- | --- | --- | --- |
| 1 | 1 | 25.072461 | 55.404304 | 2024-11-04 02:36:51.398136 |
| 2 | 1 | 15.222062 | 78.269918 | 2025-01-10 21:40:34.039613 |
| 3 | 2 | 25.075005 | 55.283809 | 2024-09-25 17:39:22.805372 |
| 4 | 2 | 24.963732 | 55.167406 | 2024-12-16 10:32:07.135483 |
| 5 | 3 | 30.137645 | 31.075186 | 2025-03-14 11:53:08.828798 |
| 6 | 3 | 25.182285 | 55.200764 | 2025-05-17 11:48:10.871953 |
| 7 | 3 | 25.573547 | 51.336119 | 2025-03-07 12:38:19.373549 |
| 8 | 3 | 25.092311 | 55.602717 | 2025-04-28 04:40:09.058256 |
| 9 | 3 | 30.20446 | 31.340012 | 2024-09-20 18:09:00.417873 |
| 10 | 4 | 30.038593 | 31.160566 | 2024-07-03 06:10:40.464360 |

### `clients`

**Columns and inferred types:**

`id` (BIGINT), `type` (TEXT), `name` (TEXT), `registration_date` (DATE), `economic_activity_id` (BIGINT), `branch_id` (BIGINT), `city_id` (BIGINT)

**Sample records (10):**

| id | type | name | registration_date | economic_activity_id | branch_id | city_id |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Individual | Anthony Johnson | 2024-03-31 | 14 | 2 | 10 |
| 2 | Individual | Karen Donovan | 2024-06-20 | 15 | 3 | 9 |
| 3 | Individual | Megan Stevenson | 2023-03-26 | 8 | 10 | 5 |
| 4 | Individual | Anthony Miller | 2024-11-20 | 2 | 8 | 1 |
| 5 | Individual | Todd Watkins | 2023-06-29 | 22 | 5 | 11 |
| 6 | Individual | Patrick Harris | 2023-08-09 | 21 | 5 | 8 |
| 7 | Individual | Andrea Hughes | 2025-05-17 | 1 | 8 | 1 |
| 8 | Individual | Ryan King | 2022-11-29 | 19 | 3 | 3 |
| 9 | Individual | Robert Mckenzie | 2023-03-31 | 7 | 5 | 2 |
| 10 | Individual | Abigail Ryan | 2023-06-21 | 2 | 10 | 3 |

### `collateral_products`

**Columns and inferred types:**

`id` (BIGINT), `name` (TEXT), `description` (TEXT)

**Sample records (10):**

| id | name | description |
| --- | --- | --- |
| 1 | Residential Real Estate | Primary or secondary homes used to secure mortgage or home equity loans   |
| 2 | Commercial Real Estate | Office buildings, retail, industrial property for business loans   |
| 3 | Land (undeveloped/farm) | Land parcels (agricultural or undeveloped) pledged against loans   |
| 4 | Passenger Vehicles | Cars and small trucks used as collateral for auto or title loans   |
| 5 | Commercial Vehicles | Heavy trucks, buses, logistics vehicles securing business financing   |
| 6 | Industrial Machinery & Equipment | Manufacturing equipment pledged in equipment finance   |
| 7 | Inventory | Raw materials or finished goods held as collateral for working capital   |
| 8 | Accounts Receivable | Outstanding invoices used in invoice discounting or factoring   |
| 9 | Savings Deposits or CDs | Bank deposits or certificates of deposit pledged as collateral   |
| 10 | Stocks and Bonds | Market securities pledged for margin loans or secured lending   |

### `collaterals`

**Columns and inferred types:**

`id` (BIGINT), `product_id` (BIGINT), `owner_id` (BIGINT), `value` (BIGINT), `description` (TEXT)

**Sample records (10):**

| id | product_id | owner_id | value | description |
| --- | --- | --- | --- | --- |
| 1 | 27 | 2934686 | 4289 | Summer keep could ability section. |
| 2 | 12 | 2934686 | 1778 | Major manage son director film imagine explain. |
| 3 | 15 | 2934686 | 2627 | After tree race threat find everything PM. |
| 4 | 27 | 2934686 | 2187 | Exactly indicate him development water check population. |
| 5 | 12 | 2934686 | 1399 | He shake management citizen structure society world. |
| 6 | 10 | 2934686 | 1288 | Hear from election director sister evidence statement. |
| 7 | 1 | 2934686 | 2128 | Size show despite up affect anything part big. |
| 8 | 28 | 2934686 | 2107 | Owner room those model down eye wind treatment. |
| 9 | 28 | 2934686 | 3035 | Financial family end today. |
| 10 | 10 | 2934686 | 1290 | While including sure stuff teacher two positive. |

### `currencies`

**Columns and inferred types:**

`id` (BIGINT), `code` (TEXT), `name` (TEXT)

**Sample records (10):**

| id | code | name |
| --- | --- | --- |
| 1 | USD | United States Dollar |
| 2 | EUR | Euro |
| 3 | GBP | British Pound Sterling |
| 4 | JPY | Japanese Yen |
| 5 | CNY | Chinese Renminbi |
| 6 | AUD | Australian Dollar |
| 7 | CAD | Canadian Dollar |
| 8 | CHF | Swiss Franc |
| 9 | HKD | Hong Kong Dollar |
| 10 | SGD | Singapore Dollar |

### `delinquency_tracking`

**Columns and inferred types:**

`id` (BIGINT), `loan_id` (BIGINT), `event_date` (DATE), `late_amount` (NUMERIC), `late_interest` (NUMERIC), `late_days` (BIGINT), `description` (TEXT), `responsible_user_id` (BIGINT)

**Sample records (10):**

| id | loan_id | event_date | late_amount | late_interest | late_days | description | responsible_user_id |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 2025-08-21 | 330.7 | 2.61 | 41 | Client missed due date due to insufficient balance | 4983 |
| 2 | 2 | 2024-10-06 | 419.8 | 4.69 | 58 | Mobile banking error during payment | 4983 |
| 3 | 3 | 2027-02-22 | 812.61 | 1.65 | 14 | Client disputing interest charges | 4810 |
| 4 | 6 | 2024-09-18 | 228.87 | 4.15 | 85 | Temporary insolvency declared | 141 |
| 5 | 6 | 2027-04-27 | 288.74 | 1.85 | 30 | Delayed collateral liquidation | 141 |
| 6 | 11 | 2024-07-26 | 120.04 | 2.07 | 49 | Death in family affected repayment | 6591 |
| 7 | 11 | 2025-02-04 | 166.63 | 2.75 | 47 | Loan restructuring under discussion | 6591 |
| 8 | 13 | 2024-06-21 | 856.53 | 18.66 | 87 | Borrower account frozen for KYC issues | 3882 |
| 9 | 13 | 2025-12-18 | 542.43 | 2.04 | 15 | Check bounce on due date | 3882 |
| 10 | 13 | 2024-06-29 | 681.3 | 15.35 | 90 | Post-disbursement health emergency | 3882 |

### `districts`

**Columns and inferred types:**

`id` (BIGINT), `name` (TEXT), `region_id` (BIGINT)

**Sample records (10):**

| id | name | region_id |
| --- | --- | --- |
| 1 | Abu Dhabi | 1 |
| 2 | Al Ain | 1 |
| 3 | Dubai | 1 |
| 4 | Sharjah | 1 |
| 5 | Ajman | 1 |
| 6 | Ras Al Khaimah | 1 |
| 7 | Doha | 3 |
| 8 | Cairo | 2 |
| 9 | Alexandria | 2 |
| 10 | Giza | 2 |

### `economic_activities`

**Columns and inferred types:**

`id` (BIGINT), `name` (TEXT)

**Sample records (10):**

| id | name |
| --- | --- |
| 1 | Corporate & Investment Banking |
| 2 | Global Transaction Banking |
| 3 | Islamic Banking |
| 4 | Treasury & Capital Markets |
| 5 | Retail Banking |
| 6 | Business Banking / SME |
| 7 | Wealth & Asset Management |
| 8 | Trading (Retail, FMCG, Commodities, Automotive) |
| 9 | Financial Institutions |
| 10 | Real Estate |

### `exchange_rates`

**Columns and inferred types:**

`id` (BIGINT), `from_currency_id` (BIGINT), `to_currency_id` (BIGINT), `rate` (NUMERIC), `date` (DATE)

**Sample records (10):**

| id | from_currency_id | to_currency_id | rate | date |
| --- | --- | --- | --- | --- |
| 1 | 1 | 2 | 0.87715 | 2025-06-10 |
| 2 | 1 | 3 | 0.73854 | 2025-06-10 |
| 3 | 1 | 4 | 144.87 | 2025-06-10 |
| 4 | 1 | 5 | 7.18210 | 2025-06-10 |
| 5 | 1 | 6 | 1.53330 | 2025-06-10 |
| 6 | 1 | 7 | 1.37052 | 2025-06-10 |
| 7 | 1 | 8 | 0.82279 | 2025-06-10 |
| 8 | 1 | 9 | 7.85409 | 2025-06-10 |
| 9 | 1 | 10 | 1.28715 | 2025-06-10 |
| 10 | 1 | 11 | 1.65525 | 2025-06-10 |

### `funding_lines`

**Columns and inferred types:**

`id` (BIGINT), `name` (TEXT)

**Sample records (10):**

| id | name |
| --- | --- |
| 1 | Import Finance (Letters of Credit) |
| 2 | Export Finance |
| 3 | Receivables Finance (Factoring) |
| 4 | Invoice Discounting |
| 5 | Cheque Discounting |
| 6 | Pre‑shipment Financing |
| 7 | Post‑shipment Financing |
| 8 | Working Capital Overdraft |
| 9 | Term Loans – Commercial |
| 10 | Construction Financing |

### `groups_members`

**Columns and inferred types:**

`group_id` (BIGINT), `member_id` (BIGINT)

**Sample records (10):**

| group_id | member_id |
| --- | --- |
| 3069505 | 62861 |
| 2892084 | 2376713 |
| 2958214 | 1417242 |
| 3128057 | 2206102 |
| 2815139 | 838341 |
| 3173382 | 2490989 |
| 2916061 | 340983 |
| 3031319 | 1168848 |
| 2894771 | 1993059 |
| 3021220 | 1975020 |

### `loan_products`

**Columns and inferred types:**

`id` (BIGINT), `name` (TEXT), `interest_method` (TEXT), `interest_rate` (NUMERIC), `max_amount` (BIGINT), `min_amount` (BIGINT), `duration_months` (BIGINT), `grace_period` (BIGINT), `funding_line_id` (BIGINT)

**Sample records (10):**

| id | name | interest_method | interest_rate | max_amount | min_amount | duration_months | grace_period | funding_line_id |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Personal Loan | Fixed | 12.00 | 50000 | 1000 | 60 | 0 | 8 |
| 2 | Unsecured Personal Loan | Fixed | 18.00 | 30000 | 500 | 48 | 0 | 8 |
| 3 | Secured Personal Loan | Fixed | 10.00 | 100000 | 500 | 60 | 0 | 8 |
| 4 | Debt Consolidation Loan | Fixed | 14.00 | 100000 | 1000 | 84 | 0 | 8 |
| 5 | Auto Loan | Fixed | 7.50 | 100000 | 5000 | 72 | 0 | 8 |
| 6 | Auto Loan Refinance | Fixed | 8.00 | 50000 | 1000 | 60 | 0 | 8 |
| 7 | Home Mortgage (Fixed) | Fixed | 6.50 | 2000000 | 50000 | 360 | 0 | 6 |
| 8 | Home Mortgage (Adjustable) | Variable | 5.50 | 2000000 | 50000 | 360 | 0 | 6 |
| 9 | Home Equity Loan | Fixed | 7.99 | 200000 | 10000 | 180 | 0 | 9 |
| 10 | Home Equity Line of Credit (HELOC) | Variable | 7.00 | 200000 | 5000 | 120 | 0 | 9 |

### `loan_tranches`

**Columns and inferred types:**

`id` (BIGINT), `loan_id` (BIGINT), `tranche_date` (DATE), `amount` (NUMERIC), `interest_rate` (NUMERIC), `number_of_installments` (BIGINT), `grace_period` (BIGINT)

**Sample records (10):**

| id | loan_id | tranche_date | amount | interest_rate | number_of_installments | grace_period |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 3550 | 2023-08-21 | 32208.28 | 6.45 | 361 | 0 |
| 2 | 3550 | 2023-09-20 | 44719.06 | 6.45 | 361 | 0 |
| 3 | 3550 | 2023-10-20 | 74263.17 | 6.45 | 361 | 0 |
| 4 | 3550 | 2023-11-19 | 28231.16 | 6.45 | 361 | 0 |
| 5 | 3550 | 2023-12-19 | 20470.46 | 6.45 | 361 | 0 |
| 6 | 9874 | 2020-07-24 | 18117.67 | 7.03 | 361 | 0 |
| 7 | 9874 | 2020-08-23 | 18070.84 | 7.03 | 361 | 0 |
| 8 | 9874 | 2020-09-22 | 15729.8 | 7.03 | 361 | 0 |
| 9 | 9874 | 2020-10-22 | 18360.24 | 7.03 | 361 | 0 |
| 10 | 9874 | 2020-11-21 | 13112.33 | 7.03 | 361 | 0 |

### `loan_writeoffs`

**Columns and inferred types:**

`id` (BIGINT), `loan_id` (BIGINT), `writeoff_date` (DATE), `amount` (NUMERIC), `reason` (TEXT)

**Sample records (10):**

| id | loan_id | writeoff_date | amount | reason |
| --- | --- | --- | --- | --- |
| 1 | 704979 | 2025-06-22 | 563690.25 | Client imprisonment on unrelated charges |
| 2 | 747577 | 2032-05-08 | 78044.0 | Natural disaster (flood, earthquake) impacted repayment |
| 3 | 1528600 | 2022-09-29 | 186285.34 | High court ruled against recovery rights |
| 4 | 962746 | 2024-05-03 | 815032.14 | Seizure attempted but no recoverable assets found |
| 5 | 1031139 | 2027-06-17 | 4132.27 | Credit bureau listed client as chronic defaulter |
| 6 | 1211773 | 2023-01-22 | 2568.32 | Client moved abroad without trace |
| 7 | 474298 | 2028-11-09 | 95108.34 | Client migrated and cannot be contacted |
| 8 | 893708 | 2022-03-28 | 481563.07 | Client declared missing |
| 9 | 21747 | 2025-09-17 | 237771.17 | Client business affected by economic downturn |
| 10 | 1222718 | 2030-03-29 | 48552.76 | Write-off due to management approval for PR reasons |

### `loans`

**Columns and inferred types:**

`id` (BIGINT), `client_id` (BIGINT), `product_id` (BIGINT), `officer_id` (BIGINT), `status` (TEXT), `principal_amount` (NUMERIC), `disbursed_date` (DATE), `maturity_date` (DATE), `interest_rate` (NUMERIC), `grace_period` (BIGINT), `funding_line_id` (BIGINT), `credit_insurance_percent` (NUMERIC)

**Sample records (10):**

| id | client_id | product_id | officer_id | status | principal_amount | disbursed_date | maturity_date | interest_rate | grace_period | funding_line_id | credit_insurance_percent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 758363 | 7 | 10555 | active | 199892.13 | 2023-08-21 | 2053-09-12 | 6.45 | 0 | 6 | 3.38 |
| 2 | 2751653 | 7 | 4983 | closed | 96542.03 | 2020-07-24 | 2050-08-16 | 7.03 | 0 | 6 | 2.97 |
| 3 | 1017860 | 8 | 4810 | active | 166909.41 | 2021-10-24 | 2051-11-16 | 5.28 | 0 | 6 | 4.83 |
| 4 | 2261252 | 6 | 1229 | active | 17939.48 | 2021-07-21 | 2026-07-25 | 7.63 | 0 | 8 | 2.54 |
| 5 | 990574 | 4 | 8111 | active | 77089.55 | 2024-02-14 | 2031-02-19 | 14.17 | 0 | 8 | 5.52 |
| 6 | 666176 | 5 | 141 | active | 12108.94 | 2023-10-28 | 2029-11-01 | 7.79 | 0 | 8 | 3.81 |
| 7 | 2342424 | 6 | 3427 | defaulted | 39683.21 | 2024-11-25 | 2029-11-29 | 7.87 | 0 | 8 | 3.27 |
| 8 | 3747611 | 19 | 3484 | closed | 78779.19 | 2020-11-14 | 2025-11-18 | 7.53 | 0 | 9 | 5.83 |
| 9 | 2319284 | 12 | 8555 | active | 57387.88 | 2022-07-19 | 2032-07-26 | 10.01 | 6 | 6 | 6.3 |
| 10 | 1845591 | 7 | 815 | active | 77073.68 | 2020-08-02 | 2050-08-25 | 6.36 | 0 | 6 | 4.06 |

### `manual_schedule_adjustments`

**Columns and inferred types:**

`id` (BIGINT), `loan_id` (BIGINT), `adjustment_date` (DATE), `details` (TEXT)

**Sample records (10):**

| id | loan_id | adjustment_date | details |
| --- | --- | --- | --- |
| 1 | 65473 | 2027-01-17 | Corrected schedule after client overpayment |
| 2 | 65473 | 2024-12-31 | Removed duplicate installment entry |
| 3 | 1531582 | 2027-05-27 | Updated schedule after moratorium approval |
| 4 | 804084 | 2025-11-11 | Reduced interest rate after negotiations |
| 5 | 804084 | 2031-08-15 | Reduced interest rate after negotiations |
| 6 | 938739 | 2028-06-23 | Updated schedule after moratorium approval |
| 7 | 996487 | 2025-11-20 | Manually split merged installments |
| 8 | 996487 | 2026-10-16 | Removed holiday overlap in payment schedule |
| 9 | 1241265 | 2026-07-01 | Adjusted schedule after partial prepayment |
| 10 | 867638 | 2025-08-16 | Removed holiday overlap in payment schedule |

### `nsg_meetings`

**Columns and inferred types:**

`id` (BIGINT), `group_id` (BIGINT), `meeting_date` (DATE), `notes` (TEXT)

**Sample records (10):**

| id | group_id | meeting_date | notes |
| --- | --- | --- | --- |
| 1 | 3200001 | 2024-06-15 | Group milestone achieved: 100% repayment. |
| 2 | 3200001 | 2024-07-15 | Officer Brian Johnson reviewed ledger entries. |
| 3 | 3200001 | 2024-08-14 | Monthly contribution discussed and revised to $374. |
| 4 | 3200001 | 2024-09-13 | Monthly contribution discussed and revised to $316. |
| 5 | 3200001 | 2024-10-13 | Success story shared by Nancy. |
| 6 | 3200001 | 2024-11-12 | Reminder: no meeting on Eid. |
| 7 | 3200001 | 2024-12-12 | NSG graduation discussed and planned for January. |
| 8 | 3200001 | 2025-01-11 | Reminded members of upcoming field audit on 2024-09-10. |
| 9 | 3200001 | 2025-02-10 | New goal set: increase savings by 6% in December. |
| 10 | 3200001 | 2025-03-12 | Reviewed savings deposits for the month of January. |

### `regions`

**Columns and inferred types:**

`id` (BIGINT), `name` (TEXT)

**Sample records (10):**

| id | name |
| --- | --- |
| 1 | UAE |
| 2 | Egypt |
| 3 | Pakistan |
| 4 | Qatar |
| 5 | Oman |
| 6 | Bahrain |
| 7 | Kuwait |
| 8 | India |
| 9 | Hong Kong |
| 10 | United Kingdom |

### `repayments`

**Columns and inferred types:**

`id` (BIGINT), `loan_id` (BIGINT), `payment_date` (DATE), `principal_paid` (NUMERIC), `interest_paid` (NUMERIC), `penalty_paid` (BIGINT), `commission_paid` (NUMERIC)

**Sample records (10):**

| id | loan_id | payment_date | principal_paid | interest_paid | penalty_paid | commission_paid |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1 | 2023-08-26 | 9086.01 | 1025.58 | 0 | 0.0 |
| 2 | 1 | 2023-09-25 | 9086.01 | 976.75 | 0 | 0.0 |
| 3 | 1 | 2023-10-27 | 9086.01 | 927.91 | 0 | 0.0 |
| 4 | 1 | 2023-11-28 | 9086.01 | 879.07 | 10 | 0.0 |
| 5 | 1 | 2023-12-26 | 9086.01 | 830.23 | 0 | 0.0 |
| 6 | 1 | 2024-01-21 | 9086.01 | 781.4 | 0 | 90.86 |
| 7 | 1 | 2024-02-27 | 7268.81 | 742.33 | 0 | 72.69 |
| 8 | 1 | 2024-03-29 | 7268.81 | 703.26 | 0 | 0.0 |
| 9 | 1 | 2024-04-28 | 9086.01 | 654.42 | 0 | 0.0 |
| 10 | 1 | 2024-05-27 | 4543.01 | 630.0 | 0 | 0.0 |

### `roles`

**Columns and inferred types:**

`id` (BIGINT), `name` (TEXT)

**Sample records (10):**

| id | name |
| --- | --- |
| 1 | System Administrator |
| 2 | IT Support Officer |
| 3 | Database Administrator |
| 4 | Branch Manager |
| 5 | Loan Officer |
| 6 | Loan Supervisor |
| 7 | Credit Committee Member |
| 8 | Client Relationship Officer |
| 9 | Field Officer |
| 10 | Teller / Cashier |

### `savings_accounts`

**Columns and inferred types:**

`id` (BIGINT), `client_id` (BIGINT), `product_id` (BIGINT), `officer_id` (BIGINT), `balance` (NUMERIC), `status` (TEXT)

**Sample records (10):**

| id | client_id | product_id | officer_id | balance | status |
| --- | --- | --- | --- | --- | --- |
| 1 | 3421720 | 10 | 5244 | 94924.79 | Active |
| 2 | 3138047 | 15 | 7903 | 49428.72 | Active |
| 3 | 3138047 | 23 | 874 | 12591.59 | Active |
| 4 | 3391709 | 13 | 5468 | 27945.88 | Active |
| 5 | 3492777 | 23 | 5453 | 688369.11 | Active |
| 6 | 1611430 | 4 | 10023 | 15372.36 | Dormant |
| 7 | 3706983 | 2 | 10590 | 252727.16 | Active |
| 8 | 2117357 | 2 | 7474 | 19580.31 | Active |
| 9 | 1043233 | 5 | 1679 | 2603.48 | Active |
| 10 | 909610 | 11 | 9942 | 14441.5 | Dormant |

### `savings_products`

**Columns and inferred types:**

`id` (BIGINT), `name` (TEXT), `interest_rate` (NUMERIC), `frequency` (TEXT), `overdraft_allowed` (BOOLEAN), `term_deposit_period` (BIGINT)

**Sample records (10):**

| id | name | interest_rate | frequency | overdraft_allowed | term_deposit_period |
| --- | --- | --- | --- | --- | --- |
| 1 | Basic Savings Account | 0.50 | Monthly | false | 0 |
| 2 | Zero-Balance (No-Min Balance) Account | 0.50 | Monthly | false | 0 |
| 3 | Salary-linked Savings Account | 0.75 | Monthly | false | 0 |
| 4 | High-Yield Online Savings Account | 1.50 | Monthly | false | 0 |
| 5 | Premium/Senior Savings Account | 1.00 | Monthly | false | 0 |
| 6 | Children’s Savings Account | 1.00 | Monthly | false | 0 |
| 7 | Joint Savings Account | 0.60 | Monthly | false | 0 |
| 8 | Health Savings Account (HSA) | 1.20 | Monthly | false | 0 |
| 9 | Money Market Account | 1.25 | Monthly | false | 0 |
| 10 | Fixed Deposit / Time Deposit | 2.00 | Quarterly | false | 12 |

### `savings_transactions`

**Columns and inferred types:**

`id` (BIGINT), `savings_account_id` (BIGINT), `transaction_type` (TEXT), `transaction_date` (DATE), `amount` (NUMERIC), `method` (TEXT)

**Sample records (10):**

| id | savings_account_id | transaction_type | transaction_date | amount | method |
| --- | --- | --- | --- | --- | --- |
| 1 | 740545 | deposit | 2025-01-31 | 673.69 | transfer |
| 2 | 740545 | withdrawal | 2024-08-06 | 591.36 | POS |
| 3 | 740545 | deposit | 2024-03-16 | 422.48 | transfer |
| 4 | 740545 | withdrawal | 2024-05-24 | 459.78 | cash |
| 5 | 740545 | withdrawal | 2024-10-01 | 135.94 | mobile |
| 6 | 740545 | deposit | 2025-01-28 | 728.22 | POS |
| 7 | 740545 | deposit | 2024-07-20 | 598.59 | transfer |
| 8 | 740545 | withdrawal | 2024-07-04 | 769.82 | cash |
| 9 | 740545 | withdrawal | 2024-04-23 | 216.33 | mobile |
| 10 | 740545 | deposit | 2024-02-11 | 36.13 | cash |

### `users`

**Columns and inferred types:**

`id` (BIGINT), `username` (TEXT), `password` (TEXT), `role_id` (BIGINT), `branch_id` (BIGINT)

**Sample records (10):**

| id | username | password | role_id | branch_id |
| --- | --- | --- | --- | --- |
| 1 | zrice | [REDACTED] | 5 | 8 |
| 2 | fmann | [REDACTED] | 7 | 9 |
| 3 | ryantaylor | [REDACTED] | 9 | 8 |
| 4 | joshuasmith | [REDACTED] | 9 | 8 |
| 5 | danielle38 | [REDACTED] | 8 | 2 |
| 6 | dylanchapman | [REDACTED] | 6 | 8 |
| 7 | richardjohnson | [REDACTED] | 9 | 11 |
| 8 | aaronkennedy | [REDACTED] | 7 | 6 |
| 9 | pzamora | [REDACTED] | 8 | 10 |
| 10 | matthewshaffer | [REDACTED] | 5 | 9 |
