# Lightning

Personal finance in one place: accounts, money in and out, transfers, budgets,
investments, cash reserves, and owned wealth. Historical wealth analysis and a dated cash outlook are planned.

## Start it

**Windows:** double-click `run.bat`. The first run sets everything up (needs Python 3.11+ from
python.org, with "Add python.exe to PATH" ticked). Your browser opens at `http://127.0.0.1:8765`.

**Linux:** launch **Lightning** from the app menu. It starts the local server and keeps a small terminal open; open `http://127.0.0.1:8765` in Firefox and bookmark it. Launching the icon again while Lightning is running reuses the server and opens no new tab. Close the terminal or press Ctrl+C to stop Lightning.

**macOS:** from the project folder, run `./run.sh`.

Options: `python -m lightning --db path\to\file.db --port 9000 --no-browser`

**Try it with sample data:** `python -m lightning --demo` opens Omar's household (three months of
money in and out, investments, gold, a budget, bills, an emergency fund and a car loan, dated up to
today) at `http://127.0.0.1:8766`. It lives in its own `data/demo.db`, rebuilt on every start, so
your own database is never touched. An empty Lightning also offers it on the welcome page.

## Run it on another computer (GitHub)

The code lives on GitHub; **your data never does** (`data/` is excluded by `.gitignore`).

```powershell
# on the new computer (needs Git and Python 3.11+)
git clone https://github.com/<your-username>/lightning.git C:\Code\Lightning
cd C:\Code\Lightning
.\run.bat
```

Get the latest version later with `git pull`. After changing the code on one computer:
`git add .` → `git commit -m "what changed"` → `git push`, then `git pull` on the other.

Each computer keeps its own `data\lightning.db`. To use the same data on both, keep the file in a synced
folder and start with `.\run.bat --db "C:\Users\<you>\OneDrive\Lightning\lightning.db"` — and only run
the app on one computer at a time.

## Your data

- Everything lives in one file: `data/lightning.db`. Copy it to back it up.
- A backup is made automatically every time the app starts (`data/backups/`, newest 30 kept).
- The app only listens on your own computer (`127.0.0.1`), never on the network.
- Open the file with any SQLite browser: the `v_ledger` and `v_balances` views are readable as-is.

## Using it

1. **Add your accounts** with today's balances.
2. Open an account and type transactions straight into its register (Counterparty · Category · Amount).
3. To import a statement, open the relevant **account** and choose **Import CSV**. Use `Date`, `Counterparty`,
   and signed `Amount` columns (negative = spending); `Category`, `Notes`, and `Reference` are optional. Review
   the preview to map aliases and categories before confirming—the app does not post until you confirm.
4. **Overview** shows today's position and recent activity. **Birdview** explains cash, investments, reserves,
   income, and spending. **Budget** shows the monthly spending plan and its remaining limit.

Global search finds accounts, investments, categories, and counterparties. Search transactions from the account register (or the all-accounts register) using its filters and search field.

## For developers

```
pip install -r requirements-dev.txt
python -m pytest          # 100+ tests incl. randomized net-worth reconciliation
lint-imports              # architecture contracts
```

- [docs/PROJECT_OVERVIEW.md](docs/PROJECT_OVERVIEW.md) — start here: the full hand-off brief
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — structure, rules, data model
- [docs/GLOSSARY.md](docs/GLOSSARY.md) — what every term and code means
- [docs/UI_AUDIT.md](docs/UI_AUDIT.md) — the tab-by-tab UI audit and what the demo pass changed
- [CHANGELOG.md](CHANGELOG.md) — every change, every time
