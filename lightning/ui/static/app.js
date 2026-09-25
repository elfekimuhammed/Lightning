// Small helpers only — no financial logic lives in the browser.

// Date quick buttons (Today / Yesterday) — always yyyy-mm-dd.
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-date]");
  if (!btn) return;
  e.preventDefault();
  const input = document.getElementById(btn.dataset.target || "date");
  const d = new Date();
  d.setDate(d.getDate() - Number(btn.dataset.date || 0));
  const pad = (n) => String(n).padStart(2, "0");
  input.value = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
});

// Register: click a row to edit it in place.
document.addEventListener("click", (e) => {
  const row = e.target.closest("tr[data-href]");
  if (row && !e.target.closest("a, button, input, select")) location.href = row.dataset.href;
});

// Keep repeated Enter presses from posting the quick-add form twice.
document.addEventListener("submit", (event) => {
  const form = event.target;
  if (form.matches("[data-confirm-delete]") && !window.confirm("Delete this transaction? You can restore it from its history page.")) {
    event.preventDefault(); return;
  }
  if (!(form.matches("#f-new, #f-edit, .investment-entry-form"))) return;
  if (form.dataset.submitting === "true") { event.preventDefault(); return; }
  form.dataset.submitting = "true";
  const buttons = [...form.querySelectorAll("button")];
  if (form.id) buttons.push(...document.querySelectorAll(`[form="${form.id}"][type="submit"], [form="${form.id}"]:not([type])`));
  buttons.forEach((button) => { button.disabled = true; });
});

// Select rows, use the right-click menu, and soft-delete one or many transactions.
const ledger = document.querySelector(".ledger");
if (ledger) {
  const menu = document.getElementById("transaction-context-menu");
  const tools = document.getElementById("selection-tools");
  const count = document.getElementById("selection-count");
  const selectAll = document.getElementById("select-visible");
  const visibleChecks = () => [...ledger.querySelectorAll(".transaction-select:not(:disabled)")];
  const selectedIds = () => visibleChecks().filter((box) => box.checked).map((box) => box.value);
  const syncSelection = () => {
    const selected = selectedIds();
    tools.hidden = selected.length === 0;
    count.textContent = `${selected.length} selected`;
    selectAll.checked = visibleChecks().length > 0 && visibleChecks().every((box) => box.checked);
    selectAll.indeterminate = selected.length > 0 && !selectAll.checked;
    if (menu && !menu.hidden) menu.querySelector("[data-context-delete]").textContent =
      selected.length > 1 ? `Delete ${selected.length} selected` : "Delete transaction";
  };
  const deleteTransactions = (ids) => {
    if (!ids.length || !window.confirm(`Delete ${ids.length === 1 ? "this transaction" : `${ids.length} transactions`}? They will be removed from the register and can be restored from transaction history.`)) return;
    const form = document.createElement("form");
    form.method = "post"; form.action = "/transactions/bulk-delete";
    const back = document.createElement("input"); back.type = "hidden"; back.name = "back"; back.value = location.pathname + location.search; form.append(back);
    ids.forEach((id) => { const input = document.createElement("input"); input.type = "hidden"; input.name = "txn_ids"; input.value = id; form.append(input); });
    document.body.append(form); form.submit();
  };
  visibleChecks().forEach((box) => box.addEventListener("change", syncSelection));
  selectAll?.addEventListener("change", () => { visibleChecks().forEach((box) => { box.checked = selectAll.checked; }); syncSelection(); });
  document.getElementById("select-visible-header")?.addEventListener("click", (event) => {
    if (event.target.closest("input")) return;
    event.preventDefault();
    selectAll.checked = !selectAll.checked;
    visibleChecks().forEach((box) => { box.checked = selectAll.checked; });
    syncSelection();
  });
  document.getElementById("delete-selected")?.addEventListener("click", () => deleteTransactions(selectedIds()));
  ledger.addEventListener("contextmenu", (event) => {
    const row = event.target.closest("tr[data-href]");
    if (!row || !menu) return;
    const checkbox = row.querySelector(".transaction-select");
    if (!checkbox || checkbox.disabled) return;
    event.preventDefault();
    if (!checkbox.checked) { visibleChecks().forEach((box) => { box.checked = false; }); checkbox.checked = true; }
    menu.dataset.href = row.dataset.href;
    menu.hidden = false;
    const x = Math.min(event.clientX, window.innerWidth - menu.offsetWidth - 8);
    const y = Math.min(event.clientY, window.innerHeight - menu.offsetHeight - 8);
    menu.style.left = `${Math.max(8, x)}px`; menu.style.top = `${Math.max(8, y)}px`;
    syncSelection();
  });
  menu?.querySelector("[data-context-edit]").addEventListener("click", () => { if (menu.dataset.href) location.href = menu.dataset.href; });
  menu?.querySelector("[data-context-delete]").addEventListener("click", () => { menu.hidden = true; deleteTransactions(selectedIds()); });
  document.addEventListener("click", (event) => { if (menu && !event.target.closest("#transaction-context-menu")) menu.hidden = true; });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && menu) menu.hidden = true; });
  syncSelection();
}

// Money held for another person is shown in its own register column and needs an owner.
document.querySelectorAll(".category-input").forEach((category) => {
  const row = category.closest("tr");
  const cell = row?.querySelector(".whom-cell");
  const header = document.querySelector(".whom-head");
  const counterparty = row?.querySelector(".counterparty-input");
  const ledger = category.closest(".ledger");
  const internalAccounts = JSON.parse(ledger?.dataset.accounts || "[]");
  if (!cell) return;
  const syncWhom = () => {
    const isCustody = /money held for others/i.test(category.value);
    const target = counterparty?.value.trim() || "";
    const isTransfer = target.startsWith("↔") || internalAccounts.includes(target);
    const visible = isCustody || isTransfer;
    cell.hidden = !visible;
    if (header && visible) header.hidden = false;
    const input = cell.querySelector("input");
    if (input) {
      input.disabled = !visible;
      input.placeholder = isTransfer ? "Whom? (if held for someone)" : "Whom?";
    }
  };
  category.addEventListener("input", syncWhom);
  category.addEventListener("change", syncWhom);
  counterparty?.addEventListener("input", syncWhom);
  counterparty?.addEventListener("change", syncWhom);
  syncWhom();
});

// For brokerage trades, owner attribution is independent from the Counterparty field.
document.querySelectorAll(".investment-entry-form").forEach((form) => {
  const flag = form.querySelector('[name="is_others"]');
  const field = form.querySelector(".investment-owner-field");
  if (!flag || !field) return;
  const sync = () => { field.hidden = !flag.checked; };
  flag.addEventListener("change", sync);
  sync();
});
document.querySelectorAll(".investment-ownership-form").forEach((form) => {
  const flag = form.querySelector('[name="is_others"]');
  const field = form.querySelector(".investment-owner-field");
  if (!flag || !field) return;
  const sync = () => { field.hidden = !flag.checked; };
  flag.addEventListener("change", sync);
  sync();
});

// CSV rows use the same Whom rule as the register when custody is selected.
document.querySelectorAll(".import-category").forEach((category) => {
  const row = category.closest("tr");
  const cell = row?.querySelector(".import-whom-cell");
  const header = document.querySelector(".import-whom-head");
  if (!cell) return;
  const sync = () => {
    const visible = /money held for others/i.test(category.selectedOptions[0]?.textContent || "");
    cell.hidden = !visible;
    if (header && visible) header.hidden = false;
    const input = cell.querySelector("input");
    if (input) input.disabled = !visible;
  };
  category.addEventListener("change", sync);
  sync();
});

// Register: Escape cancels an edit.
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  const cancel = document.querySelector("[data-cancel]");
  if (cancel && e.target.closest("tr.editing")) location.href = cancel.href;
});
// Format money as the user types (1,000.50) while retaining a plain numeric value on submit.
document.querySelectorAll(".money-input").forEach((input) => {
  input.addEventListener("input", () => {
    const before = input.value;
    const caret = input.selectionStart ?? before.length;
    const digitsBeforeCaret = before.slice(0, caret).replace(/[^0-9]/g, "").length;
    const raw = before.replace(/,/g, "").replace(/[^0-9.\-]/g, "");
    const sign = raw.startsWith("-") ? "-" : "";
    const unsigned = raw.replace(/-/g, "");
    const [whole = "", ...fraction] = unsigned.split(".");
    const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    input.value = sign + grouped + (fraction.length ? "." + fraction.join("") : (unsigned.endsWith(".") ? "." : ""));
    if (document.activeElement === input) {
      let seen = 0, next = (sign && caret > 0) ? 1 : 0;
      while (next < input.value.length && seen < digitsBeforeCaret) {
        if (/\d/.test(input.value[next])) seen++;
        next++;
      }
      input.setSelectionRange(next, next);
    }
  });
});

// Register: Counterparty and Category work together.
//  - an owned account as counterparty -> transfer: no category is needed
//  - a known counterparty -> fill its most recent category when available
// Show the per-unit price implied by the all-in total on investment trades.
document.querySelectorAll(".trade-total").forEach((total) => {
  const form = total.closest("form");
  const quantity = form?.querySelector(".quantity-input");
  const preview = form?.querySelector(".unit-price-preview");
  if (!quantity || !preview) return;
  const update = () => {
    const units = Number(quantity.value.replace(/,/g, ""));
    const amount = Number(total.value.replace(/,/g, ""));
    preview.value = units > 0 && amount > 0
      ? new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 }).format(amount / units)
      : "";
  };
  quantity.addEventListener("input", update);
  total.addEventListener("input", update);
  update();
});

// Inline brokerage activity: pick an instrument, then sign units to buy or sell.
const tradeCatalogueNode = document.getElementById("trade-instrument-catalogue");
if (tradeCatalogueNode) {
  const instruments = JSON.parse(tradeCatalogueNode.textContent || "[]");
  const form = document.querySelector(".investment-entry-form");
  const search = document.getElementById("trade-instrument-search");
  const selectedKey = form.querySelector('[name="instrument_key"]');
  const selectedLabel = form.querySelector('[name="instrument_label"]');
  const results = document.getElementById("trade-instrument-results");
  const units = document.getElementById("investment-units");
  const total = document.getElementById("investment-total");
  const unitPrice = document.getElementById("investment-unit-price");
  const basis = form.querySelector('[name="price_basis"]');
  const amountLabel = document.getElementById("investment-total-label");
  const positionHint = document.getElementById("trade-position-hint");
  const entryHint = document.getElementById("investment-entry-hint");
  const addButton = form.querySelector(".investment-entry-submit");
  let selected = instruments.find((item) => item.key === selectedKey.value) || null;
  const number = (input) => {
    const value = input.value.replace(/,/g, "").trim();
    if (!value || value === "-" || value === "+") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const formatted = (value, decimals = 6) => value > 0
    ? new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: decimals }).format(value)
    : "";
  const sync = () => {
    const qty = number(units);
    const cashTotal = number(total);
    const price = number(unitPrice);
    if (qty === null) amountLabel.textContent = "Dividend amount";
    else amountLabel.textContent = qty < 0 ? "Total received (after fees)" : "Total paid (fees included)";
    if (qty !== null && Math.abs(qty) > 0) {
      if (basis.value === "unit_price" && price !== null) total.value = formatted(Math.abs(qty) * price, 2);
      else if (cashTotal !== null) unitPrice.value = formatted(cashTotal / Math.abs(qty));
    }
    let exceeds = false;
    if (selected && qty !== null && qty < 0) {
      const owned = Number(selected.holding || 0);
      exceeds = Math.abs(qty) > owned;
      positionHint.textContent = exceeds
        ? `You have ${formatted(owned, selected.decimals)} ${selected.unit}(s); you cannot sell ${formatted(Math.abs(qty), selected.decimals)}.`
        : `You hold ${formatted(owned, selected.decimals)} ${selected.unit}(s) here.`;
    } else if (selected) {
      positionHint.textContent = `You hold ${formatted(Number(selected.holding || 0), selected.decimals)} ${selected.unit}(s) here.`;
    }
    if (qty === null) entryHint.textContent = "Leave units blank to record a dividend. Enter the dividend total received.";
    else entryHint.textContent = qty < 0
      ? "For a sell, enter units with a minus sign; the total is what arrived after fees."
      : "For a buy, enter positive units; the total paid includes fees.";
    addButton.disabled = exceeds;
  };
  const renderResults = () => {
    const query = search.value.trim().toLocaleLowerCase();
    results.replaceChildren();
    if (!query) { results.hidden = true; search.setAttribute("aria-expanded", "false"); return; }
    const matches = instruments.filter((item) => `${item.name} ${item.ticker} ${item.kind}`
      .toLocaleLowerCase().includes(query)).slice(0, 12);
    if (!matches.length) {
      const empty = document.createElement("div");
      empty.className = "instrument-result";
      empty.textContent = "No match in your list. Choose a listed stock or fund.";
      results.append(empty);
    }
    matches.forEach((item) => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "instrument-result"; button.setAttribute("role", "option");
      const name = document.createElement("span"); name.textContent = item.name;
      const ticker = document.createElement("small"); ticker.textContent = `${item.kind} · ${item.ticker}`;
      button.append(name, ticker);
      button.addEventListener("click", () => {
        selected = item; selectedKey.value = item.key;
        selectedLabel.value = `${item.name} · ${item.ticker}`;
        search.value = selectedLabel.value;
        results.hidden = true; search.setAttribute("aria-expanded", "false"); sync();
      });
      results.append(button);
    });
    results.hidden = false; search.setAttribute("aria-expanded", "true");
  };
  search.addEventListener("input", () => {
    selected = null; selectedKey.value = ""; selectedLabel.value = "";
    positionHint.textContent = "Choose an instrument from the results."; renderResults(); sync();
  });
  search.addEventListener("focus", renderResults);
  units.addEventListener("input", sync);
  total.addEventListener("input", () => { basis.value = "total"; sync(); });
  unitPrice.addEventListener("input", () => { basis.value = "unit_price"; sync(); });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".instrument-picker")) {
      results.hidden = true; search.setAttribute("aria-expanded", "false");
    }
  });
  if (selected) { search.value = selectedLabel.value || `${selected.name} · ${selected.ticker}`; }
  sync();
}

// Only physical gold uses a karat selector; funds have fund units, not gold purity.
const investmentClass = document.getElementById("class_code");
const karatField = document.getElementById("karat-field");
if (investmentClass && karatField) {
  const syncKarat = () => { karatField.hidden = investmentClass.value !== "GOLD"; };
  investmentClass.addEventListener("change", syncKarat);
  syncKarat();
}

// Investment picker: filter the bundled EGX stock and Thndr fund catalogue.
const catalogueNode = document.getElementById("instrument-catalogue");
if (catalogueNode) {
  const catalogue = JSON.parse(catalogueNode.textContent || "[]");
  const search = document.getElementById("instrument-search");
  const results = document.getElementById("instrument-results");
  const selection = document.getElementById("instrument-selection");
  const form = search.closest("form");
  const name = form.querySelector('[name="name"]');
  const kind = form.querySelector('[name="class_code"]');
  const symbol = form.querySelector('[name="symbol"]');
  const render = () => {
    const query = search.value.trim().toLocaleLowerCase(); results.replaceChildren();
    if (!query) { results.hidden = true; search.setAttribute("aria-expanded", "false"); return; }
    const matches = catalogue.filter((item) => `${item.name} ${item.ticker} ${item.kind}`.toLocaleLowerCase().includes(query)).slice(0, 12);
    if (!matches.length) { const empty=document.createElement("div"); empty.className="instrument-result"; empty.textContent="No match. You can enter the investment details below."; results.append(empty); }
    matches.forEach((item) => {
      const button=document.createElement("button"); button.type="button"; button.className="instrument-result"; button.setAttribute("role","option");
      const label=document.createElement("span"); label.textContent=item.name; const ticker=document.createElement("small"); ticker.textContent=`${item.kind} · ${item.ticker}`; button.append(label,ticker);
      button.addEventListener("click", () => { name.value=item.name; kind.value=item.class_code; if(symbol) symbol.value=item.ticker; search.value=`${item.name} · ${item.ticker}`; results.hidden=true; search.setAttribute("aria-expanded","false"); selection.textContent=`Selected ${item.name} (${item.ticker}). Review the details, then save.`; }); results.append(button);
    }); results.hidden=false; search.setAttribute("aria-expanded","true");
  };
  search.addEventListener("input",render); search.addEventListener("focus",render);
  document.addEventListener("click",(event)=>{if(!event.target.closest(".instrument-picker")){results.hidden=true;search.setAttribute("aria-expanded","false");}});
}

if (ledger) {
  const known = JSON.parse(ledger.dataset.counterparties || "{}");
  const accounts = JSON.parse(ledger.dataset.accounts || "[]");
  const parties = Object.keys(known).sort((a, b) => a.localeCompare(b));
  document.querySelectorAll(".counterparty-input").forEach((counterparty) => {
    const form = counterparty.getAttribute("form");
    const category = document.querySelector(`.category-input[form="${form}"]`);
    const results = document.getElementById(counterparty.dataset.counterpartyResults);
    const clearDecision = (name) => document.querySelector(`input[type="hidden"][form="${form}"][name="${name}"]`)?.remove();
    const closeResults = () => { if (results) { results.hidden = true; counterparty.setAttribute("aria-expanded", "false"); } };
    const sync = () => {
      const isTransfer = accounts.some((name) => name.toLocaleLowerCase() === counterparty.value.trim().toLocaleLowerCase());
      if (category) {
        category.disabled = isTransfer;
        category.placeholder = isTransfer ? "Transfer — no category needed" : "Category — type to search";
        if (isTransfer) category.value = "";
        else if (!category.value && known[counterparty.value]) {
          category.value = known[counterparty.value];
          category.dispatchEvent(new Event("input", { bubbles: true }));
        }
      }
    };
    const addGroup = (title, values, tag) => {
      if (!values.length) return;
      const heading = document.createElement("div"); heading.className = "counterparty-group-title"; heading.textContent = title; results.append(heading);
      values.forEach((name) => {
        const button = document.createElement("button"); button.type = "button"; button.className = "counterparty-option"; button.setAttribute("role", "option");
        const label = document.createElement("span"); label.textContent = name;
        const type = document.createElement("span"); type.className = "counterparty-kind"; type.textContent = tag;
        button.append(label, type);
        button.addEventListener("click", () => {
          counterparty.value = name; closeResults();
          counterparty.dispatchEvent(new Event("input", { bubbles: true }));
          counterparty.dispatchEvent(new Event("change", { bubbles: true }));
        });
        results.append(button);
      });
    };
    const renderResults = () => {
      const query = counterparty.value.trim().toLocaleLowerCase();
      results.replaceChildren();
      if (!query) { closeResults(); return; }
      const internal = accounts.filter((name) => name.toLocaleLowerCase().includes(query)).slice(0, 8);
      const saved = parties.filter((name) => name.toLocaleLowerCase().includes(query)).slice(0, 8);
      addGroup("Your accounts · internal transfers", internal, "Internal");
      addGroup("People & businesses", saved, "Counterparty");
      if (!internal.length && !saved.length) {
        const empty = document.createElement("div"); empty.className = "counterparty-group-title";
        empty.textContent = "No saved match · press Enter to review this new name"; results.append(empty);
      }
      const rect = counterparty.getBoundingClientRect();
      results.style.left = `${Math.max(8, rect.left)}px`;
      results.style.top = `${rect.bottom + 4}px`;
      results.style.width = `${Math.max(230, rect.width)}px`;
      results.hidden = false; counterparty.setAttribute("aria-expanded", "true");
    };
    counterparty.addEventListener("change", sync);
    counterparty.addEventListener("input", () => { clearDecision("counterparty_choice"); sync(); renderResults(); });
    category?.addEventListener("input", () => clearDecision("category_choice"));
    counterparty.addEventListener("focus", renderResults);
    counterparty.addEventListener("keydown", (event) => { if (event.key === "Escape") closeResults(); });
    sync();
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".counterparty-picker")) document.querySelectorAll(".counterparty-results").forEach((results) => { results.hidden = true; });
  });
}

// Budget: one-click averages, per-category overrides, and typing means manual.
const budgetForm = document.querySelector('form[action^="/budget"]');
if (budgetForm) {
  const setMode = (row, value) => {
    const mode = row.querySelector(".budget-mode");
    const amount = row.querySelector(".budget-amount");
    if (!mode || !amount) return;
    mode.value = value;
    amount.disabled = value !== "manual";
    if (value !== "manual") amount.value = "";
    amount.placeholder = value === "3" ? "Auto · 3 mo" : value === "6" ? "Auto · 6 mo" : "Enter amount";
  };
  budgetForm.querySelectorAll("[data-budget-mode]").forEach((button) => {
    button.addEventListener("click", () => setMode(button.closest("tr"), button.dataset.budgetMode));
  });
  budgetForm.querySelectorAll(".budget-amount").forEach((amount) => {
    amount.addEventListener("input", () => setMode(amount.closest("tr"), "manual"));
    const row = amount.closest("tr");
    setMode(row, row.querySelector(".budget-mode")?.value || "manual");
  });
  budgetForm.querySelectorAll("[data-budget-all]").forEach((button) => {
    button.addEventListener("click", () => {
      budgetForm.querySelectorAll("tbody tr").forEach((row) => setMode(row, button.dataset.budgetAll));
    });
  });
}

// Account form: show where the chosen type appears on the dashboard.
const typeSelect = document.getElementById("account_type");
if (typeSelect) {
  const groups = JSON.parse(typeSelect.dataset.groups || "{}");
  const target = document.getElementById("group_name");
  typeSelect.addEventListener("change", () => {
    if (target) target.textContent = groups[typeSelect.value] || "";
  });
}

// Bank import: filter the canonical Counterparty chooser as the user types.
document.querySelectorAll("[data-counterparty-filter]").forEach((search) => {
  const select = document.getElementById(search.dataset.counterpartyFilter);
  if (!select) return;
  search.addEventListener("input", () => {
    const query = search.value.trim().toLocaleLowerCase();
    Array.from(select.options).forEach((option) => {
      const fixed = option.value === "" || option.value === "new";
      option.hidden = !fixed && !option.textContent.toLocaleLowerCase().includes(query);
    });
  });
});
