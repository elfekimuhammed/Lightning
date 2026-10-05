from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi import Response
from decimal import Decimal

from lightning.core.errors import LightningError
from lightning.investments.domain import DEFAULT_SALE_FACTOR
from lightning.core.money import ZERO
from lightning.budgeting.domain import INCOME_FROM_RECURRING
from lightning.core.dates import fmt_date, today

from ..web import container, redirect, render
from lightning.categories.domain import Movement, CategoryFamily
from lightning.core.dates import month_of
from lightning.workflows.ai_analysis import AIAnalysisService
from ..periods import parse_period

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
    health_limits = c.health.limit_settings() if section == "financial-health" else []
    health_fund = c.health.emergency_fund(today()) if section == "financial-health" else None
    ai_period = ai_preview = ai_prompt = None
    if section == "general":
        try:
            ai_period = parse_period(request.query_params, today(), c.reporting.first_activity_date())
        except LightningError:
            ai_period = parse_period({}, today(), c.reporting.first_activity_date())
        ai_service = AIAnalysisService(c)
        ai_snapshot = ai_service._snapshot(ai_period, include_workbook_rows=False)
        ai_preview = ai_snapshot["preview"]
        ai_filename = f"lightning-analysis-{ai_period.start_text}-to-{ai_period.end_text}.xlsx"
        ai_prompt = ai_service.prompt(ai_period, ai_filename, ai_snapshot)
    return render(request, "settings/index.html", db_path=c.db.path, backups=[b.name for b in backups], plan=plan,
                  classes=c.assets.list_classes(), assets=c.assets.list_assets(), factor_rows=factor_rows, factor_groups=factor_groups,
                  section=request.query_params.get("section", "general"), return_to=return_to,
                  budget_return_to=f"/settings?section=budget&return_to={return_to}",
                  income_categories=income_categories, expense_categories=expense_categories,
                  selected_income=selected_income, excluded_categories=excluded_categories,
                  carryover=c.settings.get("budget_carryover_global")=="1",
                  carryover_month=c.settings.get("budget_carryover_month") or month_of(today()),
                  income_months=c.settings.get("budget_income_months") or "3",
                  emergency_basis=c.budgets.emergency_basis(),
                  manual_income=c.settings.get("budget_manual_monthly_income") or "",
                  income_from_recurring=c.settings.get(INCOME_FROM_RECURRING) == "1",
                  suggestion_percent=c.settings.get("budget_track_suggestion_percent") or "20",
                  suggestion_fixed=c.settings.get("budget_track_suggestion_fixed") or "",
                  ai_period=ai_period, ai_preview=ai_preview, ai_prompt=ai_prompt,
                  ai_month=month_of(ai_period.end) if ai_period else month_of(today()),
                  current_month=month_of(today()), health_limits=health_limits,
                  health_fund=health_fund)


@router.post("/financial-health-limit")
async def save_financial_health_limit(request: Request):
    c = container(request)
    form = await request.form()
    key = str(form.get("key", ""))
    try:
        if form.get("action") == "reset":
            c.health.restore_limit(key)
            message = "Restored the default limit."
        else:
            c.health.set_limit(key, str(form.get("value", "")), form.get("no_limit") == "1")
            message = "Financial health limit saved."
        if key == "savings_rate":  # the savings target sets Most you can plan
            message = " ".join(x for x in (message, c.health.plan_note()) if x)
    except LightningError as exc:
        if request.headers.get("X-Requested-With") == "fetch":
            return Response(exc.message, status_code=400, media_type="text/plain; charset=utf-8")
        return redirect("/settings?section=financial-health", exc.message)
    if request.headers.get("X-Requested-With") == "fetch":
        return Response(status_code=204)
    return redirect("/settings?section=financial-health", message)


@router.post("/privacy")
async def save_privacy(request: Request):
    """Remember privacy mode in the profile; the window has already switched it with its cookie."""
    form = await request.form()
    container(request).settings.set("privacy_mode", "1" if form.get("on") == "1" else "0")
    return Response(status_code=204)


@router.post("/ai-analysis")
async def prepare_ai_analysis(request: Request):
    c = container(request)
    try:
        form = await request.form()
        period = parse_period(form, today(), c.reporting.first_activity_date())
        content, filename, _ = AIAnalysisService(c).build(period)
    except (LightningError, ValueError) as exc:
        message = exc.message if isinstance(exc, LightningError) else str(exc)
        return Response(message, status_code=400, media_type="text/plain; charset=utf-8")
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"',
                             "Cache-Control": "no-store"})


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


@router.post("/fresh")
async def start_fresh(request: Request):
    """Browser mode: set the current database aside (after a backup) and open an empty one in its
    place. Nothing is deleted. The desktop app uses a new profile instead (Settings links there)."""
    import os
    from datetime import datetime
    from pathlib import Path
    from lightning.bootstrap import build

    profiles = getattr(request.app.state, "profile_session", None)
    if getattr(request.state, "secure_profiles", False) and profiles is not None:
        # Desktop: this profile stays as it is; lock it and set up a new, empty one.
        profiles.close()
        request.app.state.container = None
        return redirect("/profiles/new")
    c = container(request)
    current = Path(c.db.path)
    if str(current) == ":memory:":
        return redirect("/settings", "This database is not a file, so there is nothing to set aside.")
    saved = c.backup_now()
    aside = current.with_name(f"{current.stem}_before-fresh_{datetime.now():%Y-%m-%d_%H%M%S}{current.suffix}")
    c.db.close()
    try:
        os.replace(current, aside)
        for suffix in ("-journal", "-wal", "-shm"):
            side = Path(f"{current}{suffix}")
            if side.exists():
                os.replace(side, Path(f"{aside}{suffix}"))
    except OSError:
        request.app.state.container = build(current, backup_dir=c.backup_dir)  # reopen the untouched file
        return redirect("/settings", "Couldn't set the current database aside, so nothing changed. Close other programs using it and try again.")
    request.app.state.container = build(current, backup_dir=c.backup_dir)
    note = f" A backup is in {saved.name}." if saved else ""
    return redirect("/", f"Started a fresh database. Your old one is kept as {aside.name}.{note}")
