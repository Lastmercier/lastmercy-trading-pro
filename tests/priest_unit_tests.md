# Priest (Fact Auditor) Unit Test Cases

Priest must pass ALL cases below before every release.
Run by pasting each DATA BLOCK + CLAIM into a Priest session and verifying the EXPECTED RESULT.

---

## TC-01 — ATR% correct, Priest must NOT flag correction

**Context:** BTC at ~$60,049, ATR(14) = 2,056.74

**DATA BLOCK (feed to Priest):**
```
Price 60049 | ATR 2056.74 | ATR% (pre-computed) = 3.42%
```

**CLAIM from analyst:**
> "ATR(14) = $2,056.74, representing approximately 3.4% of current price"

**Working:**
```
[recompute: 2,056.74 / 60,049 = 0.03424 = 3.42%]
Rounded to 1dp = 3.4% ✓
```

**EXPECTED RESULT:** `verified ✓, no correction needed`

**FAIL if Priest writes:** `[CORRECTION: 3.42% → 0.34%]` or `[CORRECTION: 3.4% → 0.34%]`
— This is a decimal-shift error by Priest (0.34% = 3.42% × 0.1)

---

## TC-02 — RSI rounding, minor not an error

**DATA BLOCK:**
```
RSI(14) = 37.23
```

**CLAIM from analyst:**
> "RSI = 37.3 (approaching oversold)"

**Working:**
```
[recompute: RSI reported = 37.23, rounded to 1dp = 37.2 or 37.3 depending on rounding convention]
Difference < 0.1 = within normal rounding.
"approaching oversold" is correct per Wilder thresholds (30–40 zone).
```

**EXPECTED RESULT:** `verified ✓` — rounding to 37.3 is acceptable; "approaching oversold" label is CORRECT

**FAIL if Priest writes:** `[CORRECTION: RSI 37.3 → oversold]` (RSI 37 is NOT oversold — threshold is <30)
**FAIL if Priest writes:** `[CORRECTION: 37.3 → 37.2]` (sub-0.1 rounding differences are not errors)

---

## TC-03 — VaR arithmetic, Priest must verify correctly

**DATA BLOCK:**
```
ATR 4113.49 | z-score (95%) = 2.326
```

**CLAIM from analyst:**
> "1-day 95% VaR ≈ $9,568"

**Working:**
```
[recompute: 2.326 × 4,113.49 = 9,568.20]
Rounds to $9,568 ✓
```

**EXPECTED RESULT:** `verified ✓, no correction needed`

**FAIL if Priest writes:** `[CORRECTION: 9,568 → 956.8]` (decimal shift — Priest's error, not analyst's)
**FAIL if Priest writes:** `[CORRECTION: 9,568 → 95,682]` (same logic, opposite direction)

---

## TC-04 — Decimal-shift trap (Priest must STOP and re-verify)

**DATA BLOCK:**
```
Price 100 | Metric 3.50%
```

**CLAIM from analyst:**
> "Metric = 3.50%"

**Scenario:** Priest internally computes 0.350% and plans to flag `[CORRECTION: 3.50% → 0.35%]`

**Expected behaviour (RULE B):**
Priest detects: 0.35% = 3.50% × 0.1 → classic decimal-shift signature → STOP, re-verify
After re-verify: 3.50% is correct → write `verified ✓, no correction needed`

**FAIL if Priest writes:** `[CORRECTION: 3.50% → 0.35%]` without showing recompute working

---

## TC-05 — Genuine error Priest SHOULD catch

**DATA BLOCK:**
```
Price 60049 | 52W High 69000 | 52W Low 38500
```

**CLAIM from analyst:**
> "50% Fibonacci retracement = 42,000"

**Working:**
```
[recompute: 69,000 − (69,000 − 38,500) × 0.5 = 69,000 − 15,250 = 53,750]
Stated: 42,000 ≠ actual: 53,750
```

**EXPECTED RESULT:** `[CORRECTION: stated 50% Fib = 42,000 → actual 53,750]`
This is a REAL error and Priest should catch it.

---

## Decimal-Shift Detection Rule (summary)

| Stated | "Corrected to" | Ratio | Action |
|--------|----------------|-------|--------|
| 3.42%  | 0.342%         | ×0.1  | STOP — Priest's decimal error |
| 0.342% | 3.42%          | ×10   | STOP — Priest's decimal error |
| 9,568  | 956.8          | ×0.1  | STOP — Priest's decimal error |
| 9,568  | 95,680         | ×10   | STOP — Priest's decimal error |
| 42,000 | 53,750         | N/A   | Valid correction — proceed    |

---

## Release Checklist

Before each deployment, run TC-01 through TC-05 manually with a live BTC or equity analysis.
All five must pass. TC-01 is the regression test for the confirmed bug (2026-06-27).
