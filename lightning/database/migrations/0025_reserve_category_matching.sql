ALTER TABLE cash_reserves ADD COLUMN category_id INTEGER REFERENCES categories(id);
