from __future__ import annotations

from difflib import SequenceMatcher

from fastapi import APIRouter, Request

from ..web import container, render

router = APIRouter()


@router.get("/search")
async def search(request: Request):
    c = container(request)
    query = " ".join(str(request.query_params.get("q", "")).split())
    results = []
    if query:
        needle = query.casefold()
        candidates = []
        candidates.extend((account.label, f"/accounts/{account.id}", "Account")
                          for account in c.accounts.list(active_only=True))
        candidates.extend((asset.name, "/investments", "Investment")
                          for asset in c.assets.list_assets() if not asset.is_cash)
        candidates.extend((category.name, "/categories", "Category")
                          for category in c.categories.tree() if not category.is_root)
        candidates.extend((party["name"], "/counterparties", "Counterparty")
                          for party in c.counterparties.list_active())
        for label, href, kind in candidates:
            text = label.casefold()
            score = 1.0 if needle in text else SequenceMatcher(None, needle, text).ratio()
            if score >= 0.48:
                results.append({"label": label, "href": href, "kind": kind, "score": score})
        results.sort(key=lambda row: (row["score"], row["label"].casefold()), reverse=True)
        results = results[:30]
    return render(request, "search.html", query=query, results=results)
