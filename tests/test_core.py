from datetime import date
from decimal import Decimal

import pytest

from lightning.core import codes, dates, money, refs
from lightning.core.errors import ValidationError
from lightning.core.ledger import Effect, PostingLine, validate_posting


class TestMoney:
    def test_parses_user_input(self):
        assert money.to_decimal("1,250.50") == Decimal("1250.50")
        assert money.to_decimal(" 450 ") == Decimal("450")
        assert money.to_decimal("−450") == Decimal("-450")

    @pytest.mark.parametrize("bad", ["", "abc", "1.2.3", "NaN", "inf"])
    def test_rejects_bad_input(self, bad):
        with pytest.raises(ValidationError):
            money.to_decimal(bad)

    def test_rejects_float(self):
        with pytest.raises(ValidationError):
            money.to_decimal(0.1)

    def test_storage_round_trip_is_exact(self):
        for text in ["0.01", "12345678.99", "-0.000001", "0.1", "48.2535"]:
            value = Decimal(text)
            assert money.from_e6(money.to_e6(value)) == value

    def test_float_trap_avoided(self):
        total = sum(money.to_e6(Decimal("0.1")) for _ in range(10))
        assert money.from_e6(total) == Decimal("1.0")

    def test_refuses_precision_loss(self):
        with pytest.raises(ValidationError):
            money.to_e6(Decimal("0.0000001"))

    def test_places(self):
        money.check_places(Decimal("12.34"), 2)
        with pytest.raises(ValidationError):
            money.check_places(Decimal("12.345"), 2)

    def test_format(self):
        assert money.fmt(Decimal("-1234.5")) == "-1,234.50"
        assert money.fmt(Decimal("10"), signed=True) == "+10.00"


class TestDates:
    def test_iso_only(self):
        assert dates.parse_date("2026-12-31") == date(2026, 12, 31)
        for bad in ["31/12/2026", "2026-2-3", "2026-02-30", "", "2026/12/31"]:
            with pytest.raises(ValidationError):
                dates.parse_date(bad)

    def test_month(self):
        assert dates.parse_month("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
        with pytest.raises(ValidationError):
            dates.parse_month("2026-13")


class TestRefsAndCodes:
    def test_ref_format(self):
        ref = refs.format_ref(refs.DocType.OUT, date(2026, 9, 25), 3)
        assert ref == "OUT-2026-09-25-003"
        assert refs.parse_ref(ref) == (refs.DocType.OUT, date(2026, 9, 25), 3)
        assert refs.line_ref(ref, 2) == "OUT-2026-09-25-003/2"
        assert refs.parse_ref("OUT-2026-09-25-1000")[2] == 1000

    def test_codes(self):
        assert codes.validate_account_code("cib-cur-egp") == "CIB-CUR-EGP"
        assert codes.validate_asset_code("stk:comi") == "STK:COMI"
        assert codes.validate_path_code("exp.work.software") == "EXP.WORK.SOFTWARE"
        with pytest.raises(ValidationError):
            codes.validate_account_code("CIB CUR!")
        assert codes.slug("Carrefour Maadi") == "CARREFOUR-MAADI"


class TestPostingRules:
    def test_internal_lines_must_net_to_zero(self):
        lines = [PostingLine.cash(1, 1, Decimal("-100"), Effect.INTERNAL),
                 PostingLine.cash(2, 1, Decimal("90"), Effect.INTERNAL)]
        with pytest.raises(ValidationError, match="net to zero"):
            validate_posting(lines)

    def test_money_in_and_out_need_category(self):
        with pytest.raises(ValidationError, match="category"):
            validate_posting([PostingLine.cash(1, 1, Decimal("-5"), Effect.OUTFLOW)])

    def test_zero_and_inconsistent_lines_rejected(self):
        with pytest.raises(ValidationError):
            validate_posting([PostingLine.cash(1, 1, Decimal("0"), Effect.OPENING)])
        bad = PostingLine(1, 1, Decimal("2"), Effect.OPENING, unit_price=Decimal("3"), amount=Decimal("5"),
                          amount_base=Decimal("5"))
        with pytest.raises(ValidationError, match="quantity x unit price"):
            validate_posting([bad])

    def test_valid_transfer(self):
        validate_posting([PostingLine.cash(1, 1, Decimal("-100"), Effect.INTERNAL),
                          PostingLine.cash(2, 1, Decimal("100"), Effect.INTERNAL)])
