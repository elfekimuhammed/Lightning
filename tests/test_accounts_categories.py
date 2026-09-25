from decimal import Decimal

import pytest

from lightning.categories.domain import Movement
from lightning.core.errors import ConflictError, ValidationError
from lightning.transactions.domain import TxnFilter


class TestAccounts:
    def test_codes_are_suggested_and_unique(self, c):
        a = c.account_flows.open_account("CIB Current", "BANK", "2026-09-01", institution="CIB")
        b = c.account_flows.open_account("CIB Payroll", "BANK", "2026-09-01", institution="CIB")
        assert a.code == "CIB-CUR-EGP" and b.code == "CIB-CUR-EGP-2"
        assert a.label == "CIB-CUR-EGP · CIB Current"

    def test_duplicate_manual_code_rejected(self, c):
        c.account_flows.open_account("A", "BANK", "2026-09-01", code="MY-BANK")
        with pytest.raises(ConflictError):
            c.account_flows.open_account("B", "BANK", "2026-09-01", code="my-bank")

    def test_opening_balance_is_a_transaction(self, c):
        a = c.account_flows.open_account("CIB Current", "BANK", "2026-09-01", "50,000")
        assert c.reporting.account_balance(a.id) == Decimal("50000")
        found, total = c.transactions.find(TxnFilter())
        assert total == 1 and found[0].ref == "OPN-2026-09-01-001"

    def test_debt_accounts_are_not_offered(self, c):
        for retired in ("CREDIT_CARD", "LOAN", "PAYABLE"):
            with pytest.raises(ValidationError):
                c.account_flows.open_account("X", retired, "2026-09-01")

    def test_opening_balance_cannot_be_negative(self, c):
        with pytest.raises(ValidationError, match="negative"):
            c.account_flows.open_account("Wallet", "CASH", "2026-09-01", "-5")

    def test_cash_class_follows_where_cash_sits(self, c):
        wallet = c.account_flows.open_account("Wallet", "CASH", "2026-09-01", "100")
        bank = c.account_flows.open_account("Bank", "BANK", "2026-09-01", "200")
        cd = c.account_flows.open_account("CIB CD", "DEPOSIT", "2026-09-01", "300")
        classes = {c.assets.get_class(a.cash_class_id).code for a in (wallet, bank, cd)}
        assert classes == {"CASH.PHYSICAL", "CASH.BANK", "DEPOSIT.CD"}
        assert c.accounts.reporting_group(bank) == "Liquid Cash › Bank Balance"
        assert c.accounts.reporting_group(cd) == "Deposits › CDs / Time Deposits"

    def test_group_follows_type_on_edit(self, c):
        a = c.account_flows.open_account("QNB", "DEPOSIT", "2026-09-01", "100")
        a = c.account_flows.update_account(a.id, "QNB Savings", "BANK", "2026-09-01", "100")
        assert c.assets.get_class(a.cash_class_id).code == "CASH.BANK"

    def test_start_date_cannot_move_past_existing_transactions(self, setup, c):
        accounts, cats = setup
        c.transactions.record_outflow("2026-09-10", accounts["wallet"].id, "5", cats["EXP.PERSONAL.FOOD"].id)
        with pytest.raises(ValidationError, match="2026-09-10"):
            c.account_flows.update_account(accounts["wallet"].id, "Wallet", "CASH", "2026-09-11", "1200")
        c.account_flows.update_account(accounts["wallet"].id, "Wallet", "CASH", "2026-09-10", "1200")

    def test_editing_opening_balance_and_date(self, c):
        a = c.account_flows.open_account("Bank", "BANK", "2026-09-01", "100")
        c.account_flows.update_account(a.id, "Bank", "BANK", "2026-08-15", "250")
        assert c.reporting.account_balance(a.id) == Decimal("250")
        assert c.reporting.account_balance(a.id, "2026-08-14") == Decimal("0")
        opening = c.transactions.get(c.transactions.repo.opening_txn_id(a.id))
        assert opening.ref == "OPN-2026-09-01-001"  # ref never changes
        assert opening.date == "2026-08-15"
        c.account_flows.update_account(a.id, "Bank", "BANK", "2026-08-15", "")
        assert c.reporting.account_balance(a.id) == Decimal("0")

    def test_generated_codes_keep_whole_words(self, c):
        a = c.account_flows.open_account("Cash at hand", "CASH", "2026-09-01")
        assert a.code == "CASH-AT-HAND-CSH-EGP"

    def test_deactivate_requires_zero_balance(self, setup, c):
        accounts, cats = setup
        with pytest.raises(ConflictError, match="Move the balance"):
            c.account_flows.deactivate(accounts["wallet"].id)
        assert c.account_flows.deactivate(accounts["thndr"].id).active is False
        with pytest.raises(ValidationError, match="inactive"):
            c.transactions.record_transfer("2026-09-10", accounts["cib"].id, accounts["thndr"].id, "10")

    def test_foreign_currency_waits_for_m4(self, c):
        with pytest.raises(ValidationError, match="M4"):
            c.account_flows.open_account("USD", "BANK", "2026-09-01", currency="USD")

    def test_last4_only(self, c):
        with pytest.raises(ValidationError):
            c.account_flows.open_account("Bank", "BANK", "2026-09-01", last4="4111111111111111")

    def test_account_cannot_start_in_the_future(self, c):
        with pytest.raises(ValidationError, match="future"):
            c.account_flows.open_account("Bank", "BANK", "2027-01-01")

    def test_rename_is_found_by_search_immediately(self, setup, c):
        accounts, cats = setup
        c.transactions.record_outflow("2026-09-10", accounts["cib"].id, "10", cats["EXP.PERSONAL.FOOD"].id)
        c.account_flows.update_account(accounts["cib"].id, "Main Bank", "BANK", "2026-09-01", "50000",
                                       institution="CIB", code="CIB-MAIN-EGP")
        assert c.transactions.find(TxnFilter(search="CIB-MAIN-EGP"))[1] == 2  # opening + outflow
        assert c.transactions.find(TxnFilter(search="CIB-CUR-EGP"))[1] == 0


class TestCategories:
    def test_child_inherits_direction_and_scope(self, c):
        work = c.categories.get_by_code("EXP.WORK")
        cat = c.categories.create(work.id, "Coworking Space")
        assert cat.code == "EXP.WORK.COWORKING_SPACE"
        assert cat.movement.value == "OUTFLOW" and cat.scope.value == "WORK" and cat.default_reimbursable

    def test_full_code_accepted(self, c):
        personal = c.categories.get_by_code("EXP.PERSONAL")
        assert c.categories.create(personal.id, "Pets", "EXP.PERSONAL.PETS").code == "EXP.PERSONAL.PETS"

    def test_arabic_name_needs_a_code(self, c):
        personal = c.categories.get_by_code("EXP.PERSONAL")
        with pytest.raises(ValidationError):
            c.categories.create(personal.id, "مواصلات")
        assert c.categories.create(personal.id, "مواصلات", "MICROBUS").name == "مواصلات"

    def test_categories_stop_at_l2(self, c):
        food = c.categories.get_by_code("EXP.PERSONAL.FOOD")
        with pytest.raises(ValidationError, match="stop at L2"):
            c.categories.create(food.id, "Groceries")
        assert all(category.depth == 2 for category in c.categories.pickable())
        assert all(category.depth <= 2 for _, items in c.categories.groups() for category in items)
        assert [group.name for group, _ in c.categories.groups()] == ["Personal", "Work", "Investment"]

    def test_category_suggestions_flag_near_duplicates(self, c):
        matches = c.categories.suggestions("Food and Groceries", c.categories.get_by_code("EXP.PERSONAL").id)
        assert matches and matches[0][0].code == "EXP.PERSONAL.FOOD"

    def test_roots_and_system_categories_are_protected(self, c):
        with pytest.raises(ValidationError):
            c.categories.update(c.categories.get_by_code("EXP").id, "Expenses", active=False)
        with pytest.raises(ValidationError):
            c.categories.update(c.categories.get_by_code("EXP.UNACCOUNTED").id, "X", code="OOPS")

    def test_inactive_hidden_from_forms(self, c):
        food = c.categories.get_by_code("EXP.PERSONAL.FOOD")
        c.categories.update(food.id, food.name, active=False)
        assert food.id not in {x.id for x in c.categories.pickable(Movement.OUTFLOW)}
        personal = c.categories.get_by_code("EXP.PERSONAL")
        c.categories.update(personal.id, personal.name, active=False)
        dining = c.categories.get_by_code("EXP.PERSONAL.DINING")
        assert dining.id not in {x.id for x in c.categories.pickable(Movement.OUTFLOW)}
