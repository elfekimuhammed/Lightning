-- CD terms are projections only; actual balances and cash movements remain in the ledger.
CREATE TABLE cd_terms (
    account_id             INTEGER PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
    start_date             TEXT NOT NULL CHECK (start_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    lockup_end_date        TEXT NOT NULL CHECK (lockup_end_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    maturity_date          TEXT NOT NULL CHECK (maturity_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    principal_e6           INTEGER NOT NULL CHECK (principal_e6 > 0),
    annual_rate            TEXT NOT NULL CHECK (CAST(annual_rate AS REAL) BETWEEN 0 AND 100),
    interest_method        TEXT NOT NULL CHECK (interest_method IN ('SIMPLE','COMPOUND')),
    payout_frequency       TEXT NOT NULL CHECK (payout_frequency IN ('MONTHLY','QUARTERLY','YEARLY','AT_MATURITY')),
    compounding_frequency  TEXT NOT NULL DEFAULT 'MONTHLY' CHECK (compounding_frequency IN ('MONTHLY','QUARTERLY','YEARLY')),
    destination_account_id INTEGER NOT NULL REFERENCES accounts(id),
    CHECK (start_date < maturity_date),
    CHECK (start_date <= lockup_end_date AND lockup_end_date <= maturity_date),
    CHECK (interest_method <> 'COMPOUND' OR payout_frequency = 'AT_MATURITY'),
    CHECK (destination_account_id <> account_id)
);
