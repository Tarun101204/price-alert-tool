# Price Alert Tool

A lightweight, zero-dependency command-line tool that evaluates daily instrument prices against configurable alert rules (`level` and `ma_cross`) and outputs fired alerts in chronological order.

Built for the **Wissen Technology Campus Assessment**.

---

## 1. How to Run It

### Requirements
- **Python 3.8+** (Uses only Python Standard Library: `csv`, `json`, `sys`, `decimal`, `datetime`, `unittest`).
- **Nothing to install** (`pip install` is NOT required).

### Execution Command
```bash
python alerts.py <prices.csv> <rules.json>
```

#### Example using sample data:
```bash
python alerts.py data/sample_prices.csv data/sample_rules.json
```
**Output:**
```
2026-09-03 r1 INFY level below 1500
```

#### Example using extended 30-day dataset (demonstrating both rules):
```bash
python alerts.py data/extended_prices.csv data/sample_rules.json
```
**Output:**
```
2026-09-03 r1 INFY level below 1500
2026-09-24 r2 TCS ma_cross 5/20 above
```

### Running Tests
Execute all 31 unit and integration tests with one command:
```bash
python run_tests.py
```
*(Also fully compatible with `python -m unittest discover -s tests` or `pytest`).*

---

## 2. Rule Semantics & Edge Case Handling

1. **Level Rule (`level`)**:
   - Fires strictly on the first day price transitions from the opposite side (`it was on the other side the previous day`).
   - If price stays on the crossed side across subsequent days, **no duplicate alerts** fire.
   - Day 1 cannot fire because it has no preceding trading day.
   - Exact touches (e.g., $1510 \to 1500 \to 1490$) cleanly trigger when crossing below completes at 1490; bounces ($1510 \to 1500 \to 1510$) do not trigger.

2. **Moving Average Cross Rule (`ma_cross`)**:
   - Moving averages are computed over **trading days** (chronological rows per instrument), not calendar days.
   - Full window requirement: For short window $S$ and long window $L$ ($S < L$), the long MA is defined for the first time on trading day $L$.
   - Because day $L-1$ lacked a defined long MA, day $L$ only establishes the initial baseline relative position. **The earliest possible day an `ma_cross` can fire is day $L+1$**.

3. **Real-World Data Resilience**:
   - **Out-of-order rows**: Automatically sorted chronologically per instrument.
   - **Interleaved instruments**: Grouped independently.
   - **Whitespace & BOM**: Automatically stripped (`utf-8-sig`).
   - **Corrupted rows**: Duplicate timestamps for same instrument, malformed numbers, negative/zero prices, and bad headers raise clear descriptive errors.
   - **Exact Arithmetic**: Evaluated with `decimal.Decimal` to eliminate binary floating-point rounding errors (e.g., `1499.9999999999998` vs `1500.00`).

---

## 3. How the Assistant Was Used (Prompts in Brief)

1. **Prompt 1 (Requirements & System Design)**: Analyzed the brief's inputs, JSON rule schemas, exact output format, and proposed a zero-dependency architecture.
2. **Prompt 2 (Boundary & Edge Case Discovery)**: Brainstormed real-world data pitfalls: scrambled dates, missing calendar days, floating-point precision, touches vs crosses, and MA window boundaries.
3. **Prompt 3 (Test Suite Generation)**: Generated unit and integration tests covering positive cases, negative cases, boundary conditions, and CLI behavior.

---

## 4. What the Assistant Got Wrong & What Was Changed

| Gotcha / Defect | What the AI Initially Suggested | Why It Was Wrong | What Was Changed & Why |
| :--- | :--- | :--- | :--- |
| **1. MA Cross Day $L$ Boundary** | Attempted to evaluate crossover on trading day 20 (index 19) for a 5/20 MA cross. | On day 19, the 20-day MA is undefined (`None`). Without a prior defined relative position on day 19, it is impossible to determine whether day 20 crossed from the other side. | Updated engine so day $L$ strictly records the baseline difference ($\text{MA}_{short} - \text{MA}_{long}$), and crossover evaluation begins on day $L+1$. |
| **2. Continuous Lows vs Crossing Event** | Checked `curr_close < level` each day without tracking prior state. | If price remained below 1500 for multiple days, an alert fired every single day. The brief requires firing only on the *first day* it crosses. | Implemented state-transition verification: fires only when $P_{t-1} > L$ and $P_t < L$. |
| **3. Binary Float Inaccuracy** | Used native Python `float(row['close'])`. | In binary floating-point, values like `0.1 + 0.2` or thresholds like `1500.00` suffer representation drift, causing spurious cross triggers. | Switched all financial arithmetic to `decimal.Decimal`. |

---

## 5. Presentation Cheat-Sheet (6-Minute Walkthrough)

- **Minutes 0:00–1:30 (Overview & Demo)**: Run `python alerts.py data/extended_prices.csv data/sample_rules.json`. Show that it outputs both brief examples cleanly with zero dependencies.
- **Minutes 1:30–3:00 (Architecture & Tests)**: Show `tests/` directory (31 tests in <1s). Explain how tests verify scrambled dates, duplicate entries, touches, and multi-cross cycles.
- **Minutes 3:00–4:30 (The AI Gotcha Deep-Dive)**: Explain the MA window boundary condition (Day 20 vs Day 21). Walk through why the AI's initial day-20 cross logic was mathematically flawed and how you corrected it.
- **Minutes 4:30–6:00 (Questions Readiness)**: Be prepared to run any arbitrary CSV/JSON file the evaluators provide.
