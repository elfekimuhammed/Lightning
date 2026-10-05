CREATE TABLE fx_rate_observations (
    id              INTEGER PRIMARY KEY,
    effective_date  TEXT NOT NULL,
    base            TEXT NOT NULL CHECK (length(base)=3),
    quote           TEXT NOT NULL CHECK (length(quote)=3),
    rate_e12        INTEGER NOT NULL CHECK (rate_e12 > 0),
    fetched_at      TEXT NOT NULL,
    source          TEXT NOT NULL CHECK (source IN ('CBE','FRANKFURTER','WISE','MANUAL')),
    source_id       TEXT NOT NULL DEFAULT '',
    original_quote  TEXT NOT NULL DEFAULT '',
    bid_e12         INTEGER CHECK (bid_e12 IS NULL OR bid_e12 > 0),
    ask_e12         INTEGER CHECK (ask_e12 IS NULL OR ask_e12 > 0),
    UNIQUE (effective_date, base, quote, source, source_id)
);
CREATE INDEX ix_fx_observations_pair_date
    ON fx_rate_observations(base, quote, effective_date DESC);
