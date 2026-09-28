from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi import Response
from decimal import Decimal

from lightning.core.errors import LightningError
from lightning.core.money import ZERO
from lightning.core.dates import fmt_date, today

from ..web import container, redirect, render
from lightning.categories.domain import Movement, CategoryFamily
from lightning.core.dates import month_of

router = APIRouter(prefix="/settings")


@router.get("")
async def settings_page(request: Request):
    c = container(request)
    folder = c.data_dir / "backups"
    backups = sorted(folder.glob("lightning_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)[:10] if folder.exists() else []
    try:
        return_to = request.query_params.get("return_to", "/")
        if not return_to.startswith("/") or return_to.startswith("//") or "\\" in return_to:
            return_to = "/"
    except Exception:
        return_to = "/"
    classes = [x for x in c.assets.list_classes() if x.active and x.root_code != "CASH" and x.code != "CUSTODY"]
    values = {}
    rows, _ = c.reporting.holdings(fmt_date(today()))
    custody = {(r["account_id"], r["asset_id"]): r["units"] for r in c.money_from_others.investment_positions(fmt_date(today()))}
    for h in rows:
        asset = c.assets.get_asset(h.asset_id)
        if (not asset.is_cash or h.asset_class_code.split(".")[0] != "CASH") and h.value is not None:
            other_units = custody.get((h.account.id, h.asset_id), ZERO)
            if asset.is_cash:
                other_units = c.money_from_others.cash_total_for_account(h.account.id, fmt_date(today()))
            other_value = c.reporting.value_of(h.asset_id, other_units, fmt_date(today())).value if other_units else ZERO
            values[h.asset_class_code] = values.get(h.asset_class_code, ZERO) + max(ZERO, h.value - (other_value or ZERO))
    factors = c.investments.liquidation_factors()
    factor_rows = [{"id": cls.id, "code": cls.code, "name": cls.name, "value": values.get(cls.code, ZERO),
                    "factor": factors.get(cls.id, Decimal(95)),
                    "estimate": values.get(cls.code, ZERO) * factors.get(cls.id, Decimal(95)) / 100}
                   for cls in classes]
    income_categories = [x for x in c.categories.tree(Movement.INFLOW) if not x.is_root and x.income_class is not None]
    expense_categories = [x for x in c.categories.tree(Movement.OUTFLOW) if not x.is_root]
    try:
        selected_income = {int(x) for x in __import__('json').loads(c.settings.get("budget_income_categories"))} if c.settings.get("budget_income_categories") else {x.id for x in income_categories if x.family == CategoryFamily.WORK or any(w in x.name.casefold() for w in ("salary", "pay", "wage"))}
        excluded_categories = {int(x) for x in __import__('json').loads(c.settings.get("budget_one_off_exclusions") or "[]")}
    except (ValueError, TypeError):
        selected_income, excluded_categories = set(), set()
    return render(request, "settings/index.html", db_path=c.db.path, backups=[b.name for b in backups],
                  classes=c.assets.list_classes(), assets=c.assets.list_assets(), factor_rows=factor_rows,
                  section=request.query_params.get("section", "general"), return_to=return_to,
                  budget_return_to=f"/settings?section=budget&return_to={return_to}",
                  income_categories=income_categories, expense_categories=expense_categories,
                  selected_income=selected_income, excluded_categories=excluded_categories,
                  carryover=c.settings.get("budget_carryover_global")=="1",
                  carryover_month=c.settings.get("budget_carryover_month") or month_of(today()),
                  income_months=c.settings.get("budget_income_months") or "3",
                  manual_income=c.settings.get("budget_manual_monthly_income") or "",
                  suggestion_percent=c.settings.get("budget_track_suggestion_percent") or "20",
                  suggestion_fixed=c.settings.get("budget_track_suggestion_fixed") or "",
                  ceiling_percent=c.settings.get("budget_monthly_ceiling_percent") or "100")


@router.post("/liquidation-factor/{asset_class_id:int}")
async def save_liquidation_factor(request: Request, asset_class_id: int):
    c = container(request)
    try:
        form = await request.form()
        c.investments.set_liquidation_factor(asset_class_id, str(form.get("factor", "")))
    except (LightningError, ValueError) as exc:
        return Response(exc.message if isinstance(exc, LightningError) else "Invalid value.", status_code=400, media_type="text/plain")
    return Response(status_code=204)


@router.post("/backup")
async def backup_now(request: Request):
    path = container(request).backup_now()
    return redirect("/settings", f"Backup saved as {path.name}." if path else "Nothing to back up yet.")
