-- A DEPOSIT account is a bank-specific CD portfolio. Each certificate is a
-- non-cash financial asset with independent terms and a real purchase entry.
CREATE TABLE cd_certificates (
    id                     INTEGER PRIMARY KEY,
    account_id             INTEGER NOT NULL REFERENCES accounts(id),
    asset_id               INTEGER NOT NULL UNIQUE REFERENCES financial_assets(id),
    name                   TEXT NOT NULL,
    start_date             TEXT NOT NULL CHECK (start_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    lockup_end_date        TEXT NOT NULL CHECK (lockup_end_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    maturity_date          TEXT NOT NULL CHECK (maturity_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    principal_e6           INTEGER NOT NULL CHECK (principal_e6 > 0),
    annual_rate            TEXT NOT NULL CHECK (CAST(annual_rate AS REAL) BETWEEN 0 AND 100),
    interest_method        TEXT NOT NULL CHECK (interest_method IN ('SIMPLE','COMPOUND')),
    payout_frequency       TEXT NOT NULL CHECK (payout_frequency IN ('MONTHLY','QUARTERLY','YEARLY','AT_MATURITY')),
    compounding_frequency  TEXT NOT NULL DEFAULT 'MONTHLY' CHECK (compounding_frequency IN ('MONTHLY','QUARTERLY','YEARLY')),
    destination_account_id INTEGER NOT NULL REFERENCES accounts(id),
    purchase_transaction_id INTEGER NOT NULL UNIQUE REFERENCES transactions(id),
    created_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (start_date < maturity_date),
    CHECK (start_date <= lockup_end_date AND lockup_end_date <= maturity_date),
    CHECK (interest_method <> 'COMPOUND' OR payout_frequency = 'AT_MATURITY'),
    CHECK (destination_account_id <> account_id)
);
CREATE INDEX ix_cd_certificates_account ON cd_certificates(account_id, maturity_date, id);

CREATE TABLE cd_redemptions (
    transaction_id       INTEGER PRIMARY KEY REFERENCES transactions(id),
    certificate_id       INTEGER NOT NULL UNIQUE REFERENCES cd_certificates(id),
    destination_account_id INTEGER NOT NULL REFERENCES accounts(id)
);
