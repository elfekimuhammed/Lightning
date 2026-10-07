# Competition: our compass

Who else helps people with their money, what their users love and hate, and what that means for Lightning. When a product decision is unclear, read *The compass* first. Research of 2026-10-04 (Claude). Google Play reviews were read directly (Egypt store, English and Arabic); the rest comes from review sites. **Evidence limits** at the end says what is solid and what is not.

## Contents

| Section | Read it when |
|---|---|
| The compass | You must choose between two designs or two priorities |
| The field in one table | You want to place Lightning against everyone else |
| What users love, in every app | You are designing a screen or a first-run step |
| What users hate | You want to know what never to build |
| Local competitors | You are working on capture, Arabic or bank SMS |
| International competitors | You are comparing a feature with the best apps |
| Phone flow, words and icons | You design a phone screen, or choose between an icon and a word |
| Where Lightning wins and loses | You write the website or plan the roadmap |
| Watch list | Every few months, or before a release |
| Open source | You want source code to inspect before designing a finance feature |
| Actual Budget code analysis | You plan a feature Actual already has, or want to know what to borrow and what to leave |
| Evidence limits and sources | You doubt a claim here |

## The compass

1. **Capture beats analysis.** The most loved apps (Say, Money Manager, Copilot) win on how fast one spend is logged: a voice note, an autocomplete, a bank SMS. Lightning's analysis is stronger than all the local apps, but a ledger that is not filled in answers nothing. Phone capture and bank SMS (Project Overview › Compared with the best budgeting apps, #1 and #2) come before more reports.
2. **Free, private and offline is the Egyptian default.** The local apps run offline, with no account. A cloud login or a subscription needs a reason a user feels in the first week.
3. **Arabic and Egyptian money first.** Vodafone Cash, InstaPay, gold, certificates, CIB and NBE SMS. International apps do not know them; local apps know only the first few.
4. **Never be the busy one.** YNAB's most common complaint is a busy interface; Actual's is setup. Mohab's test stands: fewest clicks, one name for one thing.
5. **A wrong number is worse than a missing one.** Every bank-sync review complains of numbers that drift. Lightning shows what each figure includes (Architecture, financial rules).
6. **Price must stay obvious, and a free trial must not ask for a card.** The owner's decision (2026-10-04): 7 days free, then a reminder, never a lock. Say's biggest complaint, in English and Arabic, is being asked to subscribe before trying it. Users also leave over price rises (YNAB), per-person pricing (Copilot) and ads in paid versions (Money Manager). Say the price on the website before we decide it.
7. **Egyptian life is more than spending.** The fast-rising local app, Qershnat, adds the gam'eya (rotating savings circle), zakat, family assets and reminders, and users ask for more of the same. Lightning's wealth side is the right ground; gam'eya and zakat are open questions for the owner.

## The field in one table

| App | Where | Price | Data lives | Capture | Bank link | Budget method | Wealth (investments, gold, loans) |
|---|---|---|---|---|---|---|---|
| **Say** (Egypt) | Android, iPhone | Free with limits; Pro about 100 EGP a month, 3-day trial | Cloud, encrypted | Voice, bank SMS, calendar and email | SMS | Categories, insights | No |
| **Qershnat** (Egypt) | Android | Free so far (in-app items 80 to 800 EGP) | Offline-first, shareable | Manual, bank SMS | SMS | Budgets, goals, debts, gam'eya | Yes: gold, silver, property, vehicles, investments |
| **Masarifi** (Egypt) | Android | Free with ads, paid removes them | On the phone | Manual | None | Categories, reports | No |
| **Masareef** (Arab world) | Android | Free with heavy ads, paid | Phone, Google Drive backup | Manual, SMS reading | SMS | Categories, loans, goals, recurring | Loans only |
| **Masroofy / Masrofi** (several unrelated apps share the name) | Android, iPhone | Free with ads, remove ads | On the phone | Manual, SMS import, receipt scan | SMS | Categories, budgets, zakat | Debts only |
| **Money Manager** (Realbyte, 10M+ installs) | Android, iPhone | Free with ads, EGP 99.99 once | On the phone | Manual, quick add | None | Category budgets | No. No Arabic |
| **Wallet** (BudgetBakers) | All | Free, Premium subscription | Cloud | Manual, bank sync (premium) | 15,000+ banks, not Egypt | Category budgets | Basic |
| **Telda, BM app** (banks) | Phone | Free with the account | The bank | Automatic, own cards only | Own bank only | Spending insights, category budget | No |
| **Actual Budget** | Web, desktop, self-host | Free, MIT | Your computer or server | Manual, import | SimpleFIN (US), GoCardless (EU) | Envelope, zero-based | No |
| **YNAB** | All | About 109 USD a year | Cloud | Manual, import, sync | US, Canada, EU | Zero-based | No |
| **Monarch** | Web, phone | 99.99 USD a year | Cloud | Sync | US, Canada | Flexible, forecast | Net worth, investments |
| **Copilot** | iPhone, Mac, web | 95 USD a year | Cloud | Sync | US | Category budgets | Net worth, investments |
| **Quicken Classic Premier** | Windows, Mac | **$7.99/month shown currently, billed annually**; first-year offer, then renews at then-current rate | Desktop file + Quicken services | Manual, bank downloads | US/Canada | Category budgets, rollover | **Deep:** securities, tax lots, IRR/ROI, allocation, retirement |
| **Banktivity** | Mac, iPhone, iPad | **Bronze $59.99/year · Silver $79.99/year · Gold $99.99/year**; investment accounts start at Silver, multi-currency at Gold | Local device + optional encrypted cloud sync | Manual, import, bank sync | 14,000+ institutions through providers | Category or envelope budgeting | **Deep:** lots, cost basis, IRR/ROI, gains, dividends, multi-currency |
| **Moneydance** | Windows, Mac, Linux; mobile companion | $49.99 one-time | Local, encrypted; device sync | Manual, bank downloads | Hundreds of institutions | Category budgets | Stocks, bonds, CDs, funds, splits, cost basis |
| **GnuCash** | Windows, Mac, Linux | Free, open source | Local file | Manual, import | Limited/direct import rather than consumer bank sync | Accounting budgets | **Deep accounting:** security lots, realized/unrealized gains, ROI/CAGR |
| **Firefly III** | Self-host | Free | Your server | Manual, import | None | Budgets, rules | Accounts only |
| **Lunch Money** | Web | Subscription | Cloud | Import, sync | Some | Flexible | Basic |
| **Lightning** | Windows (phone planned) | Free so far | Your PC, encrypted profile | Manual, CSV, PDF statements | None yet | Rollover budgets, reserves, plans | Yes: gold, shares, funds, CDs, loans |

## What users love, in every app

Each point names the apps where people say it and what Lightning does.

| What they love | Said about | Lightning today |
|---|---|---|
| **Logging without effort:** voice, SMS auto-logging. "Hands down best budgeting app I ever dealt with and I tried a lot"; "I resorted to using my notes" before it (Say, Google Play) | Say, Copilot, MonAi | Missing. The biggest gap |
| **Knowing where the month goes:** "helps me track how much I spend each month, so I can save more and see what I need to fix" (Say, App Store) | Say, Telda, Wallet | Have it, deeper (Expense analysis) |
| **Simple, uncluttered:** "extremely simple", quick add and autocomplete (Money Manager) | Money Manager, Masrofi | Quick add is partial; menus are heavier |
| **Pay once, no ads, no subscription** (Money Manager "Remove Ads") | Money Manager, Masrofi | Free today. Decide before release |
| **No bank login, no cloud:** "data stays on your hardware, nobody else has access" (Actual) | Actual, Masroofy, Money Manager | Have it. Our strongest shared promise |
| **Open source and free,** "YNAB without the subscription" (Actual, Reddit) | Actual, Firefly III | Free yes, open source not decided |
| **A method that changes behaviour:** "transformed my finances", "saved so much money and paid off so much debt" (YNAB, Trustpilot) | YNAB, Actual | Rollover budgets and reserves; no "give every pound a job" yet |
| **An Egyptian maker who listens and answers:** "proud the creator is Egyptian", "suggestions are added right away", "answers people on TikTok" (Say, Qershnat, Masarifi) | Say, Qershnat, Masarifi | A visible changelog, a feedback address and a human reply are marketing too |
| **Beautiful design:** "best-designed budgeting app on iOS", 4.8 stars (Copilot) | Copilot, Monarch, MonAi | The brand guideline is our answer. Keep it strict |
| **Arabic that works:** bilingual, mixed dialects, zakat, Arabic categories | Say, Masarifi, Masrofi | Check Arabic and right-to-left status before any Egypt launch |
| **Couples and household,** shared wallets and debts | Monarch, Qershnat | Missing |
| **Zakat and gam'eya built in** | Masroofy, Qershnat | Not in Lightning; ask the owner |
| **Fast entry details:** home-screen widget, set the time and date of a spend, edit or delete a record | Say, Masarifi, Money Manager (all asked) | Check Lightning's quick add at phone width |
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
| **A paywall before any try:** "can't be used without a subscription even though it's advertised as freemium", "no free trial unless I add my card" | Say (the most repeated complaint), Masareef | No card, no account, the whole app on day one |
| **SMS reading that misses or invents:** "sometimes they're tracked, most of the time they aren't"; a spend that was never made; Apple Pay and some banks missed | Say, Qershnat, Money Manager, Wallet | Show every parsed SMS for review before it posts; one tested rule per bank |
| **Cannot edit or delete a record** ("I delete everything and start over") | Say, Masarifi | Every row editable, always |
| **Data lost after a phone change or update, and no reply from support** | Masareef, Wallet (a "lifetime" plan cancelled, data gone), Masarifi | Backup and restore must be tested in Mohab's test |
| **A feature removed:** Wallet dropped Arabic; a 1-star review marked by 44 people says "I will look for another app" | Wallet | Never take away a language or a feature people use |
| **No Arabic, no Hijri date, mirrored numbers** | Money Manager, Wallet | Arabic and right-to-left are a launch condition |
| **Heavy ads in the free version** | Masareef, Money Manager | None |
| **Phone verification and SMS failures in Egyptian apps** | InstaPay | Do not depend on a one-time SMS to start |

## Local competitors

**Say – Hands free budget app (Roberto Joseph, Cairo).** The one to watch. Read directly from Google Play (Egypt), 2026-10-04.
- **Numbers:** 4.84 stars from 2,128 ratings, 50,000+ installs on Android; in-app items 49.99 to 999.99 EGP. Strong word of mouth: reviewers arrive "from TikTok" and the maker answers people there.
- **What it does:** voice entry (finds amount, date, category), bank-SMS auto-logging (also InstaPay), goals, debts and instalments, subscriptions and bills, multi-currency, weekly report. Says it understands 99+ languages.
- **What users love** (Arabic translated): "I used so many apps that were difficult, I resorted to my notes; this one is easy to track, understand and use"; "first time I've given an app 5 stars because it's genuinely useful"; "one source of truth for spending, debts, billing and subscriptions"; "no ads and no pro pop-ups"; "developers truly listen, suggestions are added right away"; "a clear competitor to foreign apps".
- **What users hate:** the paywall before any try (the most repeated, in both languages); a 3-day trial "too short"; about 100 EGP a month "a bit high" (compared with Anghami); the free plan cut to 3 accounts and about 7 voice notes; SMS not detected for some banks and Apple Pay; a blank screen after the app sits in the background; no offline mode, dark mode, PIN or biometric lock, or widget; cannot set the time of a spend; cannot import from other apps (a 4-year Wallet user wants to switch but cannot move data); some wrong calculations; slow support for some.
- **What users ask for that Lightning has or could have:** gold and other assets in one place ("property, silver, watches"), informal debts to people, a monthly budget per category, a spendable amount that leaves out goal money. Lightning's money held for others, reserves and category budgets answer several of these.
- **Gaps in Say:** no investments or net worth beyond gold; a cloud service, so offline and privacy are what users ask for (our opening). **We cannot match its speed of capture until Lightning has a phone app and SMS. We beat it on everything after capture, on offline, and on the free trial.**

**Qershnat (قرشنات).** New and rising: 4.85 stars from 592 ratings, 10,000+ installs, released June 2026, Egyptian. A life organiser, not only a budget: multi-currency wallets, budgets, goals, debts and instalments, shared wallets, money held for another person, gold and silver prices, gam'eya (rotating savings) with turns and proof of payment, gift money, tasks, documents, a password vault, property, vehicles and investments with returns, a smart assistant, bank-SMS logging, widgets, offline. Reviews: "one of the best financial apps in the whole Arab world", fast support, "better because it's Egyptian". Complaints: SMS logging "not always right, sometimes a spend I didn't make" (users ask to review before posting), lag after an update, a disliked UI change, a gam'eya display bug, and "what will it cost when finished?". Users ask for zakat and voice entry through WhatsApp. **It covers the same wealth ground and the same Egyptian life as Lightning. Read it closely before every roadmap decision.**

**Masarifi, Masareef (المصاريف) and Masroofy.** Simple Arabic expense trackers. Masarifi: 4.67 from 983 ratings, 10,000+ installs; loved for "simplicity and speed without extra philosophy"; asked to add debts, edits, percentages and the date of a spend. Masareef: 4.65 from 32,000 ratings, 1M+ installs; loved as the "easiest" app, hated for overwhelming ads, lost Google Drive backups after a phone change, a daily-average bug that ignores days without spending, and SMS reading that fails. Masroofy on Android (`com.masroofi.masroofi`) is tiny (23 ratings); the larger Masrofi on iPhone is a different app, so check which one a user means.**Money Manager and Wallet.** The global manual trackers Egyptians also install. Money Manager: 4.67 stars from 466,000 ratings, 10M+ installs; loved as simple and needing no bank; hated by Arabic readers for having **no Arabic** and no Hijri date, and for ads even in the paid version. Wallet: 4.78 from 387,000, 10M+; loved for multi-currency and a lifetime plan; hated for **removing Arabic**, no bank-SMS reading, a lifetime plan cancelled with data lost, and unanswered support. Both leave an opening for an Arabic-first app.

**Bank apps (Telda, BM Online, CIB).** Free categorised insights and category budgets inside the bank. They see only their own accounts, so a person with two banks, a wallet and cash gets half a picture. That half-picture is Lightning's opening.

## International competitors

**Actual Budget.** Open source (MIT), local-first, envelope (zero-based) budgeting, YNAB-like. Data in a local SQLite file; optional self-hosted sync server.
- Loved: free, private, "go-to for people who enter bank transactions weekly and sort them", former YNAB 4 users find it familiar.
- Complained: no native mobile app (a mobile web view that struggles with big budgets); self-hosting needs skill; bank sync only through SimpleFIN (US, about 15 USD a year) and GoCardless (EU), so none for Egypt; reports are thin ("hard to see where the family budget stands"); GitHub carries long-open sync issues.
- Against Lightning: it is the closest in philosophy (local, private, free) and our nearest rival for the technical user. It has no Egyptian anything, no wealth side and no desktop installer for ordinary people. Where it wins: a mature envelope method and a large community. **Copy its promise (your data stays yours), not its setup.**

**YNAB.** The method everyone copies. Loved for changing behaviour. Hated for price (about 109 USD a year, "no value added"), a busy interface and bank connections that break. No investments, no bills. Lesson: one method taught well can build a loyal community; do not charge more without adding more.

**Monarch.** The Mint replacement. 99.99 USD a year, household sharing, net worth and investments, AI assistant. Loved for intuitive design and no ads; hated for glitchy sync and price. Lesson: net worth plus household is what people pay for. We have the first, not the second.

**Copilot.** The best-looking app. 95 USD a year, iPhone and Mac only, AI categorisation. Loved for design; hated for one platform and per-person pricing. Lesson: design alone earns a 4.8.

**Quicken Classic Premier.** The traditional all-in-one benchmark for budgeting plus serious investment accounting, aimed at the US and Canada on Windows and Mac. **Price checked 2026-10-05:** Quicken currently displays Premier at $7.99/month billed annually as a first-year offer; it renews at the then-current rate. Its current investment tools calculate IRR and ROI, track allocation and dividends, use downloaded market data, and support tax-aware lot analysis. A sale can be assigned by implied or explicit FIFO, LIFO, maximum gain or minimum gain; mutual funds can instead use average cost. It also goes beyond Lightning today with retirement planning and tax reporting. **Against Lightning:** Quicken is currently deeper for conventional listed securities, tax lots and US tax analysis; Lightning is much more specific to Egyptian wealth, physical gold, local certificates, held-for-others ownership and cash planning. Lesson: benchmark its accounting depth, not its US-specific complexity.

**Banktivity.** The closest product-level benchmark for Lightning's combination of budgeting, local data and a real investment engine. **Price checked 2026-10-05:** Bronze is $59.99/year, Silver $79.99/year and Gold $99.99/year; the investment/retirement accounts and stock-price tools relevant to this comparison begin at Silver, while multi-currency and crypto/exchange-rate downloads require Gold. It runs natively on Mac, iPhone and iPad, keeps a local ledger and offers optional encrypted cloud sync. Its budgets can use category limits or envelopes. Investments include stocks, ETFs, funds, bonds, options, crypto, CDs and private securities; it tracks cost basis per lot, lets the user choose specific lots on sale (FIFO by default), separates short- and long-term realized/unrealized gains, and reports ROI and IRR with dividends and other investment income. **Against Lightning:** Banktivity is currently the stronger conventional investment engine and already has multi-currency and mature device sync; Lightning's opening is Egyptian assets and institutions, physical-gold detail, certificates, cash ownership, simpler language and the ledger/plan/report split.

**Moneydance.** A privacy-focused desktop personal-finance suite for Windows, Mac and Linux with budgeting, banking and real investment tracking. **Price checked 2026-10-05:** $49.99 as a one-time purchase from its official site. It supports stocks, bonds, CDs and mutual funds, automatic prices, stock splits and cost-basis calculations; its underlying model also has average-cost and lot-based capital-gain handling. **Against Lightning:** it is a useful engineering benchmark for mature security bookkeeping and multi-platform longevity, but not the UX or Egypt-specific product benchmark.

**GnuCash.** **Free and open source (GNU GPL)** rather than a paid product; there is no software subscription price. It is double-entry accounting rather than a modern consumer budgeting app, but its security accounting is deep enough to matter as a technical benchmark. Its Investment Lots report tracks purchases, sales, remaining basis, realized and unrealized gains, short- and long-term gains, ROI and CAGR, with lot validation. **Against Lightning:** GnuCash is deeper where accounting and tax-lot mechanics matter, while Lightning deliberately hides accounting language and integrates investments with consumer budgeting, cash planning and Egyptian wealth. Copy the correctness discipline, not the interface.

**Firefly III and Lunch Money.** Firefly III: self-hosted, rules and reports, manual only, no mobile app. Lunch Money: web, multi-currency, simple, praised support. Lesson: multi-currency and responsive support are loved by the people who find them.

## Phone flow, words and icons

How the best money apps lay out a phone, read 2026-10-06 (Claude) for the phone audit. Their tab bars: YNAB *Plan, Spending, Accounts, Reflect*; Copilot *Dashboard, Transactions, Investments, Accounts, Categories*; Monarch *Dashboard, Accounts, Transactions, Plan…*; Money Manager *Trans., Stats, Accounts, More*.

- **Words beside every icon.** Every one of them names each tab under its icon. Apple and Material 3 say the same (Material: with four or five tabs, labels on the inactive ones "if space permits"; "should only be used when the icons have a clear meaning"). Nielsen Norman Group: "text labels are necessary to communicate the meaning and reduce ambiguity", and if a fitting icon takes more than five seconds to think of, use a word. Universal icons only stand alone: search, back, close, add (+), more (⋯), settings.
- **Tabs move, they never act.** (Apple: "use a tab bar to support navigation, not to provide actions".) The everyday action, adding a transaction, sits one tap away on the main screens: YNAB puts *Add Transaction* on Plan and on Accounts; Money Manager a + on every list.
- **Home is a short answer and a to-do list.** Copilot opens on what to review and the month's progress; YNAB on the plan. Detail lives one tab away, not further down the home screen.
- **Rows say what a tap does.** A to-do row names its action (*Review*, *Pay*); segmented controls are words (Out, In, Transfer; Week, Month).
- **Entry is a sheet:** type first as words, the amount with the number pad, category picked from recent ones, Save in reach; a long press selects rows for a bulk change.

**For Lightning (audit 2026-10-06):** the tab bar already pairs icon and word. Section tabs with four tabs (Cash planning, Settings) show icons alone for all but the chosen one, as guideline C03.3 asks, and those icons (a bank for Loans, a shield for Reserves, a grid for Categories) are not universal; the phone Overview is about seven screens long against C11.1's one; the add button is only on Accounts and an account (C05.2). The owner decided all three on 2026-10-07 (guideline 3.27; Project Overview › Product decisions): words on every tab, the add button on every section, the Overview in one screen with the rest one row away. Sources: [Material 3 navigation bar](https://developer.android.com/reference/kotlin/androidx/compose/material3/NavigationBarItem.composable), [Apple tab bars](https://developer.apple.com/design/human-interface-guidelines/tab-bars), [NN/g via "every icon needs a label"](https://trevorcalabro.substack.com/p/every-icon-needs-a-label), [YNAB mobile tabs](https://support.ynab.com/en_us/spaces-in-the-mobile-app-S1iIZQoqgg.md), [Copilot tabs](https://www.macstories.net/?p=74917), [Copilot To review](https://help.copilot.money/en/articles/11157550-quick-start-guide).

## Where Lightning wins and loses

**Wins (say it on the website):**
- One ledger, plans that move no money, reports that read both. No other app keeps those three apart.
- Wealth depth that **most modern budgeting apps** lack: real holdings and returns beside physical gold, Egyptian certificates, loans and money held for others. Quicken, Banktivity, Moneydance and GnuCash are the investment-accounting exceptions, not evidence for this claim.
- Local, encrypted, no account, no server to run, Windows installer.
- Mohab's test: a full year through the screens, kept honest in the tests.
- Brand guideline: one calm, strict look.

**Loses (be honest, plan around it):**
- No phone capture, no SMS or voice: where Say wins every day.
- No automatic feed: every competitor with sync wins the first week.
- Windows only for now; most Egyptians budget on a phone.
- No household sharing, receipts, reminders or multi-currency.
- Conventional securities are not yet as deep as Quicken or Banktivity: no tax lots/specific-lot selling, stock splits or reinvested-dividend workflow, return of capital, mature corporate actions, tax reports or TWR; GnuCash and Moneydance also provide useful lot/cost-basis benchmarks.
- Arabic and right-to-left not confirmed.
- No community, reviews or ratings yet. Say has 2,128 ratings; Qershnat 592 in four months.
- No gam'eya, zakat or WhatsApp entry, which Egyptian users already ask Qershnat for.

## Watch list

Check every few months and edit this file:
- **Say:** its Pro price, trial rules (users hate the paywall), new features, rating and review count, and whether it adds investments.
- **Qershnat:** its price once "finished", an SMS review step, gam'eya and zakat, and its rating.
- **Masroofy:** the bank-message import and how many Egyptian banks work.
- **Telda and bank apps:** whether any opens its data to other apps (open banking in Egypt would change our plan).
- **Actual Budget:** a mobile app, or any Arabic and Egyptian bank import.
- **Egyptian aggregators:** a provider that offers bank feeds would change the SMS plan.

## Open source

Open-source finance apps are especially useful to Lightning because they let us inspect the financial rules and implementation, not just the finished interface. Use them as design and correctness references; do not copy code across incompatible licences without checking the licence first.

| Project | Repository | What it is | Why it matters for Lightning |
|---|---|---|---|
| **Actual Budget** | [actualbudget/actual](https://github.com/actualbudget/actual) | Local-first envelope budgeting with sync, imports, schedules, rules, reports and a large TypeScript codebase. | **Best budgeting/workflow benchmark.** Study rules, undo, import matching, recurring schedules, sync, i18n and testing. It is already analysed in detail below. |
| **Sure** | [we-promise/sure](https://github.com/we-promise/sure) | Community-maintained continuation of Maybe Finance: self-hosted personal finance and wealth management with accounts, transactions, investments, budgets and multiple clients. | **Closest broad product-shape reference.** It combines everyday money and wealth in one product, so inspect its account/holding model, portfolio UX, net-worth flows and web/mobile architecture. |
| **Paisa** | [ananthakumaran/paisa](https://github.com/ananthakumaran/paisa) | Personal-finance manager with budgeting plus stocks, mutual funds, allocation targets, goals, recurring entries, capital gains and tax-harvesting tools. | **High-priority investment reference.** Its mix of budgeting and investments is unusually close to Lightning; inspect allocation, capital-gain and portfolio-analysis logic without importing its tax assumptions blindly. |
| **GnuCash** | [Gnucash/gnucash](https://github.com/Gnucash/gnucash) | Mature double-entry accounting application with security lots, cost basis, realized/unrealized gains, ROI/CAGR and stock-split handling. | **Investment-accounting correctness benchmark.** Its lot engine and portfolio reports show how mature software handles basis, FIFO/LIFO/average cost, gains and validation. Copy the accounting discipline, not the accountant-facing UX. |
| **KMyMoney** | [KDE/kmymoney](https://github.com/KDE/kmymoney) (official GitHub mirror; canonical repo is [KDE GitLab](https://invent.kde.org/office/kmymoney)) | Long-running KDE personal-finance suite with budgets, banking, investments and forecasting across desktop platforms. | **Mature domain-model benchmark.** Useful for investment accounts, scheduled transactions, forecasting, imports and the edge cases accumulated by a long-running finance application. |
| **Money Manager Ex** | [moneymanagerex/moneymanagerex](https://github.com/moneymanagerex/moneymanagerex) | Cross-platform personal-finance app with banking, stock-investment accounts, assets, budgets, scheduled bills, cash-flow forecasts, splits and reports. | **Strong simplicity + breadth benchmark.** Especially relevant to Lightning's desktop direction, SQLite/encryption choices, stock accounts, forecasting, portable installs and current work on local-first multi-device clients. |
| **Firefly III** | [firefly-iii/firefly-iii](https://github.com/firefly-iii/firefly-iii) | Self-hosted personal-finance manager built around double-entry bookkeeping, budgets, rules, recurring transactions, imports and a broad API. | **Rules/API/import benchmark.** Less useful for Lightning's investment engine, but valuable for automation, transaction rules, recurring workflows, import architecture and API design. |
| **OpenBudgeteer** | [TheAxelander/OpenBudgeteer](https://github.com/TheAxelander/OpenBudgeteer) | Focused bucket-budgeting app inspired by YNAB and Buckets, built with .NET and Blazor. | **Small, readable budgeting reference.** Useful when we want to study bucket/envelope behaviour without the size and complexity of Actual Budget. |
| **Cashew** | [jameskokoska/Cashew](https://github.com/jameskokoska/Cashew) | Flutter budgeting and expense-tracking app with flexible budgets, goals, repeating/upcoming transactions, multi-currency, sync, imports and a mobile-first interface. | **Best UX/mobile reference in this group.** Study transaction entry, flexible budget periods, goals, responsive layouts, charts, mobile navigation and automation links rather than investment accounting. |
| **Ivy Wallet** | [Ivy-Apps/ivy-wallet](https://github.com/Ivy-Apps/ivy-wallet) — **archived/read-only** | Former Android-first open-source money manager written in Kotlin/Jetpack Compose, known for a simple mobile experience. | **Historical Android UX/architecture reference only.** Useful for Compose patterns, mobile transaction entry and simplicity, but not a current product/roadmap benchmark because maintenance stopped and the repo is archived. |

**Research priority for Lightning:** Sure and Paisa for product/investment overlap; GnuCash for investment-accounting correctness; Actual for budgeting/workflow machinery; Money Manager Ex for desktop/local-first breadth; Cashew for mobile UX. The others are secondary references for specific problems.

## Actual Budget code analysis

**What was read:** a shallow clone of `actualbudget/actual` at commit `9732a44` (2026-10-04, "Auto bank sync"). Read in the code: the rules engine, budget templates, spreadsheet (calculation) engine, sync and CRDT, bank-sync pipeline, importers, schedules, forecast, undo, reports, i18n, tests, CI and the repo's AI-agent files. Not run: the app itself, so speed and look are not judged. Actual is TypeScript (about 14 packages; 1,010 files in the web client, 346 in the core, 133 in the sync server) and Lightning is Python, so this is a list of **ideas to borrow, not code to copy**. File paths below are inside `packages/`.

### What Actual does better, most valuable first

| # | Actual has | Where in its code | Lightning today | Take |
|---|---|---|---|---|
| 1 | **A real rules engine.** Conditions joined by and/or (contains, matches a pattern, one of a list, between two amounts, about an amount, has tag); actions set any field, split a transaction by fixed amount, percent or remainder, link a schedule, append notes; three stages (pre, default, post); runs on import and on edit; an index by field keeps it fast | `loot-core/src/server/rules/` (1,824 lines): `condition.ts`, `action.ts`, `rule.ts`, `rule-indexer.ts` | One default category per counterparty, a bulk apply with one undo. No conditions, no amounts, no splits by rule | A small rule table: if counterparty or notes contain X, and amount in a range, then category (and optional split). Plain code, no AI, fits the product rule. Actual keeps `learnCategories` **off** by default (`transactions/index.ts`), so learn only by suggesting |
| 2 | **Undo and redo everywhere.** A history of 20 steps over every change, restoring the old data and the view | `loot-core/src/server/undo.ts` | Undo only for bulk rules and a skipped payment | Undo for the last edit, delete or import. Fits "a wrong or silent result is worse than an extra click"; Say's reviewers also ask for edit and delete |
| 3 | **A layered import match.** Exact imported id first, then fuzzy by amount and nearest date; on a tie it prefers the row without an id; **reconciled rows are locked** and never overwritten; payee names optionally normalised | `loot-core/src/server/accounts/sync.ts` (`matchTransactions`, `reconcileTransactions`, `compareFuzzyMatchCandidates`) | Duplicate flag by bank reference; a row links to an entry with the same amount within 3 days, closest first, each entry once; reconciliation by balance check | Reuse the layers for SMS against CSV (the multi-device plan) and lock a checked month. Also a **merge two transactions** action that keeps a transfer linked (`transactions/merge.ts`) |
| 4 | **Schedules that know weekends and ranges.** An iCal-style recurrence engine, "skip weekend" with move before or after, skip next date, approximate or between-amount matching, and automatic detection of recurring payments from three occurrences | `loot-core/src/server/schedules/` (`app.ts`, `find-schedules.ts`), `shared/schedules.ts` | Recurring items with review of changed amounts and suggestions; **no weekend or holiday handling** | Weekend-aware due dates matter in Egypt (Friday and Saturday, salary dates that move). Add an amount tolerance to payment matching |
| 5 | **Budget templates.** One line per category (fixed monthly, by a date, repeat yearly, from a schedule, percent of income, remainder with weights, average of N months, cleanup rules) and one click fills the month. A real grammar, tests, and priorities | `loot-core/src/server/budget/goal-template.pegjs`, `goal-template.ts`, `cleanup-template.ts`, `schedule-template.ts` | Rollover budgets and reserves; every month is set by hand | The same types, but through a form, not text typed into notes (the brand guideline forbids help-text features). "Fill this month" from last month, a schedule or a goal is the first step |
| 6 | **Translations and number formats built in.** i18next, locale files, a CI job that extracts strings, a review rule that every visible string is translated, about 50 currencies with CLDR number formats | `desktop-client/src/i18n.ts`, `languages.ts`, `loot-core/src/shared/currencies.ts`, `.github/workflows/i18n-string-extract-master.yml` | English only. Arabic-Indic digits are read on input, but no Arabic screens and no right-to-left layout | Add the scaffolding before more screens are written. Money Manager and Wallet lose Egyptian users for exactly this |
| 7 | **Small entry helpers.** Arithmetic in amount fields (`120+35*2`, a real parser, no `eval`); tags written as `#tag` in notes; a command bar (Ctrl-K); a privacy filter that blurs amounts; keyboard navigation | `loot-core/src/shared/arithmetic.ts`, `shared/tags.ts`, `desktop-client/src/components/CommandBar.tsx`, `PrivacyFilter.tsx` | All four built: sums in amount fields, `#tag` in notes, the Ctrl-K command bar, privacy mode | Done |
| 8 | **Reports as a dashboard.** 14 report types you arrange as cards and save (Age of Money, Calendar, Cash flow, Net worth, Spending, Sankey, Balance forecast, Crossover, Budget analysis, Summary, Formula, Markdown, Monte Carlo); saved custom reports share one filter model with rules and schedules | `desktop-client/src/components/reports/reports/`, `loot-core/src/server/dashboard/`, `aql/` (2,467 lines) | Four fixed reports plus the Overview, with a Sankey | **Age of Money** (how long money rests before it is spent) suits people who live salary to salary; a **spending calendar**; and one saved-filter object shared by search, reports and rules. Leave Monte Carlo |
| 9 | **A change note per change.** Each pull request adds a file in `upcoming-release-notes/` (32 waiting) instead of editing one shared changelog | `upcoming-release-notes/`, `.github/workflows/release-notes.yml` | One `CHANGELOG.md`; two AIs conflicted in it three times in this session | One small file per change, joined at release, or at least a merge rule for the changelog |
| 10 | **Test depth.** 247 test files, end-to-end tests with a mobile variant of each flow, **visual regression snapshots** for pages, a bundle-size check per pull request, dead-code check (knip), security scans (CodeQL, dependency review), a warning on pull requests that touch migrations | `desktop-client/e2e/`, `.github/workflows/` (35 workflows), `knip.json` | 551 test functions; the full suite on every push; Mohab's year (a deeper check than Actual has for correctness) | Visual snapshots of key screens would guard the brand guideline; the migration warning is cheap to copy |

### What not to copy

- **The sync design.** Actual syncs many writers with a CRDT (hybrid logical clock in `crdt/src/crdt/timestamp.ts`, a merkle trie to find where two copies differ in `merkle.ts`) and end-to-end encrypted files. It works, but its own issue list shows the cost: open reports of "can't open budget on mobile" and "can't sync changes" ([#6279](https://github.com/actualbudget/actual/issues/6279), [#7542](https://github.com/actualbudget/actual/issues/7542), [#6223](https://github.com/actualbudget/actual/issues/6223)). Lightning's choice (the phone lends the file, one writer at a time) avoids merging on purpose. Keep it. One thing is worth borrowing: the merkle idea for finding which tables differ at take-back.
- **The calculation engine.** Actual recomputes budget cells through a dependency graph with a dirty-cell queue (`spreadsheet/spreadsheet.ts`, `graph-data-structure.ts`) so editing a cell updates only what depends on it. It is fast, but it is a second place where figures live. Lightning's figures come from services, one name and one calculation, and a test that lives a year. Revisit only if the Budget page is measurably slow.
- **Multi-user, sign-in with OpenID, a public API, a command-line tool and plugins** (`sync-server/src/app-openid.ts`, `packages/api`, `packages/cli`, `plugins-service`). They serve self-hosting households and developers, not a salaried user on one Windows PC.
- **Text typed into notes as a language.** It works for Actual's technical users and fails Lightning's "won't read help text" user.

### Bank sync, for the record

Actual has **five** providers behind one pipeline: GoCardless, SimpleFIN, Pluggy.ai (Brazil), Akahu (New Zealand), Enable Banking (`sync-server/src/app-*`, `accounts/sync.ts`). Adding a regional provider is routine for them, and none covers Egypt. If an Egyptian aggregator appears, the same shape applies: one normaliser, then the layered match in #3. Until then, bank SMS and statements stay Lightning's route.

### Where Lightning is already ahead of Actual

- **Wealth.** Actual has on-budget and off-budget accounts and no holdings. Lightning has gold by piece, shares and funds with real returns, certificates, loans, and money held for others.
- **Numbers.** Both are exact. Actual stores integers with at most two decimals in every listed currency; Lightning stores scaled integers to six places, which gold grams and fund units need.
- **Privacy on the PC.** Lightning's profile is encrypted at rest (SQLCipher with an Argon2id password slot and a recovery key). In Actual's code, encryption is applied to files sent to the sync server (`server/encryption/`, `cloud-storage.ts`); its docs describe end-to-end encryption as protecting data that leaves the device, and the code has no SQLCipher or local-file encryption.
- **Install.** A Windows app and a password. Actual's easy path is a hosted or Docker server.
- **Acceptance.** Mohab's test checks right answers, clarity and the brand guideline through the screens; Actual's tests check code and screenshots.
- **Dark mode.** Both have it; Actual adds a midnight theme and a custom-theme catalog.

### Worth copying from how Actual runs AI agents

Actual's repo has `AGENTS.md` (about 20 KB), `CODE_REVIEW_GUIDELINES.md` and five repo skills (`committing-actual-changes`, `review-actual-pr`, `running-vrts`, `writing-actual-docs`, `writing-release-notes`) under `.claude/skills/`. Pull requests by an AI must start with `[AI]`, and a workflow labels them "AI generated". Its review rules include **"do not add a setting for every UI tweak"** and "every standalone figure uses tabular numerals". Lightning already has the same rules in `AGENTS.md` and the brand guideline (111 tabular-number rules in `style.css`). Two additions fit: repo skills for the repeated tasks (push, changelog, hand-off) and a short review checklist for an AI that reviews another AI's push.

### Suggested order

1. **Undo for the last edit or import** (#2): the most trust per line of work.
2. **Rules with conditions** (#1), then the **layered match and a locked checked month** (#3): they also serve the SMS plan.
3. **Weekend-aware schedules** (#4) and **a month fill from last month or a schedule** (#5).
4. **i18n scaffolding and Arabic** (#6) before the screens multiply.
5. **Small helpers** (#7) as time allows; **one change note per change** (#9) to end changelog conflicts.

None of this is decided: the owner chooses what enters *Next* in `NOW.md`.

## Evidence limits and sources

**Read directly (2026-10-04):** Google Play, Egypt store, through the `google-play-scraper` library: app details and the most relevant reviews (60 per language for Say, 40 for Qershnat, Masarifi, Masareef, Money Manager and Wallet), English and Arabic. Most relevant is not a random sample: it favours reviews people marked helpful. Arabic quotes are my translation.

**Not read:** the App Store, Reddit, Facebook, Trustpilot, GitHub discussions and Say's own site (blocked or refused to a scripted visit). The Actual Budget, YNAB, Monarch, Copilot, Firefly III and Telda sections come from review-site summaries, not from users' own words. **Investment-suite update (2026-10-05):** Quicken, Banktivity, Moneydance and GnuCash were checked against their current official product/help documentation, including official pricing/store pages; no user-review claims are made for them. Prices are USD and can change; Quicken's displayed Premier price is explicitly a first-year promotion. Earlier search summaries gave Say 4.63 stars; Google Play itself says 4.84, which this file uses. Check any number or quote at its source before it goes on the website.

**The Actual Budget code analysis** is from the code only (the app was not run); user feedback on Actual comes from the sections above. **Next:** Egyptian Facebook groups and TikTok comments (Say's maker and Qershnat both answer there), the App Store reviews of the same apps, and Actual Budget's own forum, from a browser that can open them.

Sources: [Say](https://play.google.com/store/apps/details?id=com.moments.expenses&hl=en&gl=EG), [Qershnat](https://play.google.com/store/apps/details?id=com.qrshnat.app.gms), [Masarifi](https://play.google.com/store/apps/details?id=com.tm.my_expenses), [Masareef](https://play.google.com/store/apps/details?id=com.appsqueue.masareef), [Money Manager](https://play.google.com/store/apps/details?id=com.realbyteapps.moneymanagerfree), [Wallet](https://play.google.com/store/apps/details?id=com.droid4you.application.wallet), [Masroofy](https://play.google.com/store/apps/details?id=com.masroofi.masroofi), [YNAB on Trustpilot](https://www.trustpilot.com/review/ynab.com), [Monarch review roundup](https://marriagekidsandmoney.com/monarch-money-review/), [Copilot review roundup](https://www.thepennyhoarder.com/budgeting/budgeting-copilot-money-review/), [Actual Budget review](https://wealthypot.com/budgeting-apps/actual-budget/), [Actual Budget mobile issue](https://github.com/actualbudget/actual/issues/6279), [Quicken pricing](https://www.quicken.com/products/pricing-comparison/), [Quicken Classic Premier](https://www.quicken.com/products/classic-premier/), [Quicken lot assignment](https://www.quicken.com/support/assigning-lots-quicken/), [Banktivity pricing](https://www.banktivity.com/content/plans/plans.php), [Banktivity investment tracking](https://www.banktivity.com/content/topics/investment-tracking/), [Banktivity portfolio lots](https://www.banktivity.com/content/help/v10/reports/portfolio.php), [Moneydance](https://moneydance.com/hello), [GnuCash](https://www.gnucash.org/), [GnuCash Investment Lots](https://www.gnucash.org/docs/v5/C/gnucash-manual/report-classes.html), [Firefly III review](https://www.expensesorted.com/blog/147_firefly_iii), [Telda](https://telda.app/), [Banque Misr BM Online](https://www.banquemisr.com/en/Pages/BM-Online---Internet-and-Mobile-banking).
