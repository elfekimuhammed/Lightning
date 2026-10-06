-- Multiple devices: one stable ID per ledger, set when the home first pairs a device. A returned copy must carry
-- the same ID before the home accepts it; a copy of another profile is refused even with the right key.
CREATE TABLE profile_identity (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    profile_id TEXT NOT NULL CHECK (length(profile_id) = 36)
);
