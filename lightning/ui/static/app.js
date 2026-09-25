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

// Register: "To" and "Category" work together.
//  - one of your accounts in To  -> a transfer: the category box is not needed
//  - a To used before            -> its last category is filled in (if empty)
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

// Account form: show where the chosen type appears on the dashboard.
const typeSelect = document.getElementById("account_type");
if (typeSelect) {
  const groups = JSON.parse(typeSelect.dataset.groups || "{}");
  const target = document.getElementById("group_name");
  typeSelect.addEventListener("change", () => {
    if (target) target.textContent = groups[typeSelect.value] || "";
  });
}
