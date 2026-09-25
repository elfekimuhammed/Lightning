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

// Register: click a row to edit it in place; "+ Add New" jumps to the entry row.
document.addEventListener("click", (e) => {
  const row = e.target.closest("tr[data-href]");
  if (row && !e.target.closest("a, button, input, select")) location.href = row.dataset.href;
  const focus = e.target.closest("[data-focus]");
  if (focus) document.getElementById(focus.dataset.focus)?.focus();
});

// Register: Escape cancels an edit.
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  const cancel = document.querySelector("[data-cancel]");
  if (cancel && e.target.closest("tr.editing")) location.href = cancel.href;
});

// Register: a payee used before fills in its last category (only if none is chosen yet).
const known = JSON.parse(document.querySelector("[data-payees]")?.dataset.payees || "{}");
document.querySelectorAll(".payee-input").forEach((payee) => {
  payee.addEventListener("change", () => {
    const choice = document.querySelector(`select.choice-input[form="${payee.getAttribute("form")}"]`);
    if (choice && !choice.value && known[payee.value]) choice.value = known[payee.value];
  });
});

// Account form: show where the chosen type appears on the dashboard.
const typeSelect = document.getElementById("account_type");
if (typeSelect) {
  const groups = JSON.parse(typeSelect.dataset.groups || "{}");
  const target = document.getElementById("group_name");
  typeSelect.addEventListener("change", () => {
    if (target) target.textContent = groups[typeSelect.value] || "";
  });
}
