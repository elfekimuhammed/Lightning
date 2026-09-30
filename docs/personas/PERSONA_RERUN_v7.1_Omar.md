# Omar re-run · v7.1 · "tap everything, read nothing"

**Version v7.1** · code: `claude/cash-planning` · data: Omar's household from the v7 run, as of 2026-09-30, replayed on **2026-10-06** (salary, rent and the first car-loan payment are due) · driven in Chromium at desktop and phone width.

**Lens:** the user is lazy and in a hurry. They tap the obvious button, type the way their phone keyboard types, don't read help text, and want one clear number. A point is a finding if that user would get a wrong result, see nothing happen, or have to stop and think.

## 1. Scenario

| # | What Omar does | What happened before the fixes | Now |
|---|---|---|---|
| P1 | Opens the Overview on 10-06 | *Needs my attention*: Bill due · Landlord, Loan payment due · Car loan | Same |
| P2 | Looks for the loan in the Budget | The 2,500 line was planned but **hidden inside the collapsed Personal group** | The summary says "Includes 2,500.00 of loan payments scheduled this month" (#127) |
| P3 | Pays rent from the Overview, typing 12,500 (rent went up) | Paid; the bill stays 12,000 for next month, and nothing mentions the difference | Open (#133) |
| P4 | Car loan: presses **Skip this one** | **Loans still to pay dropped 2,500, as if the bank forgave it.** The skipped payment could not be found again to undo | "Move to the end of the loan": still owed, the loan ends one month later, and a "Skipped · undo" row appears (#120) |
| P5 | Edits the loan: 24 → 20 payments | Worked, but the edit form said **"Payments left 24"** after payments were made, and "Due date · the next one" showed the first date | Edit form says **First due date** and **Number of payments** (#126) |
| P6 | Adds a gym bill, typing **٦٠٠** and **5/10** on a phone keyboard | **Amount erased as it was typed:** the field kept only 0–9 | ٦٠٠ becomes 600, and Arabic digits work in dates (#121) |
| P7 | Taps **Track** on "Mom" (a monthly gift) | Opens as a *Bill* | Open (#131) |
| P8 | Presses **Delete** on Electricity (it has a paid payment) | The confirm said **"Delete this transaction? You can restore it…"**; it was then quietly *stopped*, not deleted | The button says **Stop** with "Stop Electricity? No new payments will be scheduled; its paid history stays." (#124) |
| P9 | Pay popup on a 390 px phone | Fits the screen, no side scroll | Same |
| P10 | Opens next month's budget to plan ahead | **Internal Server Error (500)** | Back to this month with "2026-11 has not started yet. This month's amounts carry on into it until you change them." (#122) |
| P11 | Reads the Plan tab | "What you owe · **Loans** 48,100.00": the link text read as the label of the total (loans were 47,500) | The link reads **See your loans** (#125) |
| — | After any popup action (Mark paid, Skip, Stop, Undo) | **No confirmation at all:** the popup closed and the page reloaded silently | A message appears under the page title, e.g. "Car loan · 2026-10-05 is back on the schedule." (#123) |
| P12 | Checks | 8 passed | 8 passed |

No JavaScript errors. The only server error (#122) is fixed.

## 2. Findings

Numbering continues from v7 (#112–119).

### Fixed in this run

| # | Severity | Finding | Fix |
|---|---|---|---|
| **120** | High · wrong numbers | Skipping a loan payment removed it from **Loans still to pay** and **Net worth**, as if the debt were forgiven. Skipped payments were then invisible, so it couldn't be undone. | For a loan, a skip moves the payment to the end (the schedule gets one more payment). The button reads "Move to the end of the loan". Skipped payments from the last two months show as "Skipped · undo" on Loans and Recurring. |
| **121** | High · silent data loss | Amount fields erased Arabic-Indic digits (٠–٩, ۰–۹) as they were typed, and dates rejected them. | Converted to 0–9 in the browser and on the server, including ٫ (decimal mark) and ٬ (thousands). |
| **122** | High · crash | `/budget?month=<next month>` returned a 500. | Redirects to this month with an explanation. |
| **123** | Medium · no feedback | Popup actions showed no confirmation unless the page already had a message box. | The message box is created when missing. |
| **124** | Medium · wrong words | Deleting a plan item asked "Delete this transaction?". An item with history was stopped under a button labelled Delete. | The button says **Stop** or **Delete** to match what happens, with its own confirmation text. |
| **125** | Medium · misleading layout | "Loans" link text sat right before What you owe's total (48,100). | "See your loans". |
| **126** | Medium · wrong label | Editing a loan showed "Payments left" and "the next one" for stored values that are the total count and the first date. | Edit mode: **First due date**, **Number of payments**, with a hint. |
| **127** | Low | The loan's budget line was only visible after opening its group. | Shown in the Budget summary. |
| **128** | Low | Switching Type to Income inside the popup kept the "paid from / who you pay" hints. | Hints now fit both: "where the money goes out or comes in", "who you pay, or who pays you". |

Regression tests were added for #120, #121, #122 and #124. The full suite shows only the 9 failures that were already there before this work.

### Open: confusing for a hurried user

| # | Finding | Suggestion |
|---|---|---|
| **129** | **Too much reading on the Plan tab: about 400 words.** Every figure carries its meaning, its formula and a note ("Bills due (0.00 EGP, loan payments included) come off free cash now…"). The unified formulas are right, but a lazy user sees a wall of text. | Show one number and one short line per card. Move the meaning and formula behind a small "How is this worked out?" toggle, the same on every tab. The Overview's position section (136 words) is about the limit. |
| **130** | A bill added with a date a few days ago (typed 5/10 on 10-06) is **instantly "due"** and cuts free cash by 600, though the user probably paid it already. | When the first date is in the past, ask once: "Already paid this one?" (link it or record it), else start from the next date. |
| **131** | Recurring suggestions include a gift to Mom (as a Bill), NBE certificate interest and a 15 EGP bank fee. Tracking the wrong ones is one tap away. | Suggest the kind from the category (interest → Income; gifts → leave out). Hide suggestions under 50 EGP. |
| **132** | "Discard your unsaved changes?" popped up 3 times in one run (after an error, or when opening another popup). | Only ask when a field actually changed since the form opened. |
| **133** | Paying rent at 12,500 against a 12,000 bill says nothing, and next month is still planned at 12,000. | Offer "Rent went up? Update the bill to 12,500" after recording a different amount. |
| 117 | Late salary not flagged. | Left out by your choice. |
| 111 | Investment Result "Unavailable" before the first price. | Carried over. |
| — | Import review opens all 40 rows (104 interactions); a fee needs the "Fees are extra" tick; a fund can't be bought by amount; 5 extra confirmations for new names. | Carried over. |

## 3. Why this matters for this user
- **Wrong or silent beats hard.** A hurried user won't notice that a skip forgave 2,500, or that ٦٠٠ vanished. #120 and #121 were the most dangerous findings; both are fixed.
- **One name per thing held up.** Omar never met two names for one number in this run. The remaining friction is *amount* of text (#129), not *conflicting* text.
- **Every tap needs visible feedback.** Before #123, every popup action looked the same whether it worked or not.
