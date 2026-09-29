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

// Date fields accept ISO, day/month/year, and day/month (current year), then normalize to ISO.
const isoDate = (value) => {
  const text = value.trim();
  let year, month, day;
  let match = text.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (match) [, year, month, day] = match;
  else {
    match = text.match(/^(\d{1,2})\/(\d{1,2})(?:\/(\d{2}|\d{4}))?$/);
    if (!match) return null;
    [, day, month, year] = match;
    if (!year) {
      const now = new Date();
      year = String(now.getFullYear() - ((Number(month) - 1 > now.getMonth() ||
        (Number(month) - 1 === now.getMonth() && Number(day) > now.getDate())) ? 1 : 0));
    }
    else if (year.length === 2) year = `20${year}`;
  }
  const y = Number(year), m = Number(month), d = Number(day);
  const check = new Date(Date.UTC(y, m - 1, d));
  if (check.getUTCFullYear() !== y || check.getUTCMonth() !== m - 1 || check.getUTCDate() !== d) return null;
  return `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
};
// Every date field is one component: a typeable ISO text box plus the same
// calendar button. Plain [data-smart-date] boxes and leftover native date
// inputs are upgraded here, so templates only need a text input.
const DATE_ERROR = "Enter a real date like 31/1, 31/1/2026, or 2026-01-31.";
let dateFieldCount = 0;
const normalizeDateField = (input) => {
  if (!input.value.trim()) { input.setCustomValidity(""); return true; }
  const normalized = isoDate(input.value);
  if (normalized) { input.value = normalized; input.setCustomValidity(""); return true; }
  input.setCustomValidity(DATE_ERROR);
  return false;
};
const initDateFields = (root = document) => {
  root.querySelectorAll('input[type="date"]:not(.date-picker-native)').forEach((native) => {
    native.type = "text";
    native.dataset.smartDate = "";
    if (!native.placeholder) native.placeholder = "31/1";
    native.inputMode = "numeric";
    native.autocomplete = "off";
  });
  root.querySelectorAll("[data-smart-date]").forEach((input) => {
    if (input.closest(".iso-date-control")) return;
    if (!input.id) input.id = `date-field-${++dateFieldCount}`;
    if (!input.placeholder) input.placeholder = "31/1";
    const wrapper = document.createElement("span");
    wrapper.className = "iso-date-control";
    input.parentNode.insertBefore(wrapper, input);
    const native = document.createElement("input");
    native.type = "date";
    native.className = "date-picker-native";
    native.tabIndex = -1;
    native.setAttribute("aria-hidden", "true");
    native.dataset.datePickerFor = input.id;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn small date-picker-button";
    button.dataset.openDatePicker = input.id;
    button.setAttribute("aria-label", "Choose date");
    button.title = "Choose date";
    button.textContent = "▦";
    wrapper.append(input, native, button);
  });
  root.querySelectorAll("[data-smart-date]:not([data-date-ready])").forEach((input) => {
    input.dataset.dateReady = "1";
    input.addEventListener("input", () => input.setCustomValidity(""));
    input.addEventListener("blur", () => normalizeDateField(input));
    const form = input.form;
    if (form && !form.dataset.dateSubmitReady) {
      form.dataset.dateSubmitReady = "1";
      form.addEventListener("submit", (event) => {
        const bad = [...form.elements].find((field) => field.matches?.("[data-smart-date]") && !normalizeDateField(field));
        if (bad) { event.preventDefault(); event.stopImmediatePropagation(); bad.reportValidity(); bad.focus(); }
      }, true);
    }
  });
  root.querySelectorAll("[data-open-date-picker]:not([data-picker-ready])").forEach((button) => {
    button.dataset.pickerReady = "1";
    button.addEventListener("click", () => {
      const control = button.closest(".iso-date-control") || root;
      const field = control.querySelector(`[data-date-picker-for="${CSS.escape(button.dataset.openDatePicker)}"]`);
      const text = control.querySelector(`#${CSS.escape(button.dataset.openDatePicker)}`);
      if (!field || !text) return;
      field.value = isoDate(text.value) || "";
      field.addEventListener("change", () => {
        if (field.value) {
          text.value = field.value;
          text.setCustomValidity("");
          text.dispatchEvent(new Event("input", { bubbles: true }));
          text.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }, { once: true });
      try { field.showPicker(); } catch { field.focus(); field.click(); }
    });
  });
};
initDateFields();

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
  if (form.id) buttons.push(...document.querySelectorAll(`button[form="${form.id}"]`));
  buttons.forEach((button) => { if (button !== event.submitter) button.disabled = true; });
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
    if (tools) tools.hidden = selected.length === 0;
    if (count) count.textContent = `${selected.length} selected`;
    if (selectAll) {
      selectAll.checked = visibleChecks().length > 0 && visibleChecks().every((box) => box.checked);
      selectAll.indeterminate = selected.length > 0 && !selectAll.checked;
    }
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
  const whomColumn = document.querySelector(".whom-column");
  const counterparty = row?.querySelector(".counterparty-input");
  const ledger = category.closest(".ledger");
  const internalAccounts = JSON.parse(ledger?.dataset.accounts || "[]");
  if (!cell) return;
  const syncWhom = () => {
    const isCustody = /money held for others/i.test(category.value);
    const target = counterparty?.value.trim() || "";
    const isTransfer = target.startsWith("↔") || internalAccounts.includes(target);
    const visible = isCustody || isTransfer;
    cell.classList.toggle("is-hidden", !visible);
    const anyVisible = document.querySelector(".whom-cell:not(.is-hidden)");
    if (header) header.classList.toggle("is-hidden", !anyVisible);
    if (whomColumn) whomColumn.style.width = anyVisible ? "12%" : "0";
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
  const savedCounterparty = row?.querySelector('[name^="counterparty_choice_"]');
  const whom = cell?.querySelector("input");
  if (!cell) return;
  const sync = () => {
    const visible = /money held for others/i.test(category.selectedOptions[0]?.textContent || "");
    cell.classList.toggle("is-hidden", !visible);
    if (header) header.classList.toggle("is-hidden", !document.querySelector(".import-whom-cell:not(.is-hidden)"));
    if (whom) {
      whom.disabled = !visible;
      if (visible && !whom.value.trim() && savedCounterparty?.value.startsWith("existing:")) {
        whom.value = savedCounterparty.selectedOptions[0]?.dataset.name || "";
      }
    }
  };
  category.addEventListener("change", sync);
  savedCounterparty?.addEventListener("change", sync);
  sync();
});

// A transfer suggestion inferred from explicit note text is always opt-in.
document.querySelectorAll(".import-transfer-suggestion").forEach((button) => {
  button.addEventListener("click", () => {
    const row = button.closest("tr");
    const counterparty = row?.querySelector('[name^="counterparty_"]');
    if (!row || !counterparty) return;
    counterparty.value = button.dataset.target || "";
    const choice = row.querySelector('[name^="counterparty_choice_"]');
    if (choice) choice.value = "";
    const whom = row.querySelector('[name^="whom_"]');
    if (whom && !whom.disabled && button.dataset.owner) whom.value = button.dataset.owner;
    button.textContent = `Transfer to ${counterparty.value} selected`;
    button.disabled = true;
  });
});

// Register: Escape cancels an edit.
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  const cancel = document.querySelector("[data-cancel]");
  if (cancel && e.target.closest("tr.editing")) location.href = cancel.href;
});
// Format money as the user types (1,000.50) while retaining a plain numeric value on submit.
const setupMoneyInput = (input) => {
  if (input.dataset.moneyFormatReady) return;
  input.dataset.moneyFormatReady = "true";
  input.setAttribute("autocomplete", "off");
  input.addEventListener("input", () => {
    const before = input.value;
    const caret = input.selectionStart ?? before.length;
    const clean = (value) => {
      const filtered = value.replace(/,/g, "").replace(/[^0-9.\-]/g, "");
      const sign = filtered.startsWith("-") ? "-" : "";
      const unsigned = filtered.replace(/-/g, "");
      const decimalAt = unsigned.indexOf(".");
      const normalized = decimalAt < 0
        ? unsigned
        : unsigned.slice(0, decimalAt) + "." + unsigned.slice(decimalAt + 1).replace(/\./g, "");
      return sign + normalized;
    };
    const raw = clean(before);
    const charactersBeforeCaret = clean(before.slice(0, caret)).length;
    const sign = raw.startsWith("-") ? "-" : "";
    const unsigned = raw.replace(/-/g, "");
    const decimalAt = unsigned.indexOf(".");
    const whole = decimalAt < 0 ? unsigned : unsigned.slice(0, decimalAt);
    const fraction = decimalAt < 0 ? null : unsigned.slice(decimalAt + 1);
    const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    input.value = sign + grouped + (fraction !== null ? "." + fraction : "");
    if (document.activeElement === input) {
      let seen = 0, next = 0;
      while (next < input.value.length && seen < charactersBeforeCaret) {
        if (input.value[next] !== ",") seen++;
        next++;
      }
      input.setSelectionRange(next, next);
    }
  });
  if (input.value) input.dispatchEvent(new Event("input"));
};
const moneySelector = 'input.money-input, input[inputmode="decimal"]:not([type="number"])';
document.querySelectorAll(moneySelector).forEach(setupMoneyInput);
const moneyPopup = document.getElementById("app-popup");
if (moneyPopup) new MutationObserver(() => moneyPopup.querySelectorAll(moneySelector).forEach(setupMoneyInput))
  .observe(moneyPopup, {childList:true, subtree:true});

// Register: Counterparty and Category work together.
//  - an owned account as counterparty -> transfer: no category is needed
//  - a known counterparty -> fill its most recent category when available
// Show the per-unit price implied by the all-in total on investment trades.
document.querySelectorAll(".trade-total").forEach((total) => {
  const form = total.closest("form");
  const quantity = form?.querySelector(".quantity-input");
  const preview = form?.querySelector(".unit-price-preview");
  if (!quantity || !preview) return;
  const feeInput = form.querySelector('[name="fees"]');
  const feeChoice = form.querySelector('[data-fees-excluded]');
  const feeField = form.querySelector('[data-fees-field]');
  const syncFeeField = () => {
    if (!feeChoice || !feeField) return;
    feeField.hidden = !feeChoice.checked;
    if (feeInput) feeInput.disabled = !feeChoice.checked;
  };
  const update = () => {
    const units = Number(quantity.value.replace(/,/g, ""));
    const amount = Number(total.value.replace(/,/g, ""));
    const fee = Number((feeInput?.value || "0").replace(/,/g, "")) || 0;
    const included = !feeChoice?.checked;
    const gross = amount + (included ? (form.dataset.tradeKind === "buy" ? -fee : fee) : 0);
    preview.value = units > 0 && gross > 0
      ? new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 }).format(gross / units)
      : "";
  };
  quantity.addEventListener("input", update);
  total.addEventListener("input", update);
  feeInput?.addEventListener("input", update);
  feeChoice?.addEventListener("change", () => { syncFeeField(); update(); });
  syncFeeField();
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
  const unitsField = document.getElementById("investment-units-field");
  const action = document.getElementById("investment-action");
  const total = document.getElementById("investment-total");
  const dividendBasis = document.getElementById("investment-dividend-basis");
  const dividendBasisField = document.getElementById("investment-dividend-basis-field");
  const unitPrice = document.getElementById("investment-unit-price");
  const fees = document.getElementById("investment-fees");
  const feesExcluded = document.getElementById("investment-fees-included");
  const feesField = document.getElementById("investment-fees-field");
  const feesToggleField = document.getElementById("investment-fees-toggle-field");
  const priceField = document.getElementById("investment-price-field");
  const basis = form.querySelector('[name="price_basis"]');
  const amountLabel = document.getElementById("investment-total-label");
  const positionHint = document.getElementById("trade-position-hint");
  const entryHint = document.getElementById("investment-entry-hint");
  const addButton = form.querySelector(".investment-entry-submit");
  let selected = instruments.find((item) => item.key === selectedKey.value) || null;
  let activeResult = 0;
  const number = (input) => {
    const value = input.value.replace(/,/g, "").trim();
    if (!value || value === "-" || value === "+") return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const formatted = (value, decimals = 6) => {
    if (!(value > 0)) return "";
    const maximumFractionDigits = Math.max(0, Number.isFinite(decimals) ? decimals : 6);
    const minimumFractionDigits = Math.min(2, maximumFractionDigits);
    return new Intl.NumberFormat(undefined, { minimumFractionDigits, maximumFractionDigits }).format(value);
  };
  const sync = () => {
    const actionKind = action?.value || "buy";
    const rawQty = number(units);
    const qty = actionKind === "dividend" || rawQty === null ? null : (actionKind === "sell" ? -rawQty : rawQty);
    const cashTotal = number(total);
    const price = number(unitPrice);
    const fee = number(fees) || 0;
    const included = !feesExcluded?.checked;
    const isDividend = actionKind === "dividend";
    form.classList.toggle("is-dividend", isDividend);
    form.querySelectorAll("[data-trade-action]").forEach((button) => {
      const active = button.dataset.tradeAction === actionKind;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
    if (unitsField) unitsField.hidden = isDividend;
    units.disabled = isDividend;
    if (dividendBasisField) dividendBasisField.hidden = !isDividend;
    if (priceField) priceField.hidden = isDividend;
    if (feesField) feesField.hidden = isDividend || !feesExcluded?.checked;
    if (feesToggleField) feesToggleField.hidden = isDividend;
    if (fees) fees.disabled = isDividend || !feesExcluded?.checked;
    if (feesExcluded) feesExcluded.disabled = isDividend;
    if (unitPrice) unitPrice.disabled = isDividend;
    if (isDividend) {
      const perShare = dividendBasis?.value === "per_share";
      amountLabel.textContent = perShare ? "Dividend per share" : "Total dividend amount";
      total.placeholder = perShare ? "Amount per share" : "Total amount received";
    }
    else {
      amountLabel.textContent = actionKind === "sell" ? "Total received" : "Total paid";
      total.placeholder = "Total amount";
    }
    if (qty !== null && Math.abs(qty) > 0) {
      if (basis.value === "unit_price" && price !== null) {
        const gross = Math.abs(qty) * price;
        total.value = formatted(gross + (included ? (qty > 0 ? fee : -fee) : 0), 2);
      } else if (cashTotal !== null) {
        const gross = cashTotal + (included ? (qty > 0 ? -fee : fee) : 0);
        unitPrice.value = formatted(gross / Math.abs(qty));
      }
    }
    let exceeds = false;
    if (selected && actionKind === "sell" && qty !== null) {
      const owned = Number(selected.holding || 0);
      exceeds = Math.abs(qty) > owned;
      positionHint.textContent = exceeds
        ? `You have ${formatted(owned, selected.decimals)} ${selected.unit}(s); you cannot sell ${formatted(Math.abs(qty), selected.decimals)}.`
        : `You hold ${formatted(owned, selected.decimals)} ${selected.unit}(s) here.`;
    } else if (selected) {
      positionHint.textContent = `You hold ${formatted(Number(selected.holding || 0), selected.decimals)} ${selected.unit}(s) here.`;
    }
    if (isDividend) entryHint.textContent = dividendBasis?.value === "per_share"
      ? "The total dividend uses this rate × shares held by the selected owner on the transaction date."
      : "Enter the total dividend received. The selected owner must hold shares on the transaction date.";
    else entryHint.textContent = actionKind === "sell"
      ? "Enter the number of units sold. Choose whether the sale total includes fees below."
      : "Enter the number of units bought. Fees are included in your cost basis.";
    addButton.disabled = exceeds;
  };
  const renderResults = () => {
    const query = search.value.trim().toLocaleLowerCase();
    results.replaceChildren();
    if (!query) { results.hidden = true; search.setAttribute("aria-expanded", "false"); return; }
    const matches = instruments.filter((item) => `${item.name} ${item.ticker} ${item.kind}`
      .toLocaleLowerCase().includes(query)).slice(0, 12);
    activeResult = 0;
    if (!matches.length) {
      const empty = document.createElement("div");
      empty.className = "instrument-result";
      empty.textContent = "No match in your list. Choose a listed stock or fund.";
      results.append(empty);
    }
    matches.forEach((item, index) => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "instrument-result"; button.setAttribute("role", "option");
      button.setAttribute("aria-selected", index === activeResult ? "true" : "false");
      if (index === activeResult) button.classList.add("is-active");
      const name = document.createElement("span"); name.textContent = item.name;
      const ticker = document.createElement("small"); ticker.textContent = `${item.kind} · ${item.ticker}`;
      button.append(name, ticker);
      const choose = () => {
        selected = item; selectedKey.value = item.key;
        selectedLabel.value = `${item.name} · ${item.ticker}`;
        search.value = selectedLabel.value;
        results.hidden = true; search.setAttribute("aria-expanded", "false"); sync();
      };
      button.addEventListener("click", choose);
      button.dataset.instrumentIndex = String(index);
      results.append(button);
    });
    results.hidden = false; search.setAttribute("aria-expanded", "true");
  };
  search.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (results.hidden) renderResults();
      const options = [...results.querySelectorAll('[role="option"]')];
      if (!options.length) return;
      event.preventDefault();
      activeResult = (activeResult + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
      options.forEach((option, index) => {
        option.classList.toggle("is-active", index === activeResult);
        option.setAttribute("aria-selected", index === activeResult ? "true" : "false");
      });
    } else if (event.key === "Enter") {
      // Enter in the typeahead chooses a result; it must not submit the trade
      // form with an uncommitted, display-only instrument name.
      event.preventDefault();
      const options = [...results.querySelectorAll('[role="option"]')];
      if (options.length) options[Math.min(activeResult, options.length - 1)].click();
      else renderResults();
    } else if (event.key === "Escape" && !results.hidden) {
      event.preventDefault(); results.hidden = true; search.setAttribute("aria-expanded", "false");
    }
  });
  search.addEventListener("input", () => {
    selected = null; selectedKey.value = ""; selectedLabel.value = "";
    positionHint.textContent = "Choose an instrument from the results."; renderResults(); sync();
  });
  search.addEventListener("focus", renderResults);
  units.addEventListener("input", sync);
  action?.addEventListener("change", sync);
  form.querySelectorAll("[data-trade-action]").forEach((button) => {
    button.addEventListener("click", () => {
      action.value = button.dataset.tradeAction;
      action.dispatchEvent(new Event("change", { bubbles: true }));
    });
  });
  total.addEventListener("input", () => { basis.value = "total"; sync(); });
  dividendBasis?.addEventListener("change", sync);
  unitPrice.addEventListener("input", () => { basis.value = "unit_price"; sync(); });
  fees?.addEventListener("input", sync);
  feesExcluded?.addEventListener("change", sync);
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

// Category picker: one alphabetized header per activity, with broad categories nested below.
const categoryCatalogueNode = document.getElementById("category-catalogue");
if (categoryCatalogueNode) {
  const categories = JSON.parse(categoryCatalogueNode.textContent || "[]");
  const closeCategoryResults = (input, results) => {
    results.hidden = true;
    input.setAttribute("aria-expanded", "false");
  };
  document.querySelectorAll(".category-input").forEach((input) => {
    const results = document.getElementById(input.dataset.categoryResults);
    const formId = input.getAttribute("form");
    let activeIndex = -1;
    const matchesFor = () => {
      const query = input.value.trim().toLocaleLowerCase().replaceAll("›", " ").replace(/\s+/g, " ");
      return categories.filter((item) => !query ||
        `${item.parent} ${item.name} ${item.label}`.toLocaleLowerCase().replaceAll("›", " ").replace(/\s+/g, " ").includes(query));
    };
    const render = () => {
      if (input.disabled || document.activeElement !== input) return;
      results.replaceChildren();
      activeIndex = -1;
      const allMatches = matchesFor();
      const matches = allMatches.slice(0, 30);
      const groups = new Map();
      matches.forEach((item) => {
        if (!groups.has(item.parent)) groups.set(item.parent, []);
        groups.get(item.parent).push(item);
      });
      [...groups.keys()].sort((a, b) => a.localeCompare(b)).forEach((parent) => {
        const heading = document.createElement("div");
        heading.className = "category-group-title";
        heading.textContent = parent;
        results.append(heading);
        groups.get(parent).sort((a, b) => a.name.localeCompare(b.name)).forEach((item) => {
          const option = document.createElement("button");
          option.type = "button";
          option.className = "category-option";
          option.setAttribute("role", "option");
          option.textContent = item.name;
          option.addEventListener("mousedown", (event) => event.preventDefault());
          option.addEventListener("click", () => {
            input.value = item.name;
            input.dispatchEvent(new Event("input", { bubbles: true }));
            input.dataset.autofilled = "false";
            const choice = document.createElement("input");
            choice.type = "hidden"; choice.name = "category_choice"; choice.value = String(item.id);
            choice.setAttribute("form", formId);
            input.closest(".category-picker").append(choice);
            closeCategoryResults(input, results);
          });
          results.append(option);
        });
      });
      if (allMatches.length > matches.length) {
        const hint = document.createElement("div");
        hint.className = "category-group-title";
        hint.textContent = "Type to find more categories";
        results.append(hint);
      }
      if (!matches.length) {
        const empty = document.createElement("div");
        empty.className = "category-group-title";
        empty.textContent = "No matching category";
        results.append(empty);
      }
      const rect = input.getBoundingClientRect();
      results.style.left = `${Math.max(8, rect.left)}px`;
      results.style.top = `${rect.bottom + 4}px`;
      results.style.width = `${Math.max(230, rect.width)}px`;
      results.hidden = false;
      input.setAttribute("aria-expanded", "true");
    };
    input.addEventListener("input", () => {
      document.querySelector(`input[type="hidden"][form="${formId}"][name="category_choice"]`)?.remove();
      input.dataset.autofilled = "false";
      render();
    });
    input.addEventListener("focus", render);
    input.addEventListener("focus", () => {
      if (input.dataset.autofilled === "true") input.select();
    });
    input.addEventListener("click", () => {
      if (input.dataset.autofilled === "true") input.select();
    });
    input.addEventListener("keydown", (event) => {
      const options = [...results.querySelectorAll(".category-option")];
      if (event.key === "Escape") closeCategoryResults(input, results);
      else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        if (results.hidden || !options.length) return;
        event.preventDefault();
        activeIndex = (activeIndex + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
        options.forEach((option, index) => {
          option.setAttribute("aria-selected", String(index === activeIndex));
          if (index === activeIndex) option.scrollIntoView({ block: "nearest" });
        });
      } else if (event.key === "Enter" && !results.hidden && options.length) {
        event.preventDefault();
        options[activeIndex < 0 ? 0 : activeIndex].click();
        document.querySelector(`[name="notes"][form="${formId}"]`)?.focus();
      }
    });
    input.addEventListener("blur", () => setTimeout(() => closeCategoryResults(input, results), 120));
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".category-picker")) {
      document.querySelectorAll(".category-results").forEach((results) => { results.hidden = true; });
    }
  });
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
        else if (!category.value) {
          const knownName = parties.find((name) => name.toLocaleLowerCase() === counterparty.value.trim().toLocaleLowerCase());
          const savedCategory = knownName ? known[knownName] : null;
          if (savedCategory?.id && savedCategory?.name) {
            category.value = savedCategory.name;
            category.dispatchEvent(new Event("input", { bubbles: true }));
            category.dataset.autofilled = "true";
            const choice = document.createElement("input");
            choice.type = "hidden"; choice.name = "category_choice"; choice.value = String(savedCategory.id);
            choice.setAttribute("form", form);
            category.closest(".category-picker").append(choice);
          }
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
      addGroup("People & businesses", saved, "External");
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
    category?.addEventListener("input", () => {
      clearDecision("category_choice");
      delete category.dataset.autofilled;
    });
    counterparty.addEventListener("focus", renderResults);
    counterparty.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeResults();
      else if (event.key === "Enter" && !results.hidden) {
        const first = results.querySelector(".counterparty-option");
        if (first) {
          event.preventDefault();
          first.click();
          category?.focus();
        }
      }
    });
    sync();
  });
  document.addEventListener("click", (event) => {
    if (!event.target.closest(".counterparty-picker")) document.querySelectorAll(".counterparty-results").forEach((results) => { results.hidden = true; });
  });
}

// Existing investment transactions save a complete valid edit on field commit.
document.querySelectorAll("form[data-autosave-existing]").forEach((form) => {
  const status = form.querySelector(".inline-save-status");
  let saved = new URLSearchParams(new FormData(form)).toString(), busy = false;
  const save = async () => {
    const data = new URLSearchParams(new FormData(form)), next = data.toString();
    if (busy || next === saved || !form.reportValidity()) return;
    busy = true; status.textContent = "Saving…";
    try {
      const response = await fetch(form.action || location.href, { method: "POST", body: data,
        headers: { "X-Requested-With": "fetch" } });
      if (!response.ok) throw Error((await response.text()) || "Could not save. Correct the value and retry.");
      saved = next; status.textContent = "Saved";
    } catch (error) { status.textContent = error.message || "Could not save. Correct the value and retry."; }
    finally { busy = false; }
  };
  form.querySelectorAll("input,select,textarea").forEach((field) => {
    field.addEventListener("change", () => save());
    field.addEventListener("blur", save);
    field.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && field.tagName !== "TEXTAREA") { event.preventDefault(); save(); }
    });
  });
});

// Budget: one-click averages, per-category overrides, and typing means manual.
const budgetForm = document.querySelector("#budget-editor-form");
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
document.querySelectorAll("[data-owner-filter]").forEach((search) => {
  const select = document.getElementById(search.dataset.ownerFilter);
  if (!select) return;
  search.addEventListener("input", () => {
    const query = search.value.trim().toLocaleLowerCase();
    Array.from(select.options).forEach((option) => {
      option.hidden = option.value !== "" && !option.textContent.toLocaleLowerCase().includes(query);
    });
    if (select.selectedOptions[0]?.hidden) select.value = "";
  });
  select.addEventListener("change", () => { search.value = ""; });
});
document.addEventListener("input", (event) => {
  const search = event.target.closest("[data-option-filter]");
  if (!search) return;
  const select = document.getElementById(search.dataset.optionFilter);
  if (!select) return;
  const query = search.value.trim().toLocaleLowerCase();
  Array.from(select.options).forEach((option) => {
    option.hidden = option.value !== "" && !option.textContent.toLocaleLowerCase().includes(query);
  });
  if (select.selectedOptions[0]?.hidden) select.value = "";
});
document.addEventListener("change", (event) => {
  if (!(event.target instanceof HTMLSelectElement)) return;
  const search = document.querySelector(`[data-option-filter="${CSS.escape(event.target.id)}"]`);
  if (search) search.value = "";
});

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

// One contextual dialog for server-rendered forms and transaction details.
(() => {
  const dialog = document.getElementById("app-popup");
  const content = document.getElementById("app-popup-content");
  if (!dialog || !content) return;
  let opener = null;
  let baseUrl = location.href;
  let baseScroll = 0;
  let dirty = false;
  let activePopupUrl = null;

  const canDiscard = () => !dirty || window.confirm("Discard your unsaved changes?");
  const close = (goBack = true) => {
    if (!dialog.open || !canDiscard()) return false;
    dirty = false;
    dialog.close();
    document.body.classList.remove("popup-open");
    content.replaceChildren();
    if (goBack && history.state?.lightningPopup) history.back();
    else if (opener?.isConnected) opener.focus();
    window.scrollTo({ top: baseScroll, behavior: "instant" });
    return true;
  };
  const extract = (doc) => {
    const main = doc.querySelector("main.main") || doc.querySelector("main");
    return main?.innerHTML || doc.body.innerHTML;
  };
  const show = (html, title = "Dialog") => {
    content.innerHTML = html;
    const h = content.querySelector("h1, h2, [data-popup-title]");
    if (h) { h.id = "app-popup-title"; dialog.setAttribute("aria-labelledby", h.id); }
    else { dialog.removeAttribute("aria-labelledby"); dialog.setAttribute("aria-label", title); }
    dirty = false;
    document.body.classList.add("popup-open");
    if (!dialog.open) dialog.showModal();
    initPopupFields();
    initTransactionForm();
    requestAnimationFrame(() => (content.querySelector("[autofocus], input:not([type=hidden]), select, button, a[href]") ||
      dialog.querySelector("[data-popup-close]")).focus());
  };
  const initPopupFields = () => {
    initDateFields(content);
    const type = content.querySelector("#account_type"), help = content.querySelector("#account-type-help");
    if (type && help && !type.dataset.popupReady) {
      type.dataset.popupReady = "1";
      const update = () => {
        help.textContent = type.value === "DEPOSIT"
          ? "Certificate or time deposit: include the term, annual return, and maturity date in Notes."
          : type.value === "PHYSICAL_ASSET" ? "Add named items such as a ring after creating this account."
          : type.value === "BROKERAGE" ? "Record brokerage cash here before buying investments."
          : "";
      };
      type.addEventListener("change", update); update();
    }
    content.querySelectorAll("[data-karat-reference]").forEach((select) => {
      if (select.dataset.popupKaratReady) return;
      select.dataset.popupKaratReady = "1";
      const karat = content.querySelector("#karat");
      const filter = () => {
        const selected = select.value;
        let kept = false;
        [...select.options].forEach((option) => {
          const match = !option.value || option.dataset.karat === karat?.value;
          option.hidden = !match; option.disabled = !match;
          if (option.value === selected && match) kept = true;
        });
        if (!kept) select.value = "";
      };
      karat?.addEventListener("change", filter); filter();
    });
    content.querySelectorAll("[data-popup-autosave]").forEach((form) => {
      if (form.dataset.popupAutosaveReady) return;
      form.dataset.popupAutosaveReady = "1";
      const status = form.querySelector("[data-autosave-status],.inline-save-status");
      let saved = new URLSearchParams(new FormData(form)).toString();
      let busy = false;
      const save = async () => {
        const data = new URLSearchParams(new FormData(form));
        const next = data.toString();
        if (busy || next === saved || !form.reportValidity()) return;
        busy = true;
        if (status) status.textContent = "Saving…";
        let succeeded = false;
        try {
          const response = await fetch(form.action || location.href, { method: "POST", body: data,
            headers: { "X-Requested-With": "fetch" } });
          if (!response.ok) throw Error((await response.text()) || "Could not save. Correct the value and retry.");
          saved = next;
          succeeded = true;
          if (status) status.textContent = "Saved";
          if (new URLSearchParams(new FormData(form)).toString() === saved) dirty = false;
        } catch (error) {
          if (status) status.textContent = error.message || "Could not save. Correct the value and retry.";
        } finally {
          busy = false;
          if (succeeded && new URLSearchParams(new FormData(form)).toString() !== saved) queueMicrotask(save);
        }
      };
      form.querySelectorAll("input,select,textarea").forEach((field) => {
        field.addEventListener("change", () => queueMicrotask(save));
        field.addEventListener("blur", save);
        field.addEventListener("keydown", (event) => {
          if (event.key === "Enter" && field.tagName !== "TEXTAREA") { event.preventDefault(); save(); }
        });
      });
    });
  };
  const initTransactionForm = () => {
    const root = content.querySelector("[data-transaction-form]");
    const form = root?.querySelector("form");
    if (!form || form.dataset.popupInitialized) return;
    form.dataset.popupInitialized = "1";
    const kinds = [...form.querySelectorAll('[name="kind"]')];
    const amount = form.querySelector('[name="amount"]');
    const owner = form.querySelector('[name="owner_id"]');
    const note = form.querySelector('[data-transaction-effect]');
    const category = form.querySelector('[name="category_id"]');
    const destination = form.querySelector('[name="to_account_id"]');
    const update = () => {
      const kind = kinds.find((input) => input.checked)?.value || "out";
      form.querySelectorAll(".transfer-only").forEach((field) => field.hidden = kind !== "transfer");
      form.querySelectorAll(".money-only").forEach((field) => field.hidden = kind === "transfer");
      if (category) [...category.options].forEach((option) => {
        option.hidden = option.value !== "" && option.dataset.movement !== (kind === "out" ? "OUTFLOW" : "INFLOW");
        if (option.hidden && option.selected) category.value = "";
      });
      if (category) { category.disabled = kind === "transfer"; category.required = kind !== "transfer"; }
      if (destination) destination.required = kind === "transfer";
      const value = Number((amount.value || "").replaceAll(",", ""));
      const shown = Number.isFinite(value) && value > 0 ? new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(value) : "…";
      const account = root.dataset.accountName, currency = root.dataset.currency;
      if (kind === "transfer") {
        const to = destination.selectedOptions[0]?.textContent || "the selected account";
        note.textContent = `Cash in ${account} decreases by ${shown} ${currency}; cash in ${to} increases by the same amount.`;
      } else {
        const own = owner.selectedOptions[0]?.textContent || "you";
        note.textContent = `Cash in ${account} ${kind === "out" ? "decreases" : "increases"} by ${shown} ${currency}; balance owned by ${own}.`;
      }
    };
    form.addEventListener("input", update); form.addEventListener("change", update); update();
  };
  const openUrl = async (url, trigger, push = true) => {
    const replacing = dialog.open;
    const priorOpener = opener;
    if (dialog.open && !close(false)) return;
    opener = replacing ? priorOpener : (trigger || document.activeElement);
    if (!replacing) {
      baseUrl = location.href;
      baseScroll = window.scrollY;
    }
    const destination = new URL(url, location.href);
    if (!destination.searchParams.has("return_to")) destination.searchParams.set("return_to", baseUrl);
    const response = await fetch(destination.href, { headers: { "X-Lightning-Popup": "1" } });
    const doc = new DOMParser().parseFromString(await response.text(), "text/html");
    show(extract(doc), doc.title);
    content.querySelectorAll("form:not([action])").forEach((form) => { form.action = destination.href; });
    if (push) {
      activePopupUrl = destination.href;
      const state = { lightningPopup: true, baseUrl, baseScroll };
      if (replacing) history.replaceState(state, "", destination.href);
      else history.pushState(state, "", destination.href);
    }
  };

  document.addEventListener("click", (event) => {
    const closeButton = event.target.closest("[data-popup-close]");
    if (closeButton) { event.preventDefault(); close(); return; }
    const link = event.target.closest("a[data-popup-open]");
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    openUrl(link.href, link).catch(() => { location.href = link.href; });
  });
  dialog.addEventListener("cancel", (event) => { event.preventDefault(); close(); });
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) close();
  });
  content.addEventListener("input", (event) => {
    if (event.target.closest("form")) dirty = true;
  });
  content.addEventListener("change", (event) => {
    if (event.target.closest("form")) dirty = true;
  });
  content.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") return;
    const focusable = [...content.querySelectorAll("a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex='-1'])")];
    if (!focusable.length) return;
    if (event.shiftKey && document.activeElement === focusable[0]) { event.preventDefault(); focusable.at(-1).focus(); }
    else if (!event.shiftKey && document.activeElement === focusable.at(-1)) { event.preventDefault(); focusable[0].focus(); }
  });
  content.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.target === "_blank") return;
    event.preventDefault();
    const submit = form.querySelector("button[type=submit]:not([form]),button:not([type])") || form.querySelector("button[type=submit]");
    const status = content.querySelector("[data-popup-status]");
    if (status) status.textContent = "Saving…";
    if (submit) submit.disabled = true;
    try {
      const response = await fetch(form.action || location.href, {
        method: (form.method || "POST").toUpperCase(), body: new FormData(form),
        headers: { "X-Lightning-Popup": "1" }, redirect: "follow"
      });
      const text = await response.text();
      if (response.status >= 400) {
        const doc = new DOMParser().parseFromString(text, "text/html");
        show(extract(doc), doc.title);
        dirty = true;
        const firstError = content.querySelector(".flash.error,.error,[aria-invalid=true]");
        firstError?.focus?.();
      } else {
        const msg = new URL(response.url).searchParams.get("msg");
        const goToResponse = form.dataset.popupReturn === "response";
        const keepInPopup = form.dataset.popupReturn === "popup";
        if (keepInPopup) {
          const doc = new DOMParser().parseFromString(text, "text/html");
          show(extract(doc), doc.title);
          activePopupUrl = response.url;
          history.pushState({ lightningPopup: true, baseUrl, baseScroll }, "", response.url);
          return;
        }
        const next = new URL(goToResponse ? response.url : baseUrl, location.href);
        close(false);
        history.replaceState(null, "", next.pathname + next.search + next.hash);
        if (msg) sessionStorage.setItem("lightning-popup-success", msg);
        if (goToResponse) location.href = next.href;
        else {
          sessionStorage.setItem("lightning-popup-scroll", String(baseScroll));
          location.reload();
        }
      }
    } catch (error) {
      if (status) status.textContent = "Could not save. Check your connection and try again.";
      if (submit) submit.disabled = false;
    }
  });
  window.addEventListener("popstate", () => {
    if (!dialog.open) return;
    if (!close(false)) {
      history.pushState({ lightningPopup: true, baseUrl, baseScroll }, "", activePopupUrl || location.href);
      return;
    }
    const base = new URL(baseUrl, location.href);
    if (base.pathname + base.search + base.hash !== location.pathname + location.search + location.hash) location.reload();
  });
  const savedScroll = sessionStorage.getItem("lightning-popup-scroll");
  if (savedScroll !== null) {
    sessionStorage.removeItem("lightning-popup-scroll");
    requestAnimationFrame(() => window.scrollTo({ top: Number(savedScroll) || 0, behavior: "instant" }));
  }
  const success = sessionStorage.getItem("lightning-popup-success");
  if (success) {
    sessionStorage.removeItem("lightning-popup-success");
    const flash = document.querySelector(".flash");
    if (flash) flash.textContent = success;
  }
  if (new URLSearchParams(location.search).get("popup") === "1" && location.pathname.startsWith("/transactions/")) {
    baseUrl = location.pathname + location.search.replace(/(?:\?|&)popup=1/, "");
    baseScroll = 0;
    show(document.querySelector("main.main")?.innerHTML || "", document.title);
  }
})();

// Shared period controls use separate month/year fields and a bounded scroll list.
document.querySelectorAll("[data-month-picker]").forEach((picker) => {
  const monthValue = picker.querySelector("[data-month-select]");
  const monthField = picker.querySelector("[data-month-part]");
  const yearField = picker.querySelector("[data-year-toggle]");
  const yearList = picker.querySelector("[data-year-options]");
  const form = picker.matches("form") ? picker : picker.closest("form") || picker.querySelector("form");
  const currentMonth = picker.dataset.currentMonth;
  const selectedMonth = picker.dataset.selectedMonth || currentMonth;
  const monthlyButton = form?.querySelector('[name="period"][value="month"]');
  if (monthlyButton) monthlyButton.addEventListener("click", () => {
    if (monthField && yearField) {
      monthField.value = currentMonth.slice(5, 7);
      yearField.textContent = currentMonth.slice(0, 4);
      monthValue.value = currentMonth;
    }
  });
  if (!monthValue || !monthField || !yearField || !yearList || !form || !/^\d{4}-\d{2}$/.test(currentMonth || "")) return;
  const toIndex = (value) => {
    const [year, month] = value.split("-").map(Number);
    return year * 12 + month - 1;
  };
  const fromIndex = (index) => `${Math.floor(index / 12)}-${String(index % 12 + 1).padStart(2, "0")}`;
  const currentIndex = toIndex(currentMonth);
  const currentYear = Number(currentMonth.slice(0, 4));
  const selectedYear = Number(selectedMonth.slice(0, 4));
  const firstYear = Math.min(currentYear - 50, selectedYear);
  const monthNames = Array.from({ length: 12 }, (_, index) => new Date(Date.UTC(2020, index, 1)).toLocaleDateString(undefined, { month: "long", timeZone: "UTC" }));
  monthNames.forEach((name, index) => {
    const option = document.createElement("option");
    option.value = String(index + 1).padStart(2, "0");
    option.textContent = name;
    monthField.append(option);
  });
  for (let year = currentYear; year >= firstYear; year -= 1) {
    const option = document.createElement("button");
    option.type = "button";
    option.className = "year-picker-option";
    option.setAttribute("role", "option");
    option.textContent = String(year);
    option.dataset.year = String(year);
    yearList.append(option);
  }
  const [initialYear, initialMonth] = selectedMonth.split("-");
  monthField.value = initialMonth;
  yearField.textContent = initialYear;
  const closeYears = () => {
    yearList.hidden = true;
    yearField.setAttribute("aria-expanded", "false");
  };
  const updateValue = () => {
    monthValue.value = `${yearField.textContent}-${monthField.value}`;
    const selectedIndex = toIndex(monthValue.value);
    picker.querySelector('[data-month-shift="-1"]').disabled = selectedIndex <= toIndex(`${firstYear}-01`);
    picker.querySelector('[data-month-shift="1"]').disabled = selectedIndex >= currentIndex;
  };
  const submit = () => { updateValue(); form.requestSubmit(); };
  yearField.addEventListener("click", () => {
    yearList.hidden = !yearList.hidden;
    yearField.setAttribute("aria-expanded", String(!yearList.hidden));
    if (!yearList.hidden) {
      const current = yearList.querySelector(`[data-year="${yearField.textContent}"]`);
      if (current) yearList.scrollTop = current.offsetTop - yearList.offsetTop;
    }
  });
  yearList.addEventListener("click", (event) => {
    const option = event.target.closest("[data-year]");
    if (!option) return;
    yearField.textContent = option.dataset.year;
    closeYears();
    submit();
  });
  document.addEventListener("click", (event) => { if (!picker.contains(event.target)) closeYears(); });
  yearField.addEventListener("keydown", (event) => { if (event.key === "Escape") closeYears(); });
  monthField.addEventListener("change", submit);
  picker.querySelectorAll("[data-month-shift]").forEach((button) => {
    button.addEventListener("click", () => {
      const nextMonth = fromIndex(toIndex(monthValue.value) + Number(button.dataset.monthShift));
      if (toIndex(nextMonth) > currentIndex) return;
      yearField.textContent = nextMonth.slice(0, 4);
      monthField.value = nextMonth.slice(5, 7);
      submit();
    });
  });
  updateValue();
});
