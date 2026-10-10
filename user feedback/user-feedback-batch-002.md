# Lightning User Feedback — Batch 002

- **Source:** Google Drive → `Lightning Data` → `App Feedback`
- **Feedback captured:** 26 September–9 October 2026
- **Polished on:** 10 October 2026
- **Coverage:** 42 app-feedback submissions; excludes survey responses and test/diagnostic rows
- **Builds represented:** 0.4.0-beta.1, 0.5.0-beta.1, and 1.0.0-beta.1-android
- **Privacy:** Submitter names, email addresses, session identifiers, and attachment links are omitted

## Executive summary

This batch focuses on clearer cash and investment planning, more useful Overview reporting, and smoother everyday workflows. Users asked for forecasts that explain when money is available, investment analysis that is accurate and easier to configure, and dashboards that show meaningful comparisons. They also reported navigation and responsiveness issues, confusing or clipped controls, and a few specific mobile and account-management needs.

The feedback below has been consolidated by topic. Requests and reported defects are presented as user feedback; they are not product decisions.

## Grouped feedback

### 1. Cash planning, reserves, and goals

Users want cash planning to reflect when money is expected to arrive or leave, and to make its assumptions easier to configure.

- Make cash forecasts date-aware, including mid-month income, upcoming bills, and the difference between funded costs and expected cash flows.
- Let users choose the relevant account, category, or counterparty when mapping planned items; show only the fields that apply to the selected choice.
- Fix the reserve selector so its options remain visible and usable while typing.
- Clarify which cash-planning fields are editable, and refresh available-cash cards immediately after a reserve is changed or saved.
- Let users define savings or emergency-fund targets and see progress and an estimate of when each target may be reached.
- Make budget and income-category controls clearer, including the action for adding or copying an income category.

### 2. Investment planning and analysis

Users want investment setup to be easier to understand and the resulting numbers to be dependable.

- Make target allocation easier to find and configure; validate allocations, explain when targets do not total 100%, and show where the settings are located.
- Correct the XIRR calculation so a full year of data is not required to show a valid result, and make its explanatory tooltip readable.
- Clarify investment holdings by reducing repeated account or asset details and improving the order of parent and child holdings.
- Explain performance measures such as “fall from highest” in plain language.
- Show the source and update timing for automatically retrieved prices and volumes, and make cached or stale data understandable.

### 3. Overview, charts, and reporting

Users want the Overview to show the current picture clearly and make changes over time easier to interpret.

- Improve the hierarchy and layout of KPI cards, remove duplicated free-cash information, and make card actions behave consistently.
- Add comparisons with the previous period or data point where they help explain a trend.
- Make it clear which figures are current snapshots and which respond to the selected date range.
- Improve cash-flow and expense views, including a request to show outflow volume more clearly in the heat map.
- Preserve positive feedback on the Sankey view while keeping its labels and categories understandable.
- Fix mobile date-range controls that appear clipped or misaligned, and make the top bar less visually dominant.

### 4. Navigation, responsiveness, and saved state

Users reported friction moving through the app and returning to their work.

- Reduce sluggish page navigation and improve responsiveness when submitting feedback with multiple screenshots.
- Keep users on their current page and in context after saving, instead of resetting the view.
- Make navigation from investment overview and other cards lead to a useful destination.
- Improve the placement and consistency of actions such as “Select all”.
- Pre-cache uploaded feedback images so multi-image submissions do not feel stalled.

### 5. Transaction and account workflows

Several requests concern making account and transaction operations more explicit.

- Support splitting a transfer or transaction fee into its own amount.
- Allow settlement through the relevant account types, including cash, mobile money, and savings accounts.
- Remove repeated identifiers from holding and account displays where they add clutter.
- Make short-, medium-, and long-term labels more readable, with clearer names and colors.

### 6. Interface clarity, accessibility, and setup

Users also identified focused changes that would make controls and guidance easier to use.

- Fix small, clipped, or low-visibility controls, including settings icons, help text, and aligned toggle arrows.
- Use more readable labels and simplify dense forms.
- Add a clear completion action to the setup guide.
- Let “needs review” items expire when they are no longer relevant.
- Remove arbitrary password-length limits while continuing to encourage strong passwords.
- Remove stale profile labels and make it possible to attach screenshots to feedback.

## Source breakdown

The submissions came from these areas in the source App Feedback tab:

- Cash planning: 8
- Investments: 9
- Overview: 10
- Something else: 10
- Expense analysis: 2
- Import CSV: 1
- Budget: 1
- Profile or settings: 1

## Review signal

The recurring review themes are cash forecast clarity, reliable investment calculations and data, useful Overview comparisons, and faster workflows that preserve user context. The individual requests range from reported defects to optional enhancements; prioritization should consider product scope and the underlying submission details in the source sheet.

## Traceability

This compilation covers 42 app-feedback submissions from the source tab, excluding test/diagnostic rows and the submissions already compiled in Batch 001. Similar requests have been combined into shared themes. No submitter identifiers or attachment links are reproduced here.
