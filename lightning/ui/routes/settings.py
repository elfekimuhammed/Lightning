from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi import Response
from decimal import Decimal

from lightning.core.errors import LightningError
from lightning.investments.domain import DEFAULT_SALE_FACTOR
from lightning.core.money import ZERO
from lightning.core.dates import fmt_date, today

from ..web import container, redirect, render
from lightning.categories.domain import Movement, CategoryFamily
from lightning.core.dates import month_of

router = APIRouter(prefix="/settings")


@router.get("")
async def settings_page(request: Request):
    c = container(request)
    backups = c.backup_files()[:10]
    try:
        return_to = request.query_params.get("return_to", "/")
        if not return_to.startswith("/") or return_to.startswith("//") or "\\" in return_to:
            return_to = "/"
    except Exception:
        return_to = "/"
    classes = [x for x in c.assets.list_classes() if x.active and x.root_code != "CASH" and x.code != "CUSTODY"]
    # The same class values and factors as Birdview's "If you sold today".
    values = {row.code: row.value for row in c.position.class_values(today())[0]}
    sources = c.investments.sale_factor_sources()
    own = c.investments.own_liquidation_factors()
    names = {cls.id: cls.name for cls in c.assets.list_classes()}

    def factor_row(cls):
        factor, source = sources.get(cls.id, (DEFAULT_SALE_FACTOR, None))
        value = values.get(cls.code, ZERO)
        return {"id": cls.id, "code": cls.code, "name": cls.name, "depth": cls.depth, "value": value,
                "own": own.get(cls.id), "factor": factor, "estimate": value * factor / 100,
                "from": "the default" if source is None else names.get(source, "")}

    # One group per top-level class: its own row (a factor here applies to every child left empty),
    # then its children. A child's own factor overrides its parent's.
    factor_rows, factor_groups = [], []
    for root in (cls for cls in classes if cls.parent_id is None or cls.parent_id not in {x.id for x in classes}):
        rows = [factor_row(root)] + [factor_row(cls) for cls in classes if cls.code.startswith(root.code + ".")]
        factor_rows += rows
        factor_groups.append({"root": rows[0], "children": rows[1:],
                              "value": sum((r["value"] for r in rows), ZERO),
                              "estimate": sum((r["estimate"] for r in rows), ZERO)})
    income_categories = [x for x in c.categories.tree(Movement.INFLOW) if not x.is_root and x.income_class is not None]
    expense_categories = [x for x in c.categories.tree(Movement.OUTFLOW) if not x.is_root]
    try:
        selected_income = {int(x) for x in __import__('json').loads(c.settings.get("budget_income_categories"))} if c.settings.get("budget_income_categories") else {x.id for x in income_categories if x.family == CategoryFamily.WORK or any(w in x.name.casefold() for w in ("salary", "pay", "wage"))}
        excluded_categories = {int(x) for x in __import__('json').loads(c.settings.get("budget_one_off_exclusions") or "[]")}
    except (ValueError, TypeError):
        selected_income, excluded_categories = set(), set()
    section = request.query_params.get("section", "general")
    plan = None
    if section == "targets":
        from .investments import target_plan
        plan = target_plan(c)
    return render(request, "settings/index.html", db_path=c.db.path, backups=[b.name for b in backups], plan=plan,
                  classes=c.assets.list_classes(), assets=c.assets.list_assets(), factor_rows=factor_rows, factor_groups=factor_groups,
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
