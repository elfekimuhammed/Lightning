"""Posting rules — the heart of the financial core. Pure Python, no database.

Every transaction (the document the user sees) is stored as one or more ledger lines.
All balances and reports are derived from ledger lines only.

Effects:
- INFLOW    value entering your finances (salary, interest)       -> needs an INFLOW category
- OUTFLOW   value leaving your finances (groceries, fees)         -> needs an OUTFLOW category
- INTERNAL  value moving inside your finances (transfers, buys)   -> must net to zero
- OPENING   balance that existed before you started tracking      -> no category

Net-worth equation (per period):
    closing = opening + inflows - outflows + revaluation + new balances added
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from .errors import ValidationError
from .money import ONE, ZERO, decimal_places


class Effect(StrEnum):
    INFLOW = "INFLOW"
    OUTFLOW = "OUTFLOW"
    INTERNAL = "INTERNAL"
    OPENING = "OPENING"


@dataclass(frozen=True)
class PostingLine:
    account_id: int
    asset_id: int
    quantity: Decimal  # signed units of the asset (for cash: the amount)
    effect: Effect
    unit_price: Decimal = ONE  # price or cost per unit, in the asset's currency
    fx_rate: Decimal = ONE  # asset currency -> base currency, fixed at transaction date
    category_id: int | None = None
    claim_id: int | None = None
    memo: str = ""
    amount: Decimal = field(default=ZERO)  # quantity x unit_price (asset currency)
    amount_base: Decimal = field(default=ZERO)  # amount x fx_rate (base currency, EGP)

    @staticmethod
    def cash(
        account_id: int,
        asset_id: int,
        amount: Decimal,
        effect: Effect,
        category_id: int | None = None,
        memo: str = "",
        fx_rate: Decimal = ONE,
    ) -> "PostingLine":
        """A cash line: quantity == amount, unit price 1."""
        return PostingLine(
            account_id=account_id,
            asset_id=asset_id,
            quantity=amount,
            unit_price=ONE,
            fx_rate=fx_rate,
            effect=effect,
            category_id=category_id,
            memo=memo,
            amount=amount,
            amount_base=_round6(amount * fx_rate),
        )


def _round6(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"))


def validate_posting(lines: list[PostingLine]) -> None:
    """Raise ValidationError unless the lines form a valid posting."""
    if not lines:
        raise ValidationError("A transaction needs at least one line.")
    internal_total = ZERO
    for i, line in enumerate(lines, start=1):
        if line.quantity == ZERO:
            raise ValidationError(f"Line {i}: amount cannot be zero.", "amount")
        for name in ("quantity", "unit_price", "fx_rate", "amount", "amount_base"):
            if decimal_places(getattr(line, name)) > 6:
                raise ValidationError(f"Line {i}: {name} has more than 6 decimal places.")
        if line.unit_price < ZERO or line.fx_rate <= ZERO:
            raise ValidationError(f"Line {i}: price and exchange rate must be positive.")
        if line.amount != _round6(line.quantity * line.unit_price):
            raise ValidationError(f"Line {i}: amount must equal quantity x unit price.")
        if line.amount_base != _round6(line.amount * line.fx_rate):
            raise ValidationError(f"Line {i}: base amount must equal amount x exchange rate.")
        if line.effect in (Effect.INFLOW, Effect.OUTFLOW) and line.category_id is None:
            raise ValidationError(f"Line {i}: money in and money out need a category.", "category")
        if line.effect == Effect.OPENING and line.category_id is not None:
            raise ValidationError(f"Line {i}: opening balances do not take a category.")
        if line.effect == Effect.INTERNAL:
            internal_total += line.amount_base
    if internal_total != ZERO:
        raise ValidationError(
            f"Internal movements must net to zero (they net to {internal_total})."
        )
