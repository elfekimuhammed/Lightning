from __future__ import annotations

from fastapi import APIRouter, Request

from lightning.core.errors import LightningError, ValidationError

from ..web import container, redirect, render

router = APIRouter(prefix="/counterparties")


@router.get("")
async def list_counterparties(request: Request):
    c = container(request)
    parties = c.counterparties.list_active()
    categories = c.categories.pickable()
    return render(request, "counterparties.html", parties=parties, categories=categories,
                  category_labels={item.id: c.categories.display_name(item.id) for item in categories})


@router.post("")
async def create_counterparty(request: Request):
    c = container(request)
    form = await request.form()
    name = str(form.get("name", "")).strip()
    raw_category_id = str(form.get("default_category_id", "")).strip()
    action = str(form.get("counterparty_action", ""))
    categories = c.categories.pickable()
    parties = c.counterparties.list_active()
    category_labels = {item.id: c.categories.display_name(item.id) for item in categories}
    try:
        category_id = int(raw_category_id) if raw_category_id else None
        if category_id is not None and category_id not in {item.id for item in categories}:
            raise ValidationError("Choose one of the suggested categories.")
        if action == "create":
            c.counterparties.create(name, category_id)
        elif action.startswith("existing:"):
            selected_id = int(action.split(":", 1)[1])
            selected = c.counterparties.get(selected_id)
            suggestions = {candidate for candidate, _ in c.counterparties.suggestions(name)}
            resolved = c.counterparties.resolve(name)
            if not selected or (selected["name"] not in suggestions and (not resolved or resolved["id"] != selected_id)):
                raise ValidationError("Choose one of the displayed matches, or create a new Counterparty.")
            c.counterparties.add_alias(selected_id, name)
            if category_id is not None:
                c.counterparties.set_default_category(selected_id, category_id)
        else:
            matches = []
            resolved = c.counterparties.resolve(name)
            if resolved:
                matches.append({"id": resolved["id"], "name": resolved["name"]})
            else:
                matches.extend({"id": int(row["id"]), "name": row["name"]}
                               for row in parties if row["name"] in
                               {candidate for candidate, _ in c.counterparties.suggestions(name)})
            return render(request, "counterparties.html", parties=parties, categories=categories,
                          category_labels=category_labels, entered_name=name,
                          entered_category_id=raw_category_id, similar_counterparties=matches,
                          exact_existing=bool(resolved), review_required=True)
    except (ValueError, LightningError) as exc:
        return render(request, "counterparties.html", status_code=400, parties=parties, categories=categories,
                      category_labels=category_labels,
                      error=str(exc) if isinstance(exc, ValueError) else exc.message,
                      entered_name=name, entered_category_id=raw_category_id)
    return redirect("/counterparties", f"Saved {name}.")
