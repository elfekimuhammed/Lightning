from __future__ import annotations

from fastapi import APIRouter, Request

from lightning.core.errors import LightningError

from ..web import container, redirect, render

router = APIRouter(prefix="/categories")


@router.get("")
async def list_categories(request: Request):
    c = container(request)
    groups = [(group, items) for group, items in c.categories.groups() if group.family]
    return render(request, "categories/list.html", groups=groups, root=c.categories.get_by_code("EXP"))


@router.get("/new")
async def new_category(request: Request):
    c = container(request)
    parent_text = request.query_params.get("parent", "0") or "0"
    if not parent_text.isdigit():
        return redirect("/categories", "Choose a valid parent category.")
    parent = c.categories.get(int(parent_text))
    return render(request, "categories/form.html", parent=parent, parent_name=c.categories.display_name(parent.id),
                  category=None, values={"name": "", "code": "", "active": "1",
                                         "default_reimbursable": "1" if parent.default_reimbursable else ""})


@router.post("/new")
async def create_category(request: Request):
    c = container(request)
    parent_text = request.query_params.get("parent", "0") or "0"
    if not parent_text.isdigit():
        return redirect("/categories", "Choose a valid parent category.")
    parent = c.categories.get(int(parent_text))
    form = await request.form()
    values = {k: str(form.get(k, "")) for k in ("name", "code", "default_reimbursable")}
    similar = c.categories.suggestions(values["name"], parent.id)
    if similar and form.get("confirm_similar") != "1":
        return render(request, "categories/form.html", status_code=400, parent=parent,
                      parent_name=c.categories.display_name(parent.id), category=None, values=values,
                      similar_categories=[{"id": item.id, "name": item.name,
                                           "display_name": c.categories.display_name(item.id), "score": score}
                                          for item, score in similar], review_required=True)
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
    # The ordinary Save button preserves status; explicit Archive/Activate buttons set it.
    if "active" not in form:
        values["active"] = "1" if cat.active else ""
    try:
        c.categories.update(category_id, values["name"], values["code"] or None, active=bool(values["active"]),
                            default_reimbursable=bool(values["default_reimbursable"]))
    except LightningError as exc:
        return render(request, "categories/form.html", status_code=400, parent=parent,
                      parent_name=c.categories.display_name(parent.id) if parent else "", category=cat,
                      values=values, error=exc.message, error_field=exc.field or "")
    return redirect("/categories", "Category saved.")


@router.post("/{category_id:int}/delete")
async def delete_category(request: Request, category_id: int):
    c = container(request)
    try:
        archived = c.categories.delete_or_archive(category_id)
    except LightningError as exc:
        return redirect("/categories", exc.message)
    message = "Category has history or is in use, so it was archived." if archived else "Category deleted."
    return redirect("/categories", message)


@router.post("/bulk-action")
async def category_bulk_action(request: Request):
    c = container(request)
    form = await request.form()
    action = str(form.get("action", ""))
    raw_ids = form.getlist("category_ids")
    single_id = str(form.get("category_id", "")).strip()
    if single_id:
        raw_ids.append(single_id)
    try:
        if action not in {"activate", "archive", "delete"}:
            raise LightningError("Choose Activate, Archive, or Delete.")
        category_ids = sorted({int(value) for value in raw_ids if str(value).isdigit()})
        if not category_ids:
            raise LightningError("Choose at least one L2 category.")
        categories = [c.categories.get(category_id) for category_id in category_ids]
        if any(category.is_root or category.is_system or category.depth < 2 for category in categories):
            raise LightningError("Only L2 categories can be managed here.")
        activated = archived = deleted = 0
        for category in categories:
            if action == "activate":
                if not category.active:
                    c.categories.update(category.id, category.name, active=True)
                activated += 1
            elif action == "archive":
                if category.active:
                    c.categories.update(category.id, category.name, active=False)
                archived += 1
            elif c.categories.delete_or_archive(category.id):
                archived += 1
            else:
                deleted += 1
        if action == "activate":
            message = f"Activated {activated} categor{'y' if activated == 1 else 'ies'}."
        elif action == "archive":
            message = f"Archived {archived} categor{'y' if archived == 1 else 'ies'}."
        else:
            message = f"Deleted {deleted}; archived {archived} categor{'y' if deleted + archived == 1 else 'ies'}."
    except (ValueError, LightningError) as exc:
        message = exc.message if isinstance(exc, LightningError) else "Choose valid categories."
    return redirect("/categories", message)
