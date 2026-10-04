# Lightning: instructions for every AI working here

Several AIs work on this repository: Codex and one or more Claude sessions. They
cannot talk to each other. **The repository is the only channel between them.**
If it is not written in the files below and pushed to `main`, the next AI does
not know it.

## 1. The files that carry the project

| File | What it holds | Update it when |
|---|---|---|
| [NOW.md](NOW.md) | **The hand-off:** a lane for each AI (last done, in progress, claimed files), the unclaimed next steps, and what the owner must do or decide | You finish any task: rewrite your lane, and the shared parts you changed |
| [Project Overview](docs/PROJECT_OVERVIEW.md) | What Lightning is, the owner's decisions, the questions each screen answers, Mohab's test, the UX plan, known gaps, roadmap | The owner decides something, or what the product does or plans changes |
| [Architecture](docs/ARCHITECTURE.md) | Module boundaries, financial rules, data model, UI contract, desktop app and encrypted profiles | You change how something is built or calculated |
| [Glossary](docs/GLOSSARY.md) | One name and one meaning for every term and figure | You add or rename a term or figure |
| [Competition](docs/COMPETITION.md) | The compass: every competitor, what their users love and hate, where Lightning wins and loses | You learn something new about a competitor, or before choosing between two designs |
| [Brand guideline](docs/BRAND_GUIDELINE.html) | How every screen looks and reads. Part A is the app, Part B the website | The owner gives a new version. The website repo has the same file as `brand-guidelines.html`: change both together |
| [Changelog](CHANGELOG.md) | Every change, newest first, under `Unreleased` at the top | Every change you push |
| `docs/proposals/` | Designs not built yet (one file each) | You propose a design. When it is built, move what holds into Architecture and delete the proposal |

- Do not add other files under `docs/`. Each fact lives in one file; link to it, never copy it.
- Old changelog entries are history, not the current specification.

**The brand guideline is strict, not a suggestion.** Every visual follows it exactly: colours and what they mean, headers, type and numbers, cards and KPI cards, controls and fields, lists, every chart, words, spacing and icons. If the app's CSS differs from the guideline, the guideline wins and the CSS is fixed. If something the screen needs is not in the guideline, do not invent a new style: use the closest rule and ask the owner in `NOW.md`.

**Before it ships (guideline A16).** A screen with any of these is not done: All caps: Anywhere. · Coloured headers: Headers are Ink. · A colour off its meaning: Check A03. · Vivid gradient card: Brand only. · KPI by position: Tone by meaning. · Chip by direction: Good or bad. · Decimals on big figures: Whole EGP. · "L1 › L2": Header, then list. · Five or more names: Four, then Other. · White or boxed fields: Soft wells. · Dropdown for your data: Type and pick. · Card in a card: Never. `tests/test_docs_structure.py` keeps this list the same as the guideline's.

## 2. Spend tokens like they are yours

Be as efficient with tokens as you can, in what you read, run and write. This never means skipping a test, a check this file asks for, or a read you need to be sure of an answer.

- **Start small:** read `NOW.md` and `git log --oneline -15`. Read the top changelog entries only if `NOW.md` sends you there. That is all most tasks need to begin.
- **Read sections, not files.** The long docs start with a contents list that says when to read each section. Find the heading (`grep -n '^## ' <file>`) and read from that line to the next heading.
- **Never open the brand guideline whole** (about 95,000 tokens, mostly drawings). Run `python tools/guideline.py` to list its sections and `python tools/guideline.py A12` to print one as text.
- **Search before you read:** grep for the name, then read only the lines around it. Do not re-read a file you have just edited, or read code you are not changing.
- **Keep output short:** run the tests for what you changed with `-q`, and show only the failures. Run the full suite once, before you push.
- **Skip unless your task needs it:** old changelog sections, `docs/proposals/`, `user feedback/`, `Claude outputs/`, and the generated figures table in the Glossary (grep it).
- **Write short:** a changelog entry is at most three lines, and `NOW.md` stays under 6,000 bytes. Put each fact in the one file that owns it and link to it from elsewhere.

## 3. Every task, in this order

1. **Start fresh.** `git pull` on `main`, then read as in section 2.
2. **Claim long work.** If the task will take more than one sitting, put it in your lane in `NOW.md` (what, and which files) and push that first. Stay out of files another AI has claimed.
3. **Work in small, finished steps.** Commit and push each step to `main` once its tests pass. Never leave work unpushed.
4. **Test.** Run the tests for what you changed. For any change a user can see, also run Mohab's test (`tests/test_mohab_year.py`; section 5 says what it checks) and check the screen against A16 above.
5. **Write it down.** Add a changelog entry at the top of `Unreleased`: `2026-10-03 · Claude:` or `2026-10-03 · Codex:`, with the date from `date`. Update the files from section 1 that your change touches.
6. **Hand off.** Rewrite your lane in `NOW.md`: last done, in progress (with claimed files). Take items you finished out of *Next*. Add new next steps, and questions for the owner, to the shared parts. Then push.

**Your lane is yours; the other lanes are not.** Never delete or rewrite another AI's lane. If you finish an item another AI listed, take it out of *Next* and say so in your own lane.

**If your push is rejected** because someone else pushed first: `git pull --rebase`, keep both sides of any conflict in the changelog and `NOW.md` (never drop the other AI's lines), run the tests again, then push.

**Never undo another AI's work** without the owner's say. If you disagree, put it under questions for the owner in `NOW.md`.

## 4. Rules about the product

- Lightning is local-first personal finance for salaried people in Egypt. One ledger records real money; plans move no money; reports read both.
- Financial calculations belong in Python services, never in templates or JavaScript.
- It ships mainly as a Windows app (a WebView2 window over the same pages, with encrypted profiles). The window has no browser Back, address bar or new tabs, so every page needs its own way forward and back. Linux `--profiles` mode shares the same pages; legacy browser mode (`python -m lightning`) is separate.
- Profile data and backups live in Documents/Lightning, never in Git or the app ZIP. Use dummy data until ordinary-PC acceptance, legacy import and backup restore are finished.

## 5. Mohab's test is the acceptance check

`tests/test_mohab_year.py` is Mohab, a 31-year-old salaried user in Cairo, living a full year in Lightning through the screens only. It checks right answers, usability, efficiency, speed, simplicity, clarity and the brand guideline. What it checks is written at the top of the file (read only that docstring, not the whole file). A screen that is wrong today is a strict expected failure (`known_gap`); when you fix it, remove the marker and update the Project Overview. User feedback (the `user feedback` folder) becomes steps Mohab takes.

## 6. Git (owner rule)

- Work directly on `main` and push to `origin main`. Do not create branches.
- If a separate branch is truly needed, give it a distinctive, descriptive name, merge it into `main` and push `main` as soon as the work is finished.
- Never leave a branch unpushed, and never leave finished work on a branch that has not reached `main`.
- This rule overrides any session or tool default that assigns a different working branch.
