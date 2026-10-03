# Lightning User Feedback — Batch 001

- **Source:** Google Drive → `Lightning-survey-responses` → `App Feedback`
- **Feedback captured:** 3 October 2026
- **Polished on:** 3 October 2026
- **Processed by:** GPT-5 (Codex)
- **Landing release:** UX-2026.10.02.07
- **App build:** 0.4.0-beta.1
- **Device:** Desktop
- **Coverage:** 27 submitted rows, now referenced in the sheet by unique Ticket # values 1–27
- **Sender:** El Feki for all 27 rows; sender email was not captured in the source submissions

## Executive summary

The feedback is concentrated in five themes: responsiveness and state preservation, CSV import reliability and review ergonomics, clearer financial and investment modelling, more dependable Overview/report behaviour, and a small set of visual/readability fixes. The strongest workflow risk is CSV import: users reported slow transitions, failed large uploads, incomplete recovery when leaving an import, missing navigation after errors, and unclear editing controls. The strongest product-model request is to distinguish investment capital movements from income and expenses while making recurring, one-off, reserve, and goal behaviour explicit.

## Grouped feedback

### 1. Performance, loading, and state preservation

- **Source tickets:** 1, 8, 13, 14, 16
- **Theme:** The app feels slow or appears stuck during navigation and saves, particularly around CSV import. Users want visible progress, immediate processing, and continuity of their place and work.
- **Polished feedback:**
  - Reduce the 4–5 second delay when opening tabs by caching calculations or other stable information where safe.
  - Start processing a CSV immediately after upload and cache the prepared result so the Import CSV page does not take several seconds to open.
  - Show a clear loading state whenever work is in progress, so the app does not appear frozen.
  - If a user leaves an unfinished import, preserve it as a pending import with its edits. Prevent a second import from starting until the pending import is completed or cancelled.
  - After saving or updating, preserve the user’s current page, scroll position, and relevant context instead of refreshing them back to the start.

### 2. CSV import and review workflow

- **Source tickets:** 6, 7, 9, 10, 11, 12, 14, 15
- **Theme:** Import and review need a more compact, resilient, and self-explanatory workflow.
- **Polished feedback:**
  - Style the file chooser so it matches the rest of the application.
  - Make review rows look like normal ledger entries rather than oversized rows with too many buttons.
  - Treat fields such as “Uncategorised” as selectable controls with clear empty/default states; users should not have to delete placeholder text before choosing a value.
  - Display the full category hierarchy, including its L1 heading, rather than only an abbreviated `L1 → L2` representation.
  - Make THNDR available as an internal-transfer destination or source when appropriate.
  - Remove the current upload-size/field-count failure for larger files, including a 300-row CSV with seven fields, which currently can result in “form expired”.
  - When review contains errors, provide an explicit route to continue or return to the relevant step; do not leave the user without a usable navigation action.
  - Support multiple CSV uploads in one workflow, if the resulting review and duplicate handling remain clear.

### 3. Financial model, categories, reserves, and planning

- **Source tickets:** 2, 23
- **Theme:** Users want clearer separation between capital movements, income/expense analysis, recurring activity, one-off activity, reserves, and goals.
- **Polished feedback:**
  - Add a dedicated investment capital-allocation account or equivalent mechanism for injecting and withdrawing investment money without classifying those movements as income or expenses.
  - Clarify category behaviour with explicit metadata for whether a category represents inflows, outflows, or both.
  - Let categories be marked as recurring or one-off so recurring items can participate in forecasting while one-off items remain separate.
  - Consider renaming “reserves” to “upcoming projects” if that better communicates their purpose, and support expected one-off income within the same planning flow.
  - Allow users to set a recurring investment goal, such as a monthly contribution target, and retain that goal in planning.
  - If an emergency-fund target exceeds current cash, show a clear warning and explain that additional income must be retained to reach the target.

### 4. Investment data and analysis

- **Source tickets:** 17, 18
- **Theme:** Investment tracking should support assets whose value is recorded directly and should include all configured investment types in analysis.
- **Polished feedback:**
  - For fixed-income funds and other appreciating assets, support either unit/price input or direct current-value input, then calculate the return from the available basis and current value.
  - Apply the same direct-current-value option to assets such as gold, buildings, and apartments; the app should not force a price-unit model when the user only knows the total current value.
  - Ensure “Other investments” appear in the investment analysis wherever they are included in the portfolio.

### 5. Overview, reporting, and time-horizon semantics

- **Source tickets:** 19, 21, 22, 24, 25, 26
- **Theme:** Report outputs need consistent time-horizon rules, complete values, and clearer chart aggregation.
- **Polished feedback:**
  - Fix the Saving and investing rate so it displays a meaningful result for the All time horizon, or show a clear unavailable reason when the data is insufficient.
  - Show net cash flow by month by default rather than by day when the Overview is used for broader periods.
  - State which visuals are fixed snapshots and which respond to the selected time horizon.
  - Keep the “Where do I stand?” section as a snapshot of today rather than changing it to represent only the selected historical period.
  - Limit the Sankey diagram to a manageable number of categories and aggregate the remainder into “Other”. Use blue for investing instead of rose to make the semantic distinction clearer.
  - Make the heat map granular by day for a single month, and use monthly columns for multi-month views; the multi-month view should cover at least six months when that is the intended comparison.

### 6. Visual clarity and feedback messages

- **Source tickets:** 3, 4, 26, 27
- **Theme:** Several controls and messages are difficult to read or consume too much space.
- **Polished feedback:**
  - Change the status-message text to a readable foreground/background combination; black text on the current deep green background has insufficient contrast.
  - Present status updates as temporary notifications, ideally disappearing after about five seconds, rather than leaving them permanently on the page.
  - Remove the explanatory “+ is income / − is expense” line from the top of Profile or Settings if the surrounding controls already make the meaning clear.
  - Fix account-register layout so the balance has enough room and is not clipped.

### 7. Bulk editing

- **Source ticket:** 20
- **Theme:** Selection is useful, but users also want a safe bulk-edit path.
- **Polished feedback:**
  - When multiple rows are selected and a field is changed, offer a confirmation asking whether the change should apply only to the edited row or to all selected rows.

## Prioritisation signal

1. **High:** CSV import reliability, pending-import recovery, large-file handling, and error navigation.
2. **High:** Loading/progress feedback and preserving user context after saves or updates.
3. **High:** Correct Overview/report values for All time, current snapshot semantics, and complete investment analysis.
4. **Medium:** Clearer investment capital flows, recurring/one-off category rules, and goal/reserve planning.
5. **Medium:** Review-row density, category hierarchy labels, bulk editing, and visual polish.

## Traceability

Every row in the source `App Feedback` tab was included once in this compilation. The final row had a repeated source ticket number, so the sheet now assigns it the unique reference Ticket #27. All current rows are attributed to El Feki; the optional sender email was not present in the captured data.
