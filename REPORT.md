# Insulin Dosing Calculation Comparison Report

> **Date:** 2026-06-06  
> **Reference implementation:** [openaps/oref0](https://github.com/openaps/oref0) (OpenAPS reference design)

---

## 1. Background — How OpenAPS Structures Its Dosing Logic

The OpenAPS project (Open Artificial Pancreas System) implements a **closed-loop insulin delivery** algorithm. Its core repository, **oref0**, organizes dosing logic into three layers that mirror the classic **monitor → predict → control** paradigm:

| Layer | oref0 Module | Purpose |
|-------|-------------|---------|
| **Profile** | `lib/profile/` | Loads patient-specific settings: ICR (insulin-to-carb ratio), ISF (insulin sensitivity factor), basal rates, DIA (duration of insulin action), BG targets, and safety caps (`max_iob`, `maxCOB`, autosens bounds). |
| **IOB / Bolus** | `lib/iob/`, `lib/bolus.js` | Tracks insulin-on-board from prior boluses (curved decay over DIA) and classifies pump history events (BolusWizard records expose `food_estimate`, `correction_estimate`, `bolus_estimate`). |
| **Determine-Basal** | `lib/determine-basal/determine-basal.js` | The central decision engine (~1 200 lines). Computes eventual BG predictions, then decides whether to set a **temp basal rate** or deliver a **Super Micro Bolus (SMB)**. It combines meal bolus logic, correction logic, IOB adjustments, and multiple safety checks. |

### Key design principles observed in oref0

1. **Separation of food vs. correction components.** The `BolusWizard` record explicitly stores `food_estimate` (carb bolus) and `correction_estimate` (ISF-based correction) separately, then sums them into `bolus_estimate`.
2. **IOB-aware adjustments.** Before recommending any new insulin, oref0 subtracts active IOB from the calculated requirement, preventing stacking.
3. **Safety caps everywhere.** `max_iob`, `maxCOB` (120 g), autosens limits (0.7–1.2), and `min_5m_carbimpact` bound every calculation.
4. **Dynamic sensitivity.** The `autosens` module can adjust both ISF and targets based on recent deviation data, something static formulas cannot do.

---

## 2. The Three Standard Calculation Methods

### 2.1 Carb-Ratio Bolus

$$\text{Bolus} = \frac{\text{Carbohydrates (g)}}{\text{ICR (g/U)}}$$

Covers **meal insulin only**. Ignores current blood glucose entirely.

### 2.2 Correction Bolus (ISF-Based)

$$\text{Bolus} = \max\!\left(0,\;\frac{\text{BG} - \text{Target BG}}{\text{ISF (mg/dL/U)}}\right)$$

Covers **BG correction only**. Ignores meal carbs entirely. Returns zero when BG is at or below target.

### 2.3 Combined Bolus (Meal + Correction)

$$\text{Bolus} = \frac{\text{Carbs}}{\text{ICR}} + \max\!\left(0,\;\frac{\text{BG} - \text{Target}}{\text{ISF}}\right)$$

This is the **standard meal-time approach** used in most pump bolus wizards (including the Medtronic BolusWizard that OpenAPS parses). It addresses both food and hyperglycemia simultaneously.

---

## 3. Test Results Across Five Patient Scenarios

| Scenario | Carbs (g) | ICR | BG (mg/dL) | Target | ISF | Carb Bolus (U) | Correction (U) | **Combined (U)** |
|----------|----------:|----:|-----------:|-------:|----:|---------------:|---------------:|-----------------:|
| A – Normal BG, Small Meal | 30 | 10 | 110 | 100 | 50 | 3.00 | 0.20 | **3.20** |
| B – High BG, Large Meal | 90 | 8 | 250 | 100 | 40 | 11.25 | 3.75 | **15.00** |
| C – Low BG, Medium Meal | 45 | 12 | 75 | 100 | 60 | 3.75 | 0.00 | **3.75** |
| D – Very High BG, No Meal | 0 | 10 | 300 | 100 | 30 | 0.00 | 6.67 | **6.67** |
| E – Normal BG, Very Large Meal | 120 | 8 | 105 | 100 | 45 | 15.00 | 0.11 | **15.11** |

### Summary Statistics

| Method | Min (U) | Max (U) | Mean (U) |
|--------|--------:|--------:|---------:|
| Carb-Ratio Bolus | 0.00 | 15.00 | 6.60 |
| Correction Bolus | 0.00 | 6.67 | 2.15 |
| Combined Bolus | 3.20 | 15.11 | 8.75 |

---

## 4. Key Differences and Practical Implications

### 4.1 When each method is appropriate

| Method | Best used when | Risk if used alone |
|--------|---------------|-------------------|
| **Carb-Ratio only** | BG is already at target and a meal is starting | Misses hyperglycemia → prolonged high BG |
| **Correction only** | BG is high with no food intake | Misses meal coverage → postprandial spike |
| **Combined** | Meal-time when BG may not be at target | Over-correction if IOB is not accounted for |

### 4.2 Critical observations from the scenarios

- **Scenario B (High BG + Large Meal):** The correction component adds 3.75 U on top of the 11.25 U carb bolus — a 33% increase. Using a carb-only bolus here would leave significant hyperglycemia unaddressed.
- **Scenario C (Low BG + Medium Meal):** The correction formula returns 0 U (BG < target), so the combined bolus equals the carb bolus. This is correct behavior — adding correction insulin when BG is already low would be dangerous.
- **Scenario D (Very High BG, No Meal):** The carb bolus is 0 U; the entire dose comes from correction. A carb-only approach would deliver nothing, which is clearly inappropriate.
- **Scenario A & E (Near-target BG):** The correction component is negligible (0.20 U and 0.11 U respectively), so combined ≈ carb-only. The correction term acts as a fine-tuning adjustment.

### 4.3 What OpenAPS adds beyond these static formulas

The three methods above are **open-loop, static calculations**. OpenAPS extends them with:

| Feature | Static Formulas | OpenAPS (oref0) |
|---------|----------------|-----------------|
| IOB subtraction | ❌ Not included | ✅ Deducts active insulin before dosing |
| Dynamic ISF/ICR | ❌ Fixed values | ✅ Autosens adjusts based on recent deviations |
| BG prediction | ❌ Snapshot only | ✅ Projects eventualBG using BGI + trend |
| Safety caps | ❌ None | ✅ `max_iob`, `maxCOB`, autosens bounds |
| Micro-bolusing | ❌ Full bolus at once | ✅ SMB delivers small increments every 5 min |
| Unannounced meals | ❌ Not handled | ✅ UAM module detects and responds |

---

## 5. Conclusion

- The **carb-ratio bolus** and **correction bolus** each address only one dimension of insulin need (food or hyperglycemia). Used alone, they are incomplete.
- The **combined bolus** is the practical minimum for safe meal-time dosing, which is why every commercial pump wizard implements it.
- However, even the combined formula is a **static, IOB-blind** calculation. OpenAPS demonstrates that a production-grade system must layer on IOB tracking, dynamic sensitivity, BG prediction, and hard safety limits to operate safely in a closed loop.

---

*Companion script: `insulin_dosing_calculations.py`*
