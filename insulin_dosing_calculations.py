"""
Standard Insulin Dosing Calculations
=====================================
Implements three bolus calculation methods tested across patient scenarios:
  1. Carb-Ratio Bolus
  2. Correction Bolus (ISF-based)
  3. Combined Bolus (carb-ratio + correction)
"""

import json


def carb_ratio_bolus(carbs_g, icr):
    """Bolus for food only: carbs ÷ insulin-to-carb ratio (ICR)."""
    return carbs_g / icr


def correction_bolus(bg_mgdl, target_bg, isf):
    """Bolus to correct high BG: (BG − target) ÷ insulin sensitivity factor (ISF).
    Returns 0 when BG is at or below target."""
    return max(0, (bg_mgdl - target_bg) / isf)


def combined_bolus(carbs_g, icr, bg_mgdl, target_bg, isf):
    """Carb bolus + correction bolus — the standard meal-time approach."""
    return carb_ratio_bolus(carbs_g, icr) + correction_bolus(bg_mgdl, target_bg, isf)


# ─────────────────────────────────────────────
# Patient Scenarios
# ─────────────────────────────────────────────
scenarios = [
    {"label": "A – Normal BG, Small Meal",
     "carbs": 30, "icr": 10, "bg": 110, "target": 100, "isf": 50},
    {"label": "B – High BG, Large Meal",
     "carbs": 90, "icr": 8,  "bg": 250, "target": 100, "isf": 40},
    {"label": "C – Low BG, Medium Meal",
     "carbs": 45, "icr": 12, "bg": 75,  "target": 100, "isf": 60},
    {"label": "D – Very High BG, No Meal (correction only)",
     "carbs": 0,  "icr": 10, "bg": 300, "target": 100, "isf": 30},
    {"label": "E – Normal BG, Very Large Meal",
     "carbs": 120, "icr": 8, "bg": 105, "target": 100, "isf": 45},
]


if __name__ == "__main__":
    header = f"{'Scenario':<40} {'Carb Bolus':>10} {'Corr Bolus':>10} {'Combined':>10}"
    print(header)
    print("─" * len(header))

    results = []
    for s in scenarios:
        cb = carb_ratio_bolus(s["carbs"], s["icr"])
        cr = correction_bolus(s["bg"], s["target"], s["isf"])
        co = combined_bolus(s["carbs"], s["icr"], s["bg"], s["target"], s["isf"])
        results.append({**s, "carb_bolus": cb, "corr_bolus": cr, "combined": co})
        print(f"{s['label']:<40} {cb:>10.2f} U {cr:>10.2f} U {co:>10.2f} U")

    print()
    print("Summary statistics:")
    for name, key in [("Carb Bolus", "carb_bolus"), ("Correction Bolus", "corr_bolus"), ("Combined Bolus", "combined")]:
        vals = [r[key] for r in results]
        print(f"  {name:<20}  min={min(vals):.2f} U   max={max(vals):.2f} U   mean={sum(vals)/len(vals):.2f} U")
