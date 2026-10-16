"""Body measurement estimation from pose/silhouette ratios + height (scale) + weight (volume)."""
import math
from typing import Optional

# Typical torso depth/width ratios (front-view width -> ellipse depth).
_DEPTH = {
    "female": {"chest": 0.70, "waist": 0.74, "hips": 0.76},
    "male": {"chest": 0.68, "waist": 0.78, "hips": 0.74},
}

# Standard size bounds (upper limits, cm): chest, waist, hips.
_BASE = {
    "female": [("XS", 84, 66, 92), ("S", 88, 70, 96), ("M", 94, 76, 102), ("L", 100, 82, 108), ("XL", 106, 88, 114), ("XXL", 112, 94, 120)],
    "male": [("XS", 88, 74, 90), ("S", 94, 80, 96), ("M", 100, 86, 102), ("L", 106, 92, 108), ("XL", 112, 98, 114), ("XXL", 118, 104, 120)],
}
# Brand offset in cm on the standard bounds (negative = brand runs small).
BRANDS = {"Zara": -2, "H&M": 0, "Mango": -1, "Nike": 1, "Adidas": 1, "Uniqlo": -2}


def _ellipse(width: float, depth: float) -> float:
    a, b = width / 2, depth / 2
    h = ((a - b) ** 2) / ((a + b) ** 2)
    return math.pi * (a + b) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h)))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _regression(height_cm: float, bmi: float, g: str) -> dict:
    return {
        "chest": height_cm * (0.50 if g == "female" else 0.53) * (bmi / 22) ** 0.45,
        "waist": height_cm * (0.40 if g == "female" else 0.45) * (bmi / 22) ** 0.75,
        "hips": height_cm * (0.56 if g == "female" else 0.53) * (bmi / 22) ** 0.45,
    }


def estimate_from_height_weight(height_cm: float, weight_kg: float, gender: str) -> dict:
    """No photo, no tape: population estimate from height (scale), weight (BMI) and sex."""
    g = "male" if gender == "male" else "female"
    bmi = weight_kg / ((height_cm / 100) ** 2)
    reg = _regression(height_cm, bmi, g)
    return {
        "chest_cm": round(_clamp(reg["chest"], 65, 160)),
        "waist_cm": round(_clamp(reg["waist"], 50, 160)),
        "hips_cm": round(_clamp(reg["hips"], 70, 170)),
        "shoulder_cm": round(_clamp(height_cm * (0.235 if g == "female" else 0.255) * (bmi / 22) ** 0.15, 30, 60)),
        "inseam_cm": round(_clamp(height_cm * (0.45 if g == "female" else 0.46), 55, 100)),
    }


def estimate(features: dict, height_cm: float, weight_kg: Optional[float], gender: str) -> dict:
    if gender not in ("male", "female"):
        # Sex unknown: average of both models.
        a, b = estimate(features, height_cm, weight_kg, "female"), estimate(features, height_cm, weight_kg, "male")
        return {k: round((a[k] + b[k]) / 2) for k in a}
    g = gender
    bmi = weight_kg / ((height_cm / 100) ** 2) if weight_kg else None
    adj = _clamp(((bmi or 22) - 22) * 0.012, -0.08, 0.15)

    widths = {k: features[f"{k}_r"] * height_cm for k in ("chest", "waist", "hips")}
    photo = {k: _ellipse(w, w * (_DEPTH[g][k] + adj)) for k, w in widths.items()}

    out = dict(photo)
    if bmi:
        # Population regression on BMI/height, blended with the photo estimate.
        reg = _regression(height_cm, bmi, g)
        out = {k: 0.65 * photo[k] + 0.35 * reg[k] for k in photo}

    res = {
        "chest_cm": round(_clamp(out["chest"], 65, 160)),
        "waist_cm": round(_clamp(out["waist"], 50, 160)),
        "hips_cm": round(_clamp(out["hips"], 70, 170)),
        "shoulder_cm": round(_clamp(features["shoulder_r"] * height_cm * 1.22, 30, 60)),
        "inseam_cm": round(_clamp(features["inseam_r"] * height_cm, 55, 100)),
    }
    return res


def _size_for(bounds: list, value: float, idx: int, offset: int) -> str:
    for row in bounds:
        if value <= row[idx] + offset:
            return row[0]
    return bounds[-1][0]


def brand_sizes(m: dict, gender: str) -> list:
    g = "female" if gender == "female" else "male"  # unknown sex -> unisex sizing follows men's tables
    order = [r[0] for r in _BASE[g]]
    out = []
    for brand, off in BRANDS.items():
        top = _size_for(_BASE[g], m["chest_cm"], 1, off)
        bottom = max(_size_for(_BASE[g], m["waist_cm"], 2, off), _size_for(_BASE[g], m["hips_cm"], 3, off), key=order.index)
        out.append({"brand": brand, "top": top, "bottom": bottom})
    return out
