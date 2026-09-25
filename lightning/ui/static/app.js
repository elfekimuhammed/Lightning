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
      let seen = 0, next = 0;
      while (next < input.value.length && seen < digitsBeforeCaret) {
        if (/\d/.test(input.value[next])) seen++;
        next++;
      }
      input.setSelectionRange(next, next);
    }
  });
});

// Register: "To" and "Category" work together.
//  - one of your accounts in To  -> a transfer: the category box is not needed
//  - a To used before            -> its last category is filled in (if empty)
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

const ledger = document.querySelector(".ledger");
if (ledger) {
  const known = JSON.parse(ledger.dataset.payees || "{}");
  const accounts = new Set(JSON.parse(ledger.dataset.accounts || "[]").map((a) => a.toLowerCase()));
  document.querySelectorAll(".to-input").forEach((to) => {
    const form = to.getAttribute("form");
    const category = document.querySelector(`.category-input[form="${form}"]`);
    const sync = () => {
      const isTransfer = accounts.has(to.value.trim().toLowerCase());
      if (category) {
        category.disabled = isTransfer;
        category.placeholder = isTransfer ? "Transfer — no category needed" : "Category — type to search";
        if (isTransfer) category.value = "";
        else if (!category.value && known[to.value]) category.value = known[to.value];
      }
    };
    to.addEventListener("change", sync);
    to.addEventListener("input", () => { if (category && category.disabled) sync(); });
    sync();
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
