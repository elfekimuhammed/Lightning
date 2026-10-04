# Competition: our compass

Who else helps people with their money, what their users love and hate, and what that means for Lightning. When a product decision is unclear, read *The compass* first. Research of 2026-10-04 (Claude), from store listings, review sites and GitHub issues. **Evidence limits** at the end says what is solid and what is not.

## Contents

| Section | Read it when |
|---|---|
| The compass | You must choose between two designs or two priorities |
| The field in one table | You want to place Lightning against everyone else |
| What users love, in every app | You are designing a screen or a first-run step |
| What users hate | You want to know what never to build |
| Local competitors | You are working on capture, Arabic or bank SMS |
| International competitors | You are comparing a feature with the best apps |
| Where Lightning wins and loses | You write the website or plan the roadmap |
| Watch list | Every few months, or before a release |
| Evidence limits and sources | You doubt a claim here |

## The compass

1. **Capture beats analysis.** The most loved apps (Say, Money Manager, Copilot) win on how fast one spend is logged: a voice note, an autocomplete, a bank SMS. Lightning's analysis is stronger than all the local apps, but a ledger that is not filled in answers nothing. Phone capture and bank SMS (Project Overview › Compared with the best budgeting apps, #1 and #2) come before more reports.
2. **Free, private and offline is the Egyptian default.** The local apps run offline, with no account. A cloud login or a subscription needs a reason a user feels in the first week.
3. **Arabic and Egyptian money first.** Vodafone Cash, InstaPay, gold, certificates, CIB and NBE SMS. International apps do not know them; local apps know only the first few.
4. **Never be the busy one.** YNAB's most common complaint is a busy interface; Actual's is setup. Mohab's test stands: fewest clicks, one name for one thing.
5. **A wrong number is worse than a missing one.** Every bank-sync review complains of numbers that drift. Lightning shows what each figure includes (Architecture, financial rules).
6. **Price must stay obvious.** Users leave over price rises without added value (YNAB), per-person pricing (Copilot) and ads in paid versions (Money Manager). Say so on the website before we decide on a price.

## The field in one table

| App | Where | Price | Data lives | Capture | Bank link | Budget method | Wealth (investments, gold, loans) |
|---|---|---|---|---|---|---|---|
| **Say** (Egypt) | Android, iPhone | Free, Pro tier | Cloud, encrypted | Voice, bank SMS, calendar and email | SMS | Categories, insights | No |
| **Masroofy / Masrofi** (Arab world) | Android, iPhone | Free with ads, remove ads | On the phone | Manual, SMS import, receipt scan | SMS | Categories, budgets, zakat | Debts only |
| **Money Manager** (Realbyte) | Android, iPhone | Free with ads, EGP 99.99 once | On the phone | Manual, quick add | None | Category budgets | No |
| **Wallet** (BudgetBakers) | All | Free, Premium subscription | Cloud | Manual, bank sync (premium) | 15,000+ banks, not Egypt | Category budgets | Basic |
| **Telda, BM app** (banks) | Phone | Free with the account | The bank | Automatic, own cards only | Own bank only | Spending insights, category budget | No |
| **Actual Budget** | Web, desktop, self-host | Free, MIT | Your computer or server | Manual, import | SimpleFIN (US), GoCardless (EU) | Envelope, zero-based | No |
| **YNAB** | All | About 109 USD a year | Cloud | Manual, import, sync | US, Canada, EU | Zero-based | No |
| **Monarch** | Web, phone | 99.99 USD a year | Cloud | Sync | US, Canada | Flexible, forecast | Net worth, investments |
| **Copilot** | iPhone, Mac, web | 95 USD a year | Cloud | Sync | US | Category budgets | Net worth, investments |
| **Firefly III** | Self-host | Free | Your server | Manual, import | None | Budgets, rules | Accounts only |
| **Lunch Money** | Web | Subscription | Cloud | Import, sync | Some | Flexible | Basic |
| **Lightning** | Windows (phone planned) | Free so far | Your PC, encrypted profile | Manual, CSV, PDF statements | None yet | Rollover budgets, reserves, plans | Yes: gold, shares, funds, CDs, loans |

## What users love, in every app

Each point names the apps where people say it and what Lightning does.

| What they love | Said about | Lightning today |
|---|---|---|
| **Logging without effort:** voice, "track my 15 dollar lunch", SMS auto-logging. "Track expenses very easily without effort by the voice note feature" (Say, App Store) | Say, Copilot, MonAi | Missing. The biggest gap |
| **Knowing where the month goes:** "helps me track how much I spend each month, so I can save more and see what I need to fix" (Say, App Store) | Say, Telda, Wallet | Have it, deeper (Expense analysis) |
| **Simple, uncluttered:** "extremely simple", quick add and autocomplete (Money Manager) | Money Manager, Masrofi | Quick add is partial; menus are heavier |
| **Pay once, no ads, no subscription** (Money Manager "Remove Ads") | Money Manager, Masrofi | Free today. Decide before release |
| **No bank login, no cloud:** "data stays on your hardware, nobody else has access" (Actual) | Actual, Masroofy, Money Manager | Have it. Our strongest shared promise |
| **Open source and free,** "YNAB without the subscription" (Actual, Reddit) | Actual, Firefly III | Free yes, open source not decided |
| **A method that changes behaviour:** "transformed my finances", "saved so much money and paid off so much debt" (YNAB, Trustpilot) | YNAB, Actual | Rollover budgets and reserves; no "give every pound a job" yet |
| **Beautiful design:** "best-designed budgeting app on iOS", 4.8 stars (Copilot) | Copilot, Monarch, MonAi | The brand guideline is our answer. Keep it strict |
| **Arabic that works:** bilingual, mixed dialects, zakat, Arabic categories | Say, Masarifi, Masrofi | Check Arabic and right-to-left status before any Egypt launch |
| **Couples and household** | Monarch | Missing |
| **Net worth in one place** | Monarch, Copilot | Have it, plus gold and local assets |
| **Responsive maker, steady improvements** | Firefly III, Monarch | A website changelog and feedback loop help here |

## What users hate

| What they hate | Said about | Lesson for Lightning |
|---|---|---|
| **Bank sync that breaks** and has no support | Wallet (long-time users, late 2024), YNAB ("went all wonky"), Monarch, Actual | If we parse SMS or statements, a failed read must say so and never post a wrong figure |
| **Price rises without new value** | YNAB | Promise stable pricing |
| **Per-person pricing,** one platform only | Copilot (iPhone only, 190 USD for two) | Windows today is a limit; say it plainly and keep the phone plan visible |
| **Busy interface, hard to learn** | YNAB | Every screen answers one question |
| **No mobile app, or one that fails** | Actual: "can't open budget on mobile", sync errors for weeks | The phone is the capture tool; it must open every time |
| **Needs a server and technical skill** | Actual, Firefly III | Install is a ZIP and a double-click. Keep it |
| **Ads, even in the paid version** | Money Manager | None |
| **No bills, no "safe to spend"** | Money Manager | Upcoming bills and the forecast exist; keep them visible |
| **Carry-over that does not work** | Money Manager | Rollover is a core figure; Mohab's test covers it |
| **Budget missing on the web version** | Wallet | One set of pages everywhere |
| **Phone verification and SMS failures in Egyptian apps** | InstaPay | Do not depend on a one-time SMS to start |

## Local competitors

**Say – Hands free budget app (Roberto Joseph, Cairo).** The one to watch.
- Tap the mic and speak: it finds amount, date and category. Says it understands 99+ languages, including Arabic and mixed dialects.
- Reads bank SMS and logs the spend. Can also read calendar and email for event-based spends and invoices.
- Free plan: unlimited expenses, 3 custom categories, multi-currency, basic analytics. Pro: unlimited SMS and voice, full trends, multiple accounts, unlimited categories, custom billing cycles, CSV and PDF export. Price varies by region.
- 4.63 stars on Google Play (top finance apps in Egypt); 4.8 on the App Store from 49 ratings. Small, early, loved.
- Weak spots, as far as visible: no investments, gold, loans or net worth; a cloud service, so "private" is a claim not a design; reviews so far praise ease only. **We cannot beat it on speed of capture until Lightning has a phone app and SMS reading. We beat it on everything after capture.**

**Masroofy / Masrofi.** Arabic-first. Offline, no account, expenses, budgets, salary, debts and a zakat calculator. Newer versions import bank messages (it names 190+ banks and wallets in 22 countries) and scan receipts. Several unrelated apps share these names, so check which one a user means. Free with ads. Zakat is a feature Lightning has not weighed.

**Money Manager, Wallet, Masarifi, Masarif.** Wide-reach manual trackers. Money Manager (4.6 stars, about 470,000 reviews) is loved for being fast and simple. Wallet (4.5 stars on Play from 340,000 reviews) is loved for multi-currency and hated for bank sync.

**Bank apps (Telda, BM Online, CIB).** Free categorised insights and category budgets inside the bank. They see only their own accounts, so a person with two banks, a wallet and cash gets half a picture. That half-picture is Lightning's opening.

## International competitors

**Actual Budget.** Open source (MIT), local-first, envelope (zero-based) budgeting, YNAB-like. Data in a local SQLite file; optional self-hosted sync server.
- Loved: free, private, "go-to for people who enter bank transactions weekly and sort them", former YNAB 4 users find it familiar.
- Complained: no native mobile app (a mobile web view that struggles with big budgets); self-hosting needs skill; bank sync only through SimpleFIN (US, about 15 USD a year) and GoCardless (EU), so none for Egypt; reports are thin ("hard to see where the family budget stands"); GitHub carries long-open sync issues.
- Against Lightning: it is the closest in philosophy (local, private, free) and our nearest rival for the technical user. It has no Egyptian anything, no wealth side and no desktop installer for ordinary people. Where it wins: a mature envelope method and a large community. **Copy its promise (your data stays yours), not its setup.**

**YNAB.** The method everyone copies. Loved for changing behaviour. Hated for price (about 109 USD a year, "no value added"), a busy interface and bank connections that break. No investments, no bills. Lesson: one method taught well can build a loyal community; do not charge more without adding more.

**Monarch.** The Mint replacement. 99.99 USD a year, household sharing, net worth and investments, AI assistant. Loved for intuitive design and no ads; hated for glitchy sync and price. Lesson: net worth plus household is what people pay for. We have the first, not the second.

**Copilot.** The best-looking app. 95 USD a year, iPhone and Mac only, AI categorisation. Loved for design; hated for one platform and per-person pricing. Lesson: design alone earns a 4.8.

**Firefly III and Lunch Money.** Firefly III: self-hosted, rules and reports, manual only, no mobile app. Lunch Money: web, multi-currency, simple, praised support. Lesson: multi-currency and responsive support are loved by the people who find them.

## Where Lightning wins and loses

**Wins (say it on the website):**
- One ledger, plans that move no money, reports that read both. No other app keeps those three apart.
- Wealth the others lack: gold, shares, funds, certificates, loans, money held for others, real returns.
- Local, encrypted, no account, no server to run, Windows installer.
- Mohab's test: a full year through the screens, kept honest in the tests.
- Brand guideline: one calm, strict look.

**Loses (be honest, plan around it):**
- No phone capture, no SMS or voice: where Say wins every day.
- No automatic feed: every competitor with sync wins the first week.
- Windows only for now; most Egyptians budget on a phone.
- No household sharing, receipts, reminders or multi-currency.
- Arabic and right-to-left not confirmed.
- No community, reviews or ratings yet. Say has 49 on one store.

## Watch list

Check every few months and edit this file:
- **Say:** its Pro price, new features, rating and review count, and whether it adds investments or an Arabic UI.
- **Masroofy:** the bank-message import and how many Egyptian banks work.
- **Telda and bank apps:** whether any opens its data to other apps (open banking in Egypt would change our plan).
- **Actual Budget:** a mobile app, or any Arabic and Egyptian bank import.
- **Egyptian aggregators:** a provider that offers bank feeds would change the SMS plan.

## Evidence limits and sources

Store pages (Google Play, App Store), `sayapp.net`, Buxfer and several review sites were blocked in the research environment. The facts above come from search summaries of those pages, not from reading them whole, and **no individual Egyptian review text was read**. The quotes marked App Store, Trustpilot or Reddit are as the search result gave them. Before they go on the website or in marketing, open the source and confirm each quote and number. Next research step: read the Egyptian Play Store reviews of Say and Masroofy in Arabic, and Egyptian Facebook and Reddit threads, on a machine that can open them.

Sources: [Say on Google Play](https://play.google.com/store/apps/details?id=com.moments.expenses&hl=en), [Say on the App Store](https://apps.apple.com/us/app/say-hands-free-budget-app/id6746735689), [Say site](https://www.sayapp.net/), [Masrofi on the App Store](https://apps.apple.com/ca/app/masrofi-budget-expenses/id1467616866), [Masroofy on Google Play](https://play.google.com/store/apps/details?id=com.masroofi.masroofi&hl=en_CA), [Money Manager on Google Play](https://play.google.com/store/apps/details?id=com.realbyteapps.moneymanagerfree&hl=en_US), [BudgetBakers on Trustpilot](https://www.trustpilot.com/review/budgetbakers.com), [YNAB on Trustpilot](https://www.trustpilot.com/review/ynab.com), [Monarch review roundup](https://marriagekidsandmoney.com/monarch-money-review/), [Copilot review roundup](https://www.thepennyhoarder.com/budgeting/budgeting-copilot-money-review/), [Actual Budget review](https://wealthypot.com/budgeting-apps/actual-budget/), [Actual Budget mobile issue](https://github.com/actualbudget/actual/issues/6279), [Firefly III review](https://www.expensesorted.com/blog/147_firefly_iii), [Telda](https://telda.app/), [Banque Misr BM Online](https://www.banquemisr.com/en/Pages/BM-Online---Internet-and-Mobile-banking).
