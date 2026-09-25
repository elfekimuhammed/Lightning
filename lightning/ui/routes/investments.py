from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Request

from lightning.core.dates import fmt_date, parse_date, today
from lightning.core.errors import LightningError, NotFoundError
from lightning.core.refs import DocType
from lightning.core.money import ZERO, to_decimal

from ..web import container, redirect, render
from ...assets.catalog import instruments

router = APIRouter(prefix="/investments")

KINDS = {
    "buy": ("Buy", "Units in, cash out — at cost, fees included."),
    "sell": ("Sell", "Units out, cash in — what you receive after fees."),
    "dividend": ("Dividend", "Cash paid to you by an investment you hold."),
    "holding": ("Add a holding you already own", "Units you had when you started tracking, and what you paid in total."),
}
FIELDS = ("date", "account_id", "asset_id", "quantity", "price", "fees", "fees_included", "cash_account_id", "amount", "total_cost", "total",
          "notes", "is_others", "whom")


def _int(value) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


@router.get("")
async def portfolio(request: Request):
    c = container(request)
    day = fmt_date(today())
    p = c.investments.portfolio(day)
    custody = {(row["account_id"], row["asset_id"]): row["units"]
               for row in c.money_from_others.investment_positions(day)}
    custody_value = custody_cost = Decimal(0)
    own_by_holding = {}
    for holding in p.open:
        units = custody.get((holding.account_id, holding.asset_id), 0)
        if not units:
            continue
        value = c.reporting.value_of(holding.asset_id, units, day).value
        held_value = value or Decimal(0)
        if value is not None:
            custody_value += value
        if holding.quantity:
            custody_cost += holding.cost_basis * units / holding.quantity
        own_by_holding[f"{holding.account_id}:{holding.asset_id}"] = (holding.value or Decimal(0)) - held_value
    owned_value = p.value - custody_value
    owned_cost = p.cost_basis - custody_cost
    owned_unrealized = owned_value - owned_cost
    return render(request, "investments/index.html", p=p, by_class=p.allocation("asset_class"),
                  by_exposure=p.allocation("exposure"), accounts=c.investments.investment_accounts(),
                  has_assets=bool(c.assets.investments(active_only=True)), owned_value=owned_value,
                  owned_cost=owned_cost, owned_unrealized=owned_unrealized, custody_units=custody,
                  own_by_holding=own_by_holding)


# -- trades -------------------------------------------------------------------
def _form(request: Request, kind: str, values: dict, txn=None, error: LightningError | None = None, status=200):
    c = container(request)
    return render(request, "investments/form.html", status_code=status, kind=kind, title=KINDS[kind][0],
                  hint=KINDS[kind][1], values=values, txn=txn,
                  holding_accounts=c.investments.investment_accounts(), all_accounts=c.accounts.list(active_only=True),
                  assets=c.assets.investments(active_only=True),
                  counterparties=c.counterparties.list_active(),
                  error=error.message if error else "", error_field=(error.field or "") if error else "")


def _save(request: Request, kind: str, v: dict, txn_id: int | None = None):
    c = container(request)
    inv = c.investments
    account, asset, cash = _int(v["account_id"]), _int(v["asset_id"]), _int(v["cash_account_id"])
    owner = None
    if v.get("is_others"):
        party = c.counterparties.resolve(v.get("whom", ""))
        if not party or not party["active"]:
            raise LightningError("Choose an active saved Counterparty in Whom.", "whom")
        owner = party["name"]
    if txn_id:
        txn = inv.update(txn_id, date=v["date"], account_id=account, asset_id=asset, quantity=v["quantity"],
                         price=v["price"], fees=v["fees"], total_fees=v["fees"],
                         fees_included=v.get("fees_included", "1") != "0", total=v["total"], cash_account_id=cash, amount=v["amount"],
                         total_cost=v["total_cost"], notes=v["notes"])
    elif kind == "buy":
        if v["total"].strip():
            txn = inv.buy_total(v["date"], account, asset, v["quantity"], v["total"], cash, v["notes"],
                                v["fees"], v.get("fees_included", "1") != "0")
        elif v["price"].strip():
            txn = inv.buy(v["date"], account, asset, v["quantity"], v["price"], v["fees"], cash, v["notes"])
        else:
            txn = inv.buy_total(v["date"], account, asset, v["quantity"], v["total"], cash, v["notes"],
                                v["fees"], v.get("fees_included", "1") != "0")
    elif kind == "sell":
        if v["total"].strip():
            txn = inv.sell_total(v["date"], account, asset, v["quantity"], v["total"], cash, v["notes"],
                                 v["fees"], v.get("fees_included", "1") != "0")
        elif v["price"].strip():
            txn = inv.sell(v["date"], account, asset, v["quantity"], v["price"], v["fees"], cash, v["notes"])
        else:
            txn = inv.sell_total(v["date"], account, asset, v["quantity"], v["total"], cash, v["notes"],
                                 v["fees"], v.get("fees_included", "1") != "0")
    elif kind == "dividend":
        txn = inv.dividend(v["date"], account, asset, v["amount"], v["notes"])
    else:
        txn = inv.add_holding(account, asset, v["quantity"], v["total_cost"], v["date"] or None, v["notes"])

    quantity = to_decimal(v.get("quantity", "0").replace(",", "") or "0", "quantity")
    signed_units = -quantity if kind == "sell" else (quantity if kind in ("buy", "holding") else ZERO)
    c.money_from_others.sync_investment(txn.id, txn.date, owner, account, asset, signed_units)
    cash_line = next((line for line in txn.lines if c.assets.get_asset(line.asset_id).is_cash), None)
    if cash_line:
        cash_amount = cash_line.quantity
        cash_account_id = cash_line.account_id
        if cash_amount < ZERO and owner:
            available = c.money_from_others.cash_balance(owner, cash_account_id, txn.date)
            cash_amount = -min(abs(cash_amount), max(available, ZERO))
            if cash_amount == ZERO:
                c.money_from_others.sync_transaction(txn.id, txn.date, None, cash_account_id, ZERO, "")
            else:
                c.money_from_others.sync_transaction(txn.id, txn.date, owner, cash_account_id, cash_amount, v["notes"])
        elif owner:
            c.money_from_others.sync_transaction(txn.id, txn.date, owner, cash_account_id, cash_amount, v["notes"])
        else:
            c.money_from_others.sync_transaction(txn.id, txn.date, None, cash_account_id, ZERO, "")
    return txn


@router.get("/new")
async def new_trade(request: Request):
    kind = request.query_params.get("kind", "buy")
    kind = kind if kind in KINDS else "buy"
    qp = request.query_params
    values = {k: "" for k in FIELDS}
    values.update(date="" if kind == "holding" else fmt_date(today()), account_id=qp.get("account", ""),
                  asset_id=qp.get("asset", ""))
    return _form(request, kind, values)


@router.post("/new")
async def create_trade(request: Request):
    kind = request.query_params.get("kind", "buy")
    kind = kind if kind in KINDS else "buy"
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in FIELDS}
    try:
        with container(request).db.transaction():
            txn = _save(request, kind, values)
    except LightningError as exc:
        return _form(request, kind, values, error=exc, status=400)
    return redirect(f"/accounts/{values['account_id']}" if values["account_id"] else "/investments",
                    f"Saved {txn.ref}.")


@router.get("/{txn_id:int}/edit")
async def edit_trade(request: Request, txn_id: int):
    c = container(request)
    txn = c.transactions.get(txn_id)
    values = {k: "" for k in FIELDS}
    found = c.investments.values_of(txn_id)
    if not found.get("kind") or (txn.type == DocType.OPN and "asset_id" not in found):
        return redirect(f"/transactions/{txn_id}", "This is not an investment transaction.")
    values.update({k: ("" if v is None else str(v)) for k, v in found.items()})
    owner = c.money_from_others.investment_transaction_owner(txn_id)
    values["is_others"] = "1" if owner else ""
    values["whom"] = owner
    return _form(request, found["kind"], values, txn=txn)


@router.post("/{txn_id:int}/edit")
async def update_trade(request: Request, txn_id: int):
    c = container(request)
    txn = c.transactions.get(txn_id)
    kind = c.investments.values_of(txn_id).get("kind", "buy")
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in FIELDS}
    try:
        with c.db.transaction():
            txn = _save(request, kind, values, txn_id=txn_id)
    except LightningError as exc:
        return _form(request, kind, values, txn=txn, error=exc, status=400)
    return redirect("/investments", f"Saved {txn.ref}.")


# -- investments (what you can hold) -------------------------------------------
def _asset_form(request: Request, values: dict, asset=None, error: LightningError | None = None, status=200):
    c = container(request)
    return render(request, "investments/asset_form.html", status_code=status, values=values, asset=asset,
                  classes=c.assets.investment_classes(), error=error.message if error else "",
                  error_field=(error.field or "") if error else "",
                  catalogue=instruments() if asset is None else [])


@router.get("/assets/new")
async def new_asset(request: Request):
    return _asset_form(request, {"class_code": request.query_params.get("class", "STOCK"), "karat": "21",
                                 "name": "", "symbol": "", "isin": "", "notes": ""})


@router.post("/assets/new")
async def create_asset(request: Request):
    c = container(request)
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in ("name", "class_code", "symbol", "karat", "isin", "notes")}
    try:
        asset = c.assets.create_investment(values["name"], values["class_code"], values["symbol"], values["karat"],
                                           values["isin"], values["notes"])
    except LightningError as exc:
        return _asset_form(request, values, error=exc, status=400)
    back = request.query_params.get("then", "")
    target = f"/investments/new?kind={back}&asset={asset.id}" if back in KINDS else "/investments"
    return redirect(target, f"Added {asset.label}.")


@router.get("/assets/{asset_id:int}/edit")
async def edit_asset(request: Request, asset_id: int):
    c = container(request)
    asset = c.assets.get_asset(asset_id)
    if asset.is_cash:
        raise NotFoundError("That is a currency, not an investment.")
    values = {"name": asset.name, "class_code": c.assets.get_class(asset.asset_class_id).code,
              "notes": asset.notes, "active": "1" if asset.active else ""}
    return _asset_form(request, values, asset=asset)


@router.post("/assets/{asset_id:int}/edit")
async def update_asset(request: Request, asset_id: int):
    c = container(request)
    asset = c.assets.get_asset(asset_id)
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in ("name", "class_code", "notes", "active")}
    try:
        asset = c.assets.update_investment(asset_id, values["name"], values["class_code"], asset.isin or "",
                                           values["notes"], active=bool(values["active"]))
    except LightningError as exc:
        return _asset_form(request, values, asset=asset, error=exc, status=400)
    return redirect("/investments", f"Saved {asset.label}.")


# -- prices ---------------------------------------------------------------------
@router.get("/prices")
async def prices(request: Request, error: str = ""):
    c = container(request)
    raw_day = request.query_params.get("date")
    try:
        day = fmt_date(parse_date(raw_day)) if raw_day else fmt_date(today())
    except LightningError as exc:
        day, error = fmt_date(today()), exc.message
    portfolio = c.investments.portfolio(day)
    held = {p.asset_id: p for p in portfolio.open}
    rows = []
    for asset in c.assets.investments(active_only=True):
        valuation = c.reporting.value_of(asset.id, 1, day)
        rows.append({"asset": asset, "held": held.get(asset.id), "price": valuation.price,
                     "price_date": valuation.price_date, "source": valuation.source})
    rows.sort(key=lambda r: (r["held"] is None, r["asset"].name))
    return render(request, "investments/prices.html", rows=rows, day=day, error=error,
                  pending=c.reevaluations.pending_prices())


@router.post("/prices")
async def save_prices(request: Request):
    c = container(request)
    form = await request.form()
    day = str(form.get("date", "")) or fmt_date(today())
    values = {int(k[2:]): str(v) for k, v in form.items() if k.startswith("p_") and k[2:].isdigit()}
    try:
        count = c.assets.set_prices(day, values)
        for key, raw in form.items():
            if not key.startswith("rp_") or not str(raw).strip():
                continue
            asset_text, checkpoint = key[3:].split("_", 1)
            c.reevaluations.record_manual_price(int(asset_text), checkpoint,
                                                to_decimal(str(raw), "price"))
            count += 1
        c.reevaluations.process_due()
    except LightningError as exc:
        return redirect(f"/investments/prices?date={day}", exc.message)
    return redirect("/investments", f"Saved {count} price input{'s' if count != 1 else ''}; reevaluation catch-up completed." if count
                    else "No prices entered.")


@router.get("/reevaluations")
async def reevaluations_page(request: Request):
    c = container(request)
    return render(request, "investments/reevaluations.html", rows=c.reevaluations.history(),
                  pending=c.reevaluations.pending_prices())
