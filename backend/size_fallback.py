"""Size fallback when a brand has no readable size chart: saved tape measures vs the international average table."""
import json
import os
import re
from typing import Optional

with open(os.path.join(os.path.dirname(__file__), "data", "size_standard_media_internazionale.json"), encoding="utf-8") as f:
    TABLE = json.load(f)

MAX_CONF = 93
_FIELD = {"petto": "chest_cm", "vita": "waist_cm", "fianchi": "hips_cm"}
_LABEL = {"petto": "torace", "vita": "vita", "fianchi": "fianchi"}
_SIZES = ["S", "M", "L", "XL", "XXL"]
_TYPICAL_HEIGHT = {"uomo": (165, 190), "donna": (155, 178)}
_KIND_LABEL = {"t-shirt": "T-shirt", "felpa": "Felpa", "giacca": "Giacca", "abito": "Abito", "pantaloni": "Pantaloni", "cargo": "Cargo pants", "sneakers": "Sneakers"}


def garment_kind(category: Optional[str], text: str = "") -> str:
    t, cat = (text or "").lower(), (category or "").lower()
    if cat == "shoes" or re.search(r"scarp|shoe|sneaker|boot|stival|sandal", t):
        return "sneakers"
    if cat == "bottom" or re.search(r"pantalon|trouser|jean|pant|short|gonna|skirt|legging", t):
        return "cargo" if "cargo" in t else "pantaloni"
    if cat == "dress" or re.search(r"abito|vestito|dress", t):
        return "abito"
    if cat == "outerwear" or re.search(r"giacc|jacket|cappott|coat|blazer|trench", t):
        return "giacca"
    return "felpa" if re.search(r"felpa|hoodie|sweatshirt|sweater|maglion", t) else "t-shirt"


def _measure_conf(v: float, lo: float, hi: float) -> int:
    if v < lo:
        return 88  # roomier on this body part: the size is set by a larger measure
    if v <= hi:
        margin = min(v - lo, hi - v) / max(1.0, hi - lo)
        return MAX_CONF if margin >= 0.15 else (90 if margin >= 0.07 else 88)
    return max(70, int(86 - 3 * (v - hi)))


def _shoes(m: dict) -> dict:
    foot = float(m["foot_cm"])
    table = TABLE["sneakers"]["piede_cm_max_per_eu"]
    eu = next((k for k, mx in table.items() if foot <= mx), list(table)[-1])
    gap = table[eu] - foot
    conf = MAX_CONF if 0.15 <= gap <= 0.55 else 89
    if foot > list(table.values())[-1]:
        conf = 80
    return {"size": f"{eu} EU", "confidence": conf, "details": f"piede {foot:g} cm"}


def recommend(m: dict, kind: str) -> dict:
    if kind == "sneakers":
        r = _shoes(m)
    else:
        sex = "donna" if m.get("gender") == "female" else "uomo"
        table, weights = TABLE[sex], TABLE["capi"][kind]["misure"]
        vals = {k: float(m[_FIELD[k]]) for k in weights if m.get(_FIELD[k])}

        # Each measure picks its own size; the garment must fit the largest body part.
        own = {k: min(_SIZES, key=lambda s, k=k, v=v: max(0.0, table[s][k][0] - v, v - table[s][k][1])) for k, v in vals.items()}
        size = max(own.values(), key=_SIZES.index)
        per = {k: _measure_conf(v, *table[size][k]) for k, v in vals.items()}
        conf = round(sum(weights[k] * c for k, c in per.items()) / sum(weights[k] for k in per))
        if any(c < MAX_CONF for c in per.values()):
            conf = min(conf, 90)  # a measure at the edge of the range: 88-90%, never full confidence
        if len(set(own.values())) > 1:
            conf = min(conf, 89)
        lo, hi = _TYPICAL_HEIGHT[sex]
        if m.get("height_cm") and not lo <= float(m["height_cm"]) <= hi:
            conf -= 2
        length = table[size]["lunghezza"].get(kind)
        details = ", ".join(f"{_LABEL[k]} {v:g} cm" for k, v in vals.items())
        if length:
            details += f" · lunghezza media {kind if kind != 'abito' else 'capo'} {length} cm"
        r = {"size": size, "confidence": conf, "details": details}
    r["confidence"] = max(70, min(MAX_CONF, r["confidence"]))
    r["explanation"] = (f"Taglia consigliata: {r['size']} - basata sulle tue misure salvate + media internazionale - "
                        f"Affidabilità {r['confidence']}%")
    r["kind"] = kind
    r["kind_label"] = _KIND_LABEL[kind]
    return r
