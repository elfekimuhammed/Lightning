from __future__ import annotations

from fastapi import APIRouter, Request

from lightning.core.dates import fmt_date, today
from lightning.core.errors import LightningError, NotFoundError
from lightning.core.refs import DocType

from ..web import container, redirect, render
from ...assets.catalog import instruments

router = APIRouter(prefix="/investments")

KINDS = {
    "buy": ("Buy", "Units in, cash out — at cost, fees included."),
    "sell": ("Sell", "Units out, cash in — what you receive after fees."),
    "dividend": ("Dividend", "Cash paid to you by an investment you hold."),
    "holding": ("Add a holding you already own", "Units you had when you started tracking, and what you paid in total."),
}
FIELDS = ("date", "account_id", "asset_id", "quantity", "price", "fees", "cash_account_id", "amount", "total_cost", "total",
          "notes")


def _int(value) -> int | None:
    text = str(value or "").strip()
    return int(text) if text.isdigit() else None


@router.get("")
async def portfolio(request: Request):
    c = container(request)
    p = c.investments.portfolio(fmt_date(today()))
    return render(request, "investments/index.html", p=p, by_class=p.allocation("asset_class"),
                  by_exposure=p.allocation("exposure"), accounts=c.investments.investment_accounts(),
                  has_assets=bool(c.assets.investments(active_only=True)))


# -- trades -------------------------------------------------------------------
def _form(request: Request, kind: str, values: dict, txn=None, error: LightningError | None = None, status=200):
    c = container(request)
    return render(request, "investments/form.html", status_code=status, kind=kind, title=KINDS[kind][0],
                  hint=KINDS[kind][1], values=values, txn=txn,
                  holding_accounts=c.investments.investment_accounts(), all_accounts=c.accounts.list(active_only=True),
                  assets=c.assets.investments(active_only=True),
                  error=error.message if error else "", error_field=(error.field or "") if error else "")


def _save(request: Request, kind: str, v: dict, txn_id: int | None = None):
    inv = container(request).investments
    account, asset, cash = _int(v["account_id"]), _int(v["asset_id"]), _int(v["cash_account_id"])
    if txn_id:
        return inv.update(txn_id, date=v["date"], account_id=account, asset_id=asset, quantity=v["quantity"],
                          price=v["price"], fees=v["fees"], total=v["total"], cash_account_id=cash, amount=v["amount"],
                          total_cost=v["total_cost"], notes=v["notes"])
    if kind == "buy":
        return inv.buy_total(v["date"], account, asset, v["quantity"], v["total"], cash, v["notes"])
    if kind == "sell":
        return inv.sell_total(v["date"], account, asset, v["quantity"], v["total"], cash, v["notes"])
    if kind == "dividend":
        return inv.dividend(v["date"], account, asset, v["amount"], v["notes"])
    return inv.add_holding(account, asset, v["quantity"], v["total_cost"], v["date"] or None, v["notes"])


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
    return _form(request, found["kind"], values, txn=txn)


@router.post("/{txn_id:int}/edit")
async def update_trade(request: Request, txn_id: int):
    c = container(request)
    txn = c.transactions.get(txn_id)
    kind = c.investments.values_of(txn_id).get("kind", "buy")
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in FIELDS}
    try:
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
              "isin": asset.isin or "", "notes": asset.notes, "active": "1" if asset.active else ""}
    return _asset_form(request, values, asset=asset)


@router.post("/assets/{asset_id:int}/edit")
async def update_asset(request: Request, asset_id: int):
    c = container(request)
    asset = c.assets.get_asset(asset_id)
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in ("name", "class_code", "isin", "notes", "active")}
    try:
        asset = c.assets.update_investment(asset_id, values["name"], values["class_code"], values["isin"],
                                           values["notes"], active=bool(values["active"]))
    except LightningError as exc:
        return _asset_form(request, values, asset=asset, error=exc, status=400)
    return redirect("/investments", f"Saved {asset.label}.")


# -- prices ---------------------------------------------------------------------
@router.get("/prices")
async def prices(request: Request, error: str = ""):
    c = container(request)
    day = request.query_params.get("date") or fmt_date(today())
    portfolio = c.investments.portfolio(day)
    held = {p.asset_id: p for p in portfolio.open}
    rows = []
    for asset in c.assets.investments(active_only=True):
        valuation = c.reporting.value_of(asset.id, 1, day)
        rows.append({"asset": asset, "held": held.get(asset.id), "price": valuation.price,
                     "price_date": valuation.price_date, "source": valuation.source})
    rows.sort(key=lambda r: (r["held"] is None, r["asset"].name))
    return render(request, "investments/prices.html", rows=rows, day=day, error=error)


@router.post("/prices")
async def save_prices(request: Request):
    c = container(request)
    form = await request.form()
    day = str(form.get("date", "")) or fmt_date(today())
    values = {int(k[2:]): str(v) for k, v in form.items() if k.startswith("p_") and k[2:].isdigit()}
    try:
        count = c.assets.set_prices(day, values)
    except LightningError as exc:
        return redirect(f"/investments/prices?date={day}", exc.message)
    return redirect("/investments", f"Saved {count} price{'s' if count != 1 else ''} for {day}." if count
                    else "No prices entered.")
