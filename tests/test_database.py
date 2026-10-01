from lightning.bootstrap import build
from lightning.database.migrator import migrate
from lightning.database.seed import seed


def test_migrations_and_seed_are_idempotent(c):
    assert migrate(c.db) == []
    seed(c.db)
    seed(c.db)
    assert c.db.scalar("SELECT COUNT(*) FROM categories WHERE code = 'EXP.PERSONAL.FOOD'") == 1
    assert c.db.scalar("SELECT COUNT(*) FROM financial_assets WHERE code = 'CASH:EGP'") == 1


def test_seed_never_overwrites_user_edits(c):
    food = c.categories.get_by_code("EXP.PERSONAL.FOOD")
    c.categories.update(food.id, "Groceries")
    seed(c.db)
    assert c.categories.get(food.id).name == "Groceries"


def test_seed_does_not_resurrect_a_renamed_default_category(c):
    education = c.categories.get_by_code("EXP.PERSONAL.EDUCATION")
    c.categories.update(education.id, "Courses", "EXP.PERSONAL.COURSES")
    # Simulate an installation from before the seed marker migration.
    c.db.execute("DELETE FROM settings WHERE key = 'category_seed_version'")
    c.db.execute("DELETE FROM schema_migrations WHERE version = 14")
    assert migrate(c.db) == ["0014_preserve_category_codes (APPLIED)"]

    seed(c.db)

    assert c.categories.repo.get_by_code("EXP.PERSONAL.EDUCATION") is None
    renamed = c.categories.get_by_code("EXP.PERSONAL.COURSES")
    assert renamed.id == education.id and renamed.name == "Courses"


def test_seed_structure(c):
    assert c.assets.get_class_by_code("FUND.GOLD").parent_id == c.assets.get_class_by_code("FUND").id
    work = c.categories.get_by_code("EXP.WORK.SOFTWARE")
    assert work.scope.value == "WORK" and work.default_reimbursable
    assert c.categories.get_by_code("EXP.INVEST.DIVIDEND").income_class.value == "INVESTMENT"
    assert c.categories.get_by_code("EXP.WORK.SALARY").income_class.value == "HOUSEHOLD"


def test_readable_views(setup, c):
    row = c.db.one("SELECT * FROM v_ledger WHERE line_ref LIKE 'OPN-%' ORDER BY line_ref LIMIT 1")
    assert row["account"] == "CIB-CUR-EGP · CIB Current"
    assert row["amount"] == "50000.00"
    balances = {r["account"]: r["balance"] for r in c.db.all("SELECT * FROM v_balances")}
    assert balances["CIB-CD-EGP · CIB CD"] == "5000.00"


def test_money_is_stored_as_exact_integers(setup, c):
    accounts, cats = setup
    for _ in range(10):
        c.transactions.record_outflow("2026-09-10", accounts["cib"].id, "0.10", cats["EXP.PERSONAL.FOOD"].id)
    assert c.reporting.account_balance(accounts["cib"].id) == 50000 - 1
    types = {r[0] for r in c.db.all("SELECT typeof(amount_e6) FROM ledger_entries")}
    assert types == {"integer"}


def test_backup(tmp_path):
    c = build(tmp_path / "x.db")
    path = c.backup_now()
    assert path and path.exists() and path.name.startswith("x_backup_")
    c.db.close()


def test_rollback_keeps_database_clean(c):
    try:
        with c.db.transaction():
            c.db.execute("INSERT INTO settings(key, value, updated_at) VALUES ('tmp','1','now')")
            raise RuntimeError
    except RuntimeError:
        pass
    assert c.db.scalar("SELECT 1 FROM settings WHERE key = 'tmp'") is None
