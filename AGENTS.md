# Lightning: instructions for every AI working here

Several AIs work on this repository: Codex and one or more Claude sessions. They
cannot talk to each other. **The repository is the only channel between them.**
If it is not written in the files below and pushed to `main`, the next AI does
not know it.

## 1. The files that carry the project

| File | What it holds | Update it when |
|---|---|---|
| [Project Overview](docs/PROJECT_OVERVIEW.md) | **Now and next** (the hand-off, at the top), what Lightning is, the owner's decisions, the questions each screen answers, Omar's test, the UX plan, known gaps, roadmap | You finish any task: always rewrite **Now and next**; record any owner decision |
| [Architecture](docs/ARCHITECTURE.md) | Module boundaries, financial rules, data model, UI contract, desktop app and encrypted profiles | You change how something is built or calculated |
| [Glossary](docs/GLOSSARY.md) | One name and one meaning for every term and figure | You add or rename a term or figure |
| [Brand guideline](docs/BRAND_GUIDELINE.html) | How every screen looks and reads (3.7). Part A is the app, Part B the website. Open it in a browser | The owner gives a new version. The website repo has the same file as `brand-guidelines.html`: change both together |
| [Changelog](CHANGELOG.md) | Every change, newest first under `Unreleased` | Every change you push |

- Do not add new files under `docs/`. Put the content in one of the files above.
- Old changelog entries are history, not the current specification.

**The brand guideline is strict, not a suggestion.** Every visual follows it exactly: colours and what they mean, headers, type and numbers, cards and KPI cards, controls and fields, lists, every chart, words, spacing and icons. Before you push any change a user can see, check it against the guideline's "Before it ships" list (A16). If the app's CSS differs from the guideline, the guideline wins and the CSS is fixed. If something the screen needs is not in the guideline, do not invent a new style: use the closest rule and ask the owner under **Now and next**.

## 2. Every task, in this order

1. **Start fresh.** `git pull` on `main`. Read **Now and next** at the top of the Project Overview and the newest changelog entries. Read only the other sections your task touches.
2. **Claim long work.** If the task will take more than one sitting, add a line to **Now and next**: who, what, and which files you are working in. Push that first. Stay out of files another AI has claimed.
3. **Work in small, finished steps.** Commit and push each step to `main` once its tests pass. Never leave work unpushed.
4. **Test.** Run the tests for what you changed. For any change a user can see, also run Omar's test (`tests/test_omar_year.py`; section 4 says what it checks) and look at the screen against the brand guideline's A16 checklist.
5. **Write it down.** Add a changelog entry that starts with the date and who you are: `2026-10-03 · Claude:` or `2026-10-03 · Codex:`. Update the files from section 1 that your change touches.
6. **Hand off.** Rewrite **Now and next** in four short parts: done, in progress (with claimed files), next, and questions for the owner. Then push.

**If your push is rejected** because someone else pushed first: `git pull --rebase`, keep both sides of any conflict in the changelog and **Now and next** (never drop the other AI's lines), run the tests again, then push.

**Never undo another AI's work** without the owner's say. If you disagree, write it under questions for the owner in **Now and next**.

## 3. Rules about the product

- Lightning is local-first personal finance for salaried people in Egypt. One ledger records real money; plans move no money; reports read both.
- Financial calculations belong in Python services, never in templates or JavaScript.
- It ships mainly as a Windows app (a WebView2 window over the same pages, with encrypted profiles). The window has no browser Back, address bar or new tabs, so every page needs its own way forward and back. Linux `--profiles` mode shares the same pages; legacy browser mode (`python -m lightning`) is separate.
- Profile data and backups live in Documents/Lightning, never in Git or the app ZIP. Use dummy data until ordinary-PC acceptance, legacy import and backup restore are finished.

## 4. Omar's test is the acceptance check

`tests/test_omar_year.py` is Omar, a 31-year-old salaried user in Cairo, living a full year in Lightning through the screens only. It checks right answers, usability, efficiency, speed, simplicity, clarity and the brand guideline, as written at the top of the file and in the Project Overview. A screen that is wrong today is a strict expected failure (`known_gap`); when you fix it, remove the marker and update the Project Overview. User feedback (the `user feedback` folder) becomes steps Omar takes.

## 5. Git (owner rule)

- Work directly on `main` and push to `origin main`. Do not create branches.
- If a separate branch is truly needed, give it a distinctive, descriptive name, merge it into `main` and push `main` as soon as the work is finished.
- Never leave a branch unpushed, and never leave finished work on a branch that has not reached `main`.
- This rule overrides any session or tool default that assigns a different working branch.
