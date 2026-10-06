-- A planned payment that falls on the Egyptian weekend (Friday, Saturday) can move to the working day
-- before or after. Existing plans keep their dates ('none').
ALTER TABLE planned_items ADD COLUMN weekend_move TEXT NOT NULL DEFAULT 'none'
    CHECK (weekend_move IN ('none', 'before', 'after'));
