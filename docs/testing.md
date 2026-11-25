# ShopImpact — testing log

*Stage 4 of the WACP brief: test as a new user, find what breaks or confuses, fix it, and add creative features.*

---

## 1. How the app was tested

| Kind of test | What it covers | Where |
|---|---|---|
| Automated unit and API tests | The maths, badge rules, validation, turtle pen, data storage, backup and restore | `tests/test_engine.py` (58 tests) |
| Automated Streamlit tests | The real `app.py` run headlessly: every screen renders; ringing up a purchase through the widgets works | `tests/test_streamlit_app.py` (5 tests) |
| Purchase scenarios | 29 cheap, expensive, eco, non-eco, invalid, missing and boundary inputs | Section 3 |
| Screen-by-screen checks | Every screen in a browser (desktop and phone, light and dark), plus 15 interaction checks driven headlessly | Section 4 |
| Code review | A line-by-line review against the brief and rubric that found 25 issues, all now fixed or addressed | Section 5 |
| Real users | Friends and family trying the app and giving feedback | Section 6 — *to be completed* |

Run the automated tests:

```bash
python -m unittest discover tests
```

Latest run: **63 tests, all passing.**

## 2. Automated tests by area

| Area | Tests | Examples of what is checked |
|---|---|---|
| CO₂ maths | 9 | price × multiplier; currencies converted before multiplying; every swap is greener than the original |
| Brands | 7 | every brand points at a real product type; no duplicates; 100+ brands for each of India, Singapore, Switzerland and the US |
| Countries and currencies | 3 | every country has a known currency; price-tag steps make sense for small-unit currencies |
| Monthly summary | 4 | totals, the cumulative day-by-day series, grouping by category and tier |
| Badges | 8 | penny purchases can't farm badges; month-long badges lock in only when the month ends; Carbon Cutter compares day for day; First Step is lifetime |
| Eco score | 3 | going over budget pulls the score down; a huge footprint can't score well; what-if numbers come from Python |
| Validation and data | 7 | NaN, infinity, text and negative prices; strict dates; future dates; over-long text; CSV formulas defused; backup → restore round trip |
| Turtle graphics | 4 | a square returns home; a circle closes; fills appear after their outline; every drawing renders |
| API (web edition) | 13 | add, swap, delete and restore; bad months return 400 not 500; exchange-rate changes don't rewrite history; a new budget doesn't rewrite last month |
| Streamlit app | 5 | all six screens render; a purchase rung up through the widgets reaches the receipt and the footprint card; a missing price shows a friendly error; the price tag follows the typed price |

## 3. Purchase scenarios

Run against the app's Python service with a fixed date of 24 November 2026, so the results can be repeated. *Actual result* is the real output, copied from the run.

| # | Scenario | Expected | Actual result |
|---|---|---|---|
| 1 | Cheap, low impact: second-hand clothing £5 | ≈0.40 kg, low, leaf sprig | Saved · 0.40 kg · low · turtle draws sprig |
| 2 | Expensive, high impact: long-haul flight £950 | ≈1,330 kg, high, deep footprint | Saved · 1,330.00 kg · high · turtle draws deep step |
| 3 | High impact: beef & lamb £20 | 52 kg, high; swap to plant protein saves 47 kg | Saved · 52.00 kg · high · turtle draws deep step · swap → Plant protein (beans, tofu, dal) saves 47.0 kg |
| 4 | Expensive, low impact: refurbished laptop £600 | 90 kg, low | Saved · 90.00 kg · low · turtle draws sprig |
| 5 | Medium impact: new phone £799 | ≈479 kg, medium, light steps | Saved · 479.40 kg · medium · turtle draws steps |
| 6 | Rounding: fast fashion £12.3456 | price stored as £12.35 | Saved · 11.12 kg · high · turtle draws deep step · price stored as 12.35 |
| 7 | Tiny: second-hand book £0.01 | saved, but doesn't count towards badges | Saved · 0.00 kg · low · turtle draws sprig |
| 8 | Boundary: £1,000,000 | accepted (upper limit) | Saved · 120,000.00 kg · low · turtle draws sprig |
| 9 | Boundary: £1,000,000.01 | rejected — too large | Rejected: “That price looks too large — check for an extra zero.” |
| 10 | Invalid: price 0 | rejected | Rejected: “Enter a price above zero.” |
| 11 | Invalid: price −5 | rejected | Rejected: “Enter a price above zero.” |
| 12 | Missing: no product type | rejected | Rejected: “Choose a product type from the list.” |
| 13 | Missing: no price | rejected | Rejected: “Enter a price as a number, for example 24.99.” |
| 14 | Invalid: price “abc” | rejected | Rejected: “Enter a price as a number, for example 24.99.” |
| 15 | Invalid: price “NaN” | rejected (previously crashed) | Rejected: “Enter a price as a number, for example 24.99.” |
| 16 | Invalid: price “Infinity” | rejected | Rejected: “Enter a price as a number, for example 24.99.” |
| 17 | Invalid date: 30 February | rejected | Rejected: “Pick a valid date (YYYY-MM-DD).” |
| 18 | Odd date format “2026-W48-2” | rejected (previously saved as corrupt data) | Rejected: “Pick a valid date (YYYY-MM-DD).” |
| 19 | Odd date format “20261124” | rejected | Rejected: “Pick a valid date (YYYY-MM-DD).” |
| 20 | Future date 5 Dec 2026 | rejected — log purchases once made | Rejected: “That date is in the future — log purchases once you've made them.” |
| 21 | Brand longer than 60 characters | rejected with a message | Rejected: “Keep the brand under 60 characters.” |
| 22 | Brand containing HTML `<img onerror=…>` | saved as plain text, shown safely | Saved · 4.00 kg · medium · turtle draws steps |
| 23 | Brand `=HYPERLINK(…)` exported to CSV | cell starts with `'` so spreadsheets don't run it | Exported as `'=HYPERLINK(…` |
| 24 | ₹2,000 fast fashion (country set to India) | converted to £ first, then × 0.90 | 15.44 kg · after an exchange-rate change: 15.44 kg (unchanged) |
| 25 | One £2,500 low-impact buy (188% of budget) | eco score pulled down, not grade A | 375.0 kg = 188% of budget · score 47 (D, Heavy-ish) |
| 26 | Five £0.01 second-hand items | only First Step | Badges earned: First Step |
| 27 | Eco Saver of the Month: 5 light buys, checked on 24 Nov and 2 Dec | on track mid-month, earned after the month ends | 24 Nov: “On track — locks in when November ends.” · 2 Dec: earned = True |
| 28 | Delete a purchase, then Undo | row removed, then restored with the same CO₂ | after delete: 5 purchases · after undo: 6 purchases |
| 29 | Open month “2026-13” | friendly error (previously crashed) | Rejected: “Month must look like 2026-11.” |

**Result: 29 of 29 behave as expected, with no crashes.**

## 4. Screen-by-screen checks in the browser

### 4a. Clicked by hand in the running Streamlit app

Desktop size (1440 × 900) and phone size (375 × 812), in Daylight and Night canopy.

| Screen | What was done | Result |
|---|---|---|
| Overview | Picked Leather shoes, Clarks, £85 → live estimate (102 kg, high) with the formula and a swap offer; the price tag moved to £85; Ring it up → receipt fed out with the printer light blinking, the turtle stamped a deep footprint, the footprint and spend cards and eco score updated, the form reset | Works |
| Overview | Load a sample month → confirmation dialog → 15 + 7 purchases, the chart and breakdown filled in | Works |
| Brand dropdown | Typed "ta" → TANGS, Target, Tanishq, Tata 1mg, Taco Bell and TAG Heuer listed with their logos; picked Target → its logo shows in the field; the custom "Add: ta" option has no logo | Works |
| Ledger | Swap on leather shoes → dialog with greener brand picks → picked Veja → row became "Recycled or plant-based shoes · swapped from leather shoes", saving shown; deleted a row, then Undo restored it | Works |
| Swaps, Badges, Garden, Settings | Each screen opened and drawn correctly: what-if figures, logo wall and catalogue; badge states (Earned, On track, Lifetime); the turtle grew the month's tree; settings cards | Works |
| Themes | Switched to Night canopy in Settings → every screen, including Streamlit's own widgets, recoloured | Works |
| Phone | Bottom tab bar; every one of the six screens fits the width (no sideways scrolling) | Works |
| Browser console | No errors on any screen | Clean |

### 4b. Driven headlessly (Streamlit AppTest, against the real `app.py`)

| Check | Result |
|---|---|
| Ledger search "oat" narrows the list (15 → 2 rows); clearing it shows all 15 again | Pass |
| Impact filter set to Low only shows 10 of 15 rows | Pass |
| Sort by highest CO₂ puts the heaviest purchase first | Pass |
| Delete removes a row; Undo brings it back | Pass |
| What-if slider at 100% shows exactly the saving Python calculated (112.5 kg) | Pass |
| Catalogue group filter (Food) | Pass |
| "Watch it drawn" opens the badge dialog | Pass |
| Garden Replay and "Another quote" | Pass |
| Choosing Singapore in Settings switches the currency to SGD | Pass |
| Theme choice is saved | Pass |

**Not clicked:** the CSV and backup *download* buttons, because they save files to the computer. What they produce is covered by scenario 23 (CSV) and the backup → restore test.

## 5. Problems found and fixed

A full review of the code against the brief found these issues. Every one was fixed, and most now have an automated test so they can't come back.

| Problem found | What could go wrong | Fix | Test |
|---|---|---|---|
| A price of "NaN" crashed the request | A server error instead of a message | Prices must be finite numbers | `ValidationTests.test_numbers` |
| Dates like `2026-W48-2` were accepted | Corrupt rows saved, hidden and impossible to delete | Strict `YYYY-MM-DD` dates only | `ValidationTests.test_strict_dates` |
| Invalid months (13, 00, letters) crashed three screens | Server errors | Months checked before use | `ApiTests.test_bad_months_are_400_not_500` |
| The eco score only looked at kg per £ | 188% over budget still showed grade A; spending more raised the score | Score scaled down when over budget | `EcoScoreTests` |
| Badges counted 1p purchases | Six badges from five £0.01 entries | Only purchases ≥ about £1 count | `test_penny_purchases_cannot_farm_badges` |
| "Eco Saver of the Month" was awarded mid-month | Awarded, then lost after one more purchase | Month-long badges show "on track", then lock in at month end | `test_month_badges_lock_in_only_when_the_month_ends` |
| Carbon Cutter compared a part month with a full month | Earned on day 24 just because the month wasn't over | Day-for-day comparison | `test_carbon_cutter_compares_like_for_like` |
| First Step showed as "unlocked this month" in empty months | Misleading | Labelled as a lifetime badge | `test_first_step_is_a_lifetime_badge` |
| Changing the budget rewrote past months | Last month's badges could disappear | Each month keeps its own budget | `test_new_budget_does_not_rewrite_last_month` |
| CO₂ was recalculated with today's exchange rate | Old purchases changed value over time | £ value, CO₂ and rate frozen when logged | `test_rate_changes_do_not_rewrite_history` |
| Future-dated purchases were allowed | Dashboard total and chart disagreed; next-month entries unreachable | Future dates refused; date picker capped at today | `test_future_dates_are_refused` |
| CSV export copied formulas as-is | A spreadsheet could run them | Risky cells prefixed with `'` | `test_csv_cells_are_defused` |
| Calculations were copied into JavaScript | Two versions could disagree | All maths in Python only | `test_whatif_comes_from_python` |
| Swaps screen overflowed on phones | Sideways scrolling | Chips wrap (checked in the browser) | Section 4 |
| Some text failed colour contrast | Hard to read | Colours adjusted to pass WCAG AA | See `docs/design.md` |
| Database connections were never closed | Resource warnings and possible leaks | Every connection closed after use | Tests run with warnings treated as errors |
| "Today" came from the server's clock | Wrong month near midnight for users in other time zones | Uses the shopper's own time zone | — |
| Long brand names were cut off silently | Confusing | A clear message instead | `test_long_text_is_refused_not_cut` |

## 6. Testing with real people — *to be completed by the developer*

The brief asks: "ask friends/family to try it and observe what confuses them." Run this with 2–3 people (ideally one student, one adult who shops for a family) and record what really happened. Don't fill this in until it has.

**Tasks to give each person (don't help unless they're stuck for a minute):**

1. "Log something you bought this week."
2. "Find out which of your purchases has the biggest footprint."
3. "Swap one purchase for a greener option."
4. "Find a badge you're close to earning."
5. "Change the app to dark mode."

**Questions afterwards:**

- What did you think the app was for, in one sentence?
- What confused you?
- Did anything make you feel guilty, or did it feel encouraging?
- Would you use it again? Why or why not?

| Tester (role, age) | Task they struggled with | What they said | What I changed afterwards |
|---|---|---|---|
| *e.g. classmate, 17* | | | |
| | | | |
| | | | |

## 7. Known limitations

- **CO₂ estimates are approximate.** Spend-based factors suit comparing choices, not exact accounting. Prices are converted to pounds at market rates, which doesn't adjust for purchasing power between countries.
- **Streamlit Cloud storage is temporary.** Data can reset when the app restarts. Settings → Download a full backup keeps a copy.
- **The price tag updates on release.** Streamlit sends the slider's value when you let go; the tuck sounds play live while you drag.
- **Logos** come from each brand's website icon. A few brands without a usable icon show a neat monogram instead.
