from __future__ import annotations

from fastapi import APIRouter, Request

from lightning.categories.domain import Movement
from lightning.core.errors import LightningError

from ..web import container, redirect, render

router = APIRouter(prefix="/categories")


@router.get("")
async def list_categories(request: Request):
    c = container(request)
    sides = []
    for title, movement, root_code in (("Money out", Movement.OUTFLOW, "EXP"), ("Money in", Movement.INFLOW, "INC")):
        groups = c.categories.groups(movement)
        sides.append({
            "title": title,
            "root": c.categories.get_by_code(root_code),
            "groups": [(g, items) for g, items in groups if items],
            "loose": [g for g, items in groups if not items],
            "loose_title": "Other" if movement == Movement.OUTFLOW else "Income",
        })
    return render(request, "categories/list.html", sides=sides)


@router.get("/new")
async def new_category(request: Request):
    c = container(request)
    parent = c.categories.get(int(request.query_params.get("parent", "0") or 0))
    return render(request, "categories/form.html", parent=parent, parent_name=c.categories.display_name(parent.id),
                  category=None, values={"name": "", "code": "", "active": "1",
                                         "default_reimbursable": "1" if parent.default_reimbursable else ""})


@router.post("/new")
async def create_category(request: Request):
    c = container(request)
    parent = c.categories.get(int(request.query_params.get("parent", "0") or 0))
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in ("name", "code", "default_reimbursable")}
    try:
        cat = c.categories.create(parent.id, values["name"], values["code"] or None,
                                  default_reimbursable=bool(values["default_reimbursable"]))
    except LightningError as exc:
        return render(request, "categories/form.html", status_code=400, parent=parent,
                      parent_name=c.categories.display_name(parent.id), category=None,
                      values=values, error=exc.message, error_field=exc.field or "")
    return redirect("/categories", f"Added {c.categories.display_name(cat.id)}.")


@router.get("/{category_id:int}/edit")
async def edit_category(request: Request, category_id: int):
    c = container(request)
    cat = c.categories.get(category_id)
    parent = c.categories.get(cat.parent_id) if cat.parent_id else None
    return render(request, "categories/form.html", parent=parent,
                  parent_name=c.categories.display_name(parent.id) if parent else "", category=cat,
                  values={"name": cat.name, "code": cat.code, "active": "1" if cat.active else "",
                          "default_reimbursable": "1" if cat.default_reimbursable else ""})


@router.post("/{category_id:int}/edit")
async def update_category(request: Request, category_id: int):
    c = container(request)
    cat = c.categories.get(category_id)
    parent = c.categories.get(cat.parent_id) if cat.parent_id else None
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in ("name", "code", "active", "default_reimbursable")}
    try:
        c.category_flows.update_category(category_id, values["name"], values["code"] or None,
                                         active=bool(values["active"]),
                                         default_reimbursable=bool(values["default_reimbursable"]))
    except LightningError as exc:
        return render(request, "categories/form.html", status_code=400, parent=parent,
                      parent_name=c.categories.display_name(parent.id) if parent else "", category=cat,
                      values=values, error=exc.message, error_field=exc.field or "")
    return redirect("/categories", "Category saved.")
