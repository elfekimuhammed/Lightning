from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Request

from lightning.accounts.domain import AccountType
from lightning.core.dates import fmt_date, parse_date, today
from lightning.core.errors import LightningError, NotFoundError, ValidationError
from lightning.core.money import to_decimal

from ..web import container, redirect, render

router = APIRouter(prefix="/deposits")

FIELDS = ("start_date", "maturity_date", "lockup_end_date", "principal", "annual_rate",
          "interest_method", "compounding_frequency", "payout_frequency", "destination_account_id")
METHODS = {"SIMPLE": "Simple", "COMPOUND": "Compound"}
COMPOUNDING_FREQUENCIES = {"MONTHLY": "Monthly", "QUARTERLY": "Quarterly", "YEARLY": "Yearly"}
FREQUENCIES = {"MONTHLY": "Monthly", "QUARTERLY": "Quarterly", "YEARLY": "Yearly",
               "AT_MATURITY": "At maturity"}


def _field(term, name, default=""):
    if isinstance(term, dict):
        value = term.get(name, default)
    else:
        value = getattr(term, name, default)
    return default if value is None else value


def _text_date(value):
    if isinstance(value, date):
        return fmt_date(value)
    return str(value or "")


def _account(c, account_id: int):
    account = c.accounts.get(account_id)
    if account.account_type != AccountType.DEPOSIT:
        raise NotFoundError("Deposit account not found.")
    return account


def _values(term=None):
    values = {"start_date": "", "maturity_date": "", "lockup_end_date": "", "principal": "",
              "annual_rate": "", "interest_method": "SIMPLE", "compounding_frequency": "MONTHLY",
              "payout_frequency": "AT_MATURITY",
              "destination_account_id": ""}
    if term is not None:
        for key in FIELDS:
            value = _field(term, key)
            if key in {"start_date", "maturity_date", "lockup_end_date"}:
                value = _text_date(value)
            elif key == "destination_account_id" and value != "":
                value = str(value)
            values[key] = str(value)
    return values


def _page(request: Request, account_id: int, values, error="", status_code=200):
    c = container(request)
    account = _account(c, account_id)
    withdrawal = None
    try:
        maturity = parse_date(values["maturity_date"], "maturity_date")
        lockup = parse_date(values["lockup_end_date"], "lockup_end_date") if values["lockup_end_date"] else maturity
        principal = to_decimal(values["principal"], "principal")
        cd_class = c.assets.get_class_by_code("DEPOSIT.CD")
        factor = c.investments.liquidation_factors()[cd_class.id]
        if today() < lockup:
            withdrawal = {"state": "locked", "date": fmt_date(lockup)}
        elif today() >= maturity:
            withdrawal = {"state": "matured", "amount": principal}
        else:
            withdrawal = {"state": "estimate", "amount": principal * factor / 100, "factor": factor}
    except (LightningError, KeyError, ValueError):
        pass
    return render(request, "deposits/detail.html", status_code=status_code, account=account,
                  values=values, error=error,
                  withdrawal=withdrawal,
                  destinations=[a for a in c.accounts.list(active_only=True)
                                if a.id != account_id and a.account_type in {AccountType.CASH, AccountType.BANK}
                                and a.currency == account.currency])


@router.get("/{account_id:int}")
async def detail(request: Request, account_id: int):
    c = container(request)
    _account(c, account_id)
    try:
        term = c.deposits.get(account_id)
    except NotFoundError:
        term = None
    return _page(request, account_id, _values(term))


@router.post("/{account_id:int}")
async def save(request: Request, account_id: int):
    c = container(request)
    account = _account(c, account_id)
    form = await request.form()
    values = {key: str(form.get(key, "")).strip() for key in FIELDS}
    try:
        start = parse_date(values["start_date"], "start_date")
        maturity = parse_date(values["maturity_date"], "maturity_date")
        if maturity <= start:
            raise ValidationError("Maturity must be after the start date.", "maturity_date")
        lockup = parse_date(values["lockup_end_date"], "lockup_end_date") if values["lockup_end_date"] else maturity
        if lockup < start or lockup > maturity:
            raise ValidationError("Earliest withdrawal must be between the start and maturity dates.",
                                  "lockup_end_date")
        principal = to_decimal(values["principal"], "principal")
        if principal <= 0:
            raise ValidationError("Principal must be greater than zero.", "principal")
        annual_rate = to_decimal(values["annual_rate"], "annual_rate")
        if annual_rate < 0 or annual_rate > 100:
            raise ValidationError("Enter an annual rate from 0 to 100 percent.", "annual_rate")
        method = values["interest_method"]
        compounding_frequency = values["compounding_frequency"]
        frequency = values["payout_frequency"]
        if method not in METHODS:
            raise ValidationError("Choose simple or compound interest.", "interest_method")
        if compounding_frequency not in COMPOUNDING_FREQUENCIES:
            raise ValidationError("Choose monthly, quarterly, or yearly compounding.", "compounding_frequency")
        if frequency not in FREQUENCIES:
            raise ValidationError("Choose a payout schedule.", "payout_frequency")
        if method == "COMPOUND" and frequency != "AT_MATURITY":
            raise ValidationError("Compound interest is paid at maturity only.", "payout_frequency")
        destination_id = int(values["destination_account_id"]) if values["destination_account_id"].isdigit() else None
        if destination_id is None:
            raise ValidationError("Choose a destination bank or cash account.", "destination_account_id")
        destination = c.accounts.require_usable(destination_id, "destination_account_id")
        if (destination.id == account.id or destination.account_type not in {AccountType.CASH, AccountType.BANK}
                or destination.currency != account.currency):
            raise ValidationError("Choose an active bank or cash account in the same currency.",
                                  "destination_account_id")
        c.deposits.save(account_id, fmt_date(start), fmt_date(maturity), principal, annual_rate, method,
                        frequency, destination_id, lockup_end_date=fmt_date(lockup),
                        compounding_frequency=compounding_frequency)
    except (LightningError, ValueError) as exc:
        message = exc.message if isinstance(exc, LightningError) else "Choose a valid destination account."
        return _page(request, account_id, values, message, 400)
    return redirect(f"/deposits/{account_id}", "CD terms saved. No ledger transaction was created.")


@router.post("/{account_id:int}/delete")
async def delete(request: Request, account_id: int):
    c = container(request)
    _account(c, account_id)
    await request.form()  # consume the protected form body before the service call
    c.deposits.delete(account_id)
    return redirect(f"/deposits/{account_id}", "CD terms removed.")
