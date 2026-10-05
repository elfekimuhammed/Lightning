"""One search for the whole app: the Search page and the Ctrl-K command bar ask the same matcher.

It finds pages, actions, a transaction by its reference, accounts, counterparties, categories,
investments and #tags, ranks them (exact name, starts with, a word starts with, contains, then a close
spelling), groups them by type so an own account is never mistaken for a counterparty, and always ends
with "Find transactions with ...". A close spelling is never tried on amounts or dates. Choosing a
result is the user's click; the matcher changes nothing.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from lightning.core.errors import LightningError
from lightning.core.refs import parse_ref
from lightning.transactions.tags import normalize as normal_tag

from ..web import container, privacy_on, render

router = APIRouter()

# Where each page is, and other words someone might type for it.
PAGES = (
    ("Overview", "/", "home start where do i stand net worth needs you"),
    ("Budget", "/budget", "plan spending limits left in plan"),
    ("Investments", "/investments", "portfolio holdings stocks shares funds gold returns"),
    ("Expense analysis", "/birdview/expenses", "spending where did my money go"),
    ("Cash planning", "/plan", "safe to spend forecast free cash payday"),
    ("Recurring", "/plan/recurring", "bills subscriptions income fixed costs"),
    ("Loans", "/plan/loans", "debt installments owe"),
    ("Reserves", "/plan/reserves", "emergency fund goals savings"),
    ("Held for others", "/money-from-others", "custody family people their money"),
    ("All transactions", "/transactions", "register ledger history"),
    ("Accounts", "/accounts", "banks wallets manage accounts"),
    ("Categories", "/categories", "income spending one-off recurring"),
    ("Counterparties", "/counterparties", "payees shops people names"),
    ("Investment planner", "/investments/planner", "allocation targets invest"),
    ("Update prices", "/investments/prices", "valuations market prices gold price"),
    ("Settings", "/settings", "backup data version"),
    ("Budget settings", "/settings?section=budget", "average monthly income one-off emergency fund"),
    ("Target allocation", "/settings?section=targets", "asset classes targets"),
    ("Valuations", "/settings?section=valuations", "sale factors prices catalogue"),
    ("Data checks", "/checks", "integrity is my data right"),
    ("Deleted transactions", "/transactions/deleted", "voided removed restore"),
)
ACTIONS = (
    ("Add transaction", "/transactions", "new spend expense income record enter"),
    ("Add account", "/accounts/new", "new bank wallet"),
    ("Add recurring item", "/plan/items/new?kind=BILL", "new bill subscription income"),
    ("Add loan", "/plan/items/new?kind=LOAN", "new installment debt"),
    ("Add an investment to the catalogue", "/investments/assets/new", "new fund stock instrument"),
)
GROUPS = ("Transaction", "Page", "Action", "Account", "Counterparty", "Category", "Investment", "Tag", "Search")
_LOOKS_NUMERIC = re.compile(r"[\d\s,./:+−-]+")


def _score(needle: str, text: str, fuzzy: bool = True) -> float:
    """1 for the exact name, then starts with, a word starts with, contains, then a close spelling."""
    text = " ".join(text.casefold().split())
    if not needle or not text:
        return 0.0
    if text == needle:
        return 1.0
    if text.startswith(needle):
        return 0.95
    if any(word.startswith(needle) for word in re.split(r"[\s›·/&,()-]+", text)):
        return 0.9
    if needle in text:
        return 0.8
    ratio = SequenceMatcher(None, needle, text).ratio() if fuzzy else 0.0
    return ratio * 0.75 if ratio >= 0.6 else 0.0


def matches(c, query: str, privacy: bool = False, per_group: int = 6) -> list[dict]:
    """Ranked results grouped by type: {label, href, kind, context}; an action may carry "action"."""
    query = " ".join(str(query or "").split())
    needle = query.casefold()
    fuzzy = not _LOOKS_NUMERIC.fullmatch(query)  # never a close spelling for amounts or dates
    privacy_action = {"label": "Show amounts" if privacy else "Hide amounts", "href": "#", "kind": "Action",
                      "context": "Privacy mode for this profile", "action": "privacy"}
    if not needle:  # an empty command bar is a launcher: the main pages and the everyday actions
        return ([{"label": label, "href": href, "kind": "Page", "context": ""} for label, href, _ in PAGES[:10]]
                + [{"label": label, "href": href, "kind": "Action", "context": ""} for label, href, _ in ACTIONS[:3]]
                + [privacy_action])
    found: list[tuple[float, dict]] = []

    def add(score: float, label: str, href: str, kind: str, context: str = "", **more) -> None:
        if score > 0:
            found.append((score, {"label": label, "href": href, "kind": kind, "context": context, **more}))

    try:
        txn = c.transactions.get_by_ref(query) if parse_ref(query.upper()) else None
        add(1.0, txn.ref, f"/transactions/{txn.id}", "Transaction", f"{txn.date} · {txn.counterparty or txn.description}")
    except LightningError:
        pass
    for label, href, words in PAGES:
        add(max(_score(needle, label, fuzzy), _score(needle, words, False) * 0.85), label, href, "Page")
    for label, href, words in ACTIONS:
        add(max(_score(needle, label, fuzzy), _score(needle, words, False) * 0.85), label, href, "Action")
    add(max(_score(needle, privacy_action["label"], fuzzy), _score(needle, "privacy hide show amounts blur", False) * 0.85),
        privacy_action["label"], "#", "Action", privacy_action["context"], action="privacy")
    for account in c.accounts.list(active_only=True):
        score = _score(needle, account.label, fuzzy)
        add(score, account.label, f"/accounts/{account.id}", "Account", account.account_type.label
            if hasattr(account.account_type, "label") else account.account_type.value.title())
        if account.account_type.value in ("BANK", "CASH", "BROKERAGE"):
            for verb, path in (("Import CSV", "import"), ("Check against bank", "reconcile")):
                add(max(_score(needle, f"{verb} {account.label}", fuzzy), _score(needle, verb, False) * 0.85 if score
                        or len(needle) > 2 else 0), f"{verb} · {account.label}", f"/accounts/{account.id}/{path}", "Action")
    for party in c.counterparties.list_active():
        add(_score(needle, party["name"], fuzzy), party["name"], "/transactions?" + urlencode({"q": party["name"]}), "Counterparty",
            "Its transactions")
    for category in c.categories.tree():
        if not category.is_root:
            add(_score(needle, category.name, fuzzy), category.name, f"/transactions?category_id={category.id}",
                "Category", c.categories.display_name(category.id))
    for asset in c.assets.list_assets():
        if not asset.is_cash:
            add(max(_score(needle, asset.name, fuzzy), _score(needle, asset.code or "", False)), asset.name,
                "/investments", "Investment", asset.code or "")
    tag_needle = normal_tag(needle) if needle.startswith("#") or len(needle) > 1 else ""
    for tag, count in (c.transactions.tags() if tag_needle else []):
        add(_score(tag_needle, tag, False) or (0.7 if needle == "#" else 0), f"#{tag}", f"/transactions?tag={quote(tag)}", "Tag",
            f"{count} transaction{'s' if count != 1 else ''}")
    results: list[dict] = []
    for group in GROUPS:
        ranked = sorted((pair for pair in found if pair[1]["kind"] == group), key=lambda p: (-p[0], p[1]["label"].casefold()))
        results += [row for _, row in ranked[:per_group]]
    results.append({"label": f"Find transactions with “{query}”", "href": "/transactions?" + urlencode({"q": query}),
                    "kind": "Search", "context": "Search every account's register"})
    return results


@router.get("/search")
async def search(request: Request):
    c = container(request)
    query = " ".join(str(request.query_params.get("q", "")).split())
    results = matches(c, query, privacy=privacy_on(request))
    if request.query_params.get("format") == "json":
        return JSONResponse({"query": query, "results": results})
    return render(request, "search.html", query=query, results=results if query else [])
