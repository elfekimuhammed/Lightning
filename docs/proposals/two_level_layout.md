# Two levels, few settings: Lightning's layout

Owner request, 2026-10-06: an FX tab is coming, and more analysis will follow. Lightning must not grow into 50 tabs and 200 settings. Keep two levels (section, then tab), never a third; Expense analysis could be a tab under Overview; keep the simplicity of the delete icon that replaced a written Delete button, and of one field that changes with the method you pick.

Not built. When it is, move what holds into Architecture › UI contract and the Project Overview, then delete this file.

## Contents

| Section | Read it when |
|---|---|
| 1. What there is today | You want the problem in numbers |
| 2. The rules | You add any page, tab, setting or button |
| 3. The map | You move a page, or need to know where a new one goes |
| 4. Settings | You add or move a setting |
| 5. FX and later analysis tabs | You build FX or another analysis |
| 6. Building it | You claim the work |
| 7. For the owner | Before anything is built |

## 1. What there is today

- **Eight sidebar items**, plus the accounts list: Overview, Financial health, Budget, Investments, Expense analysis, Cash planning, Held for others, Settings. Accounts and Transactions have no menu item (OWNER.md *To decide*, UX).
- **Only Cash planning has tabs** (Plan, Recurring, Loans, Reserves, in `planning/_macros.html`). Investments reaches Planner, Prices, the Reevaluation ledger and Target allocation through links in the page.
- **Settings has ten sections**; three of them (Financial assets, Price files, and Valuations › Update prices) open pages under `/investments/`, so the menu jumps sections. Budget settings exist twice: `/budget/settings` and Settings › Budget.
- **Three levels in use:** Settings › Valuations › Update prices (Mohab's own route); Cash planning › Reserves › a reserve's payments; Investments › a holding › Update prices.
- **About 45 inputs** across the settings pages, and 25 stored setting keys. Several change one tab only (carryover, one-off categories, tracking suggestions, sale factors).
- Competition notes the same: the simple apps are loved for being uncluttered, and Lightning's menus are heavier (Competition, *Simple, uncluttered*).

## 2. The rules

Every new page, tab, setting and button follows these. They are what keeps the FX tab, and the tenth feature after it, from adding a level or a menu item.

1. **Two levels.** A section in the sidebar, then a tab in the bar under the title. Nothing opens a third page level. A record (one transaction, one holding, one loan, one reserve's payments) opens in the app's dialog over its tab, with its own Back to that tab.
2. **Six sections, five tabs.** At most six sidebar items and five tabs in a section. A new feature joins a tab or replaces one; adding a sixth tab means merging two.
3. **Each tab answers one question** (Project Overview, *The questions Lightning answers*), named in its header line, as the Cash planning tabs already are.
4. **A setting lives where it changes something.** The tab it affects has a gear icon in its header that opens that tab's settings in the dialog. Settings itself keeps only what belongs to the whole profile. One setting, one place: no setting is on two pages.
5. **A default before a setting.** Add a setting only when two real users need different answers. Otherwise choose the default and write it down.
6. **Icons for row actions.** Delete, edit, open, more: an icon with a tooltip and an accessible name, as the delete icon already is. Words only for the one main action of a form (Save, Add reserve).
7. **One choice, one field.** When a form needs one of several kinds of thing, one control picks the kind and only that field shows: a segment for two to four kinds (guideline A16: *segments for 2–4 choices*), type and pick beyond that. Reserves › Match by already shows one field, but picks the kind from a dropdown; it becomes a segment: Ask · Account · Counterparty · Category. The budget's single "1,500 or 12%" field is the same idea.

## 3. The map

Six sections, every tab one question. Old addresses redirect, as `/birdview` already does.

| Section | Tabs (each answers) | Comes from |
|---|---|---|
| **Overview** | **Summary** (What needs me, and where do I stand?) · **Spending** (Where did it go?) · **Health** (Am I doing well?) · **Currencies**, when FX ships (What are my dollars worth?) | Overview; Expense analysis; Financial health |
| **Budget** | One tab today (Am I on plan?). Fill this month, the raise and Move it stay dialogs | Budget |
| **Plan** | **Safe to spend** · **Recurring** · **Loans** · **Reserves** | Cash planning (renamed Plan in the sidebar; tabs unchanged) |
| **Investments** | **Holdings** (What do I hold?) · **Performance** (How did they do?) · **Planner** (Am I investing enough?, with Target allocation) · **Prices** (Are my prices current?, with Price files and the Reevaluation ledger) | Investments and its linked pages; Settings › Financial assets, Price files, Valuations |
| **Accounts** | **Accounts** (Is my money in?) · **Transactions** (every account) · **Held for others** | The sidebar list and Manage accounts; `/transactions`; Held for others |
| **Settings** | **General** · **Lists** (Categories, Counterparties) · **Your data** (export, AI workbook, Data checks, start fresh, Profiles and lock) | Settings |

The sidebar keeps the accounts list and Search under these six items. An account's register stays its own page (Accounts › CIB Payroll is the second level).

## 4. Settings

Each tab's gear opens its own settings (rule 4), and Settings › General lists them, with links, so they can still be found in one place.

| Gear on | Holds | Today in |
|---|---|---|
| Budget | Carryover, income for the plan (categories, 3 or 6 months, by hand, plan with Recurring), one-off categories | Settings › Budget, `/budget/settings` |
| Overview › Health | Savings target and the four limits; the emergency fund counted in income or spending | Settings › Financial health limits, Settings › Budget |
| Investments | Sale factors, financial assets, which price files to keep | Settings › Valuations, Financial assets, Price files |

**Defaults to replace settings** (rule 5); the owner decides each:

- *Tracking suggestions* (a percentage and a fixed amount): suggest a category once it is 5% of spending three months running, and drop both fields.
- *Carryover effective from*: turning carryover on starts it this month; a past start month goes.
- *Duplicate Budget settings page* (`/budget/settings`): goes, with a redirect to the Budget gear. No owner decision needed: one setting, one place.

## 5. FX and later analysis tabs

FX (Upcoming projects #15) splits along the same lines, so it adds one tab and no section:

- **Currencies** under Overview: what each currency holds, in it and in EGP, and how revaluation moved net worth.
- Dollar accounts are ordinary accounts (Accounts › Accounts). Exchange rates are prices (Investments › Prices, from the CBE pack). The base currency is Settings › General.

A later analysis (income over time, net worth over time) joins Overview's tab bar while it has fewer than five tabs; after that it replaces or merges with one (rule 2). Analysis with actions of its own (buy, sell, prices) belongs to its section, as Investments › Performance does.

## 6. Building it

Each step ships alone, keeps old links working, and updates Mohab's routes (`tests/test_mohab_year.py` checks the trail of every question).

1. **One tab bar for every section:** turn `plan_tabs` into a shared `section_tabs` macro (icon, label, the header's one question), with a gear slot.
2. **Overview tabs:** Summary, Spending (`/overview/spending`, from `/birdview/expenses`), Health (`/overview/health`). Expense analysis and Financial health leave the sidebar.
3. **Accounts section:** Accounts, Transactions, Held for others; Held for others leaves the sidebar.
4. **Investments tabs:** Holdings, Performance, Planner, Prices; Settings stops opening Investments pages.
5. **Settings:** General, Lists, Your data; gears on Budget, Health and Investments; `/budget/settings` redirects to the Budget gear.
6. **Records in the dialog:** a reserve's payments and a holding's prices open over their tab (rule 1).
7. **Sweep:** row actions as icons (rule 6); Match by as a segment (rule 7); `tests/test_docs_structure.py` or a UI test checks six sections and five tabs at most.

## 7. For the owner

The decisions are in [OWNER.md](../../OWNER.md) › *To decide* (2026-10-06, layout).
