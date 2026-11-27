-- Inferred from each CSV header and its first 10 data rows.
-- Types are sample-based; no keys or relationships are asserted.

CREATE TABLE branches (
    id BIGINT,
    name TEXT
);

CREATE TABLE cities (
    id BIGINT,
    name TEXT,
    district_id BIGINT
);

CREATE TABLE client_locations (
    id BIGINT,
    client_id BIGINT,
    latitude NUMERIC,
    longitude NUMERIC,
    recorded_at TIMESTAMP
);

CREATE TABLE clients (
    id BIGINT,
    type TEXT,
    name TEXT,
    registration_date DATE,
    economic_activity_id BIGINT,
    branch_id BIGINT,
    city_id BIGINT
);

CREATE TABLE collateral_products (
    id BIGINT,
    name TEXT,
    description TEXT
);

CREATE TABLE collaterals (
    id BIGINT,
    product_id BIGINT,
    owner_id BIGINT,
    value BIGINT,
    description TEXT
);

CREATE TABLE currencies (
    id BIGINT,
    code TEXT,
    name TEXT
);

CREATE TABLE delinquency_tracking (
    id BIGINT,
    loan_id BIGINT,
    event_date DATE,
    late_amount NUMERIC,
    late_interest NUMERIC,
    late_days BIGINT,
    description TEXT,
    responsible_user_id BIGINT
);

CREATE TABLE districts (
    id BIGINT,
    name TEXT,
    region_id BIGINT
);

CREATE TABLE economic_activities (
    id BIGINT,
    name TEXT
);

CREATE TABLE exchange_rates (
    id BIGINT,
    from_currency_id BIGINT,
    to_currency_id BIGINT,
    rate NUMERIC,
    date DATE
);

CREATE TABLE funding_lines (
    id BIGINT,
    name TEXT
);

CREATE TABLE groups_members (
    group_id BIGINT,
    member_id BIGINT
);

CREATE TABLE loan_products (
    id BIGINT,
    name TEXT,
    interest_method TEXT,
    interest_rate NUMERIC,
    max_amount BIGINT,
    min_amount BIGINT,
    duration_months BIGINT,
    grace_period BIGINT,
    funding_line_id BIGINT
);

CREATE TABLE loan_tranches (
    id BIGINT,
    loan_id BIGINT,
    tranche_date DATE,
    amount NUMERIC,
    interest_rate NUMERIC,
    number_of_installments BIGINT,
    grace_period BIGINT
);

CREATE TABLE loan_writeoffs (
    id BIGINT,
    loan_id BIGINT,
    writeoff_date DATE,
    amount NUMERIC,
    reason TEXT
);

CREATE TABLE loans (
    id BIGINT,
    client_id BIGINT,
    product_id BIGINT,
    officer_id BIGINT,
    status TEXT,
    principal_amount NUMERIC,
    disbursed_date DATE,
    maturity_date DATE,
    interest_rate NUMERIC,
    grace_period BIGINT,
    funding_line_id BIGINT,
    credit_insurance_percent NUMERIC
);

CREATE TABLE manual_schedule_adjustments (
    id BIGINT,
    loan_id BIGINT,
    adjustment_date DATE,
    details TEXT
);

CREATE TABLE nsg_meetings (
    id BIGINT,
    group_id BIGINT,
    meeting_date DATE,
    notes TEXT
);

CREATE TABLE regions (
    id BIGINT,
    name TEXT
);

CREATE TABLE repayments (
    id BIGINT,
    loan_id BIGINT,
    payment_date DATE,
    principal_paid NUMERIC,
    interest_paid NUMERIC,
    penalty_paid BIGINT,
    commission_paid NUMERIC
);

CREATE TABLE roles (
    id BIGINT,
    name TEXT
);

CREATE TABLE savings_accounts (
    id BIGINT,
    client_id BIGINT,
    product_id BIGINT,
    officer_id BIGINT,
    balance NUMERIC,
    status TEXT
);

CREATE TABLE savings_products (
    id BIGINT,
    name TEXT,
    interest_rate NUMERIC,
    frequency TEXT,
    overdraft_allowed BOOLEAN,
    term_deposit_period BIGINT
);

CREATE TABLE savings_transactions (
    id BIGINT,
    savings_account_id BIGINT,
    transaction_type TEXT,
    transaction_date DATE,
    amount NUMERIC,
    method TEXT
);

CREATE TABLE users (
    id BIGINT,
    username TEXT,
    password TEXT,
    role_id BIGINT,
    branch_id BIGINT
);
