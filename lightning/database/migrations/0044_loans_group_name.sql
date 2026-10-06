-- "System" was the level-1 name for loan payments and money held for others; people read it as
-- something the app did (Mohab's test: no "System" on screen). A group the user renamed keeps its name.
UPDATE categories SET name = 'Loans & held money' WHERE code = 'EXP.SYSTEM' AND name = 'System';
