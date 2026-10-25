import os
from pathlib import Path
import stripe
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

CATALOG = [
    {"emergent_product_id": "atelier_extra", "name": "My Atelier · 1 prova extra", "tax_code": "txcd_10103001",
     "prices": [{"lookup_key": "atelier_extra_once", "amount": 99, "currency": "eur"}]},
    {"emergent_product_id": "atelier_single", "name": "My Atelier · Single 30 giorni", "tax_code": "txcd_10103001",
     "prices": [{"lookup_key": "atelier_single_30d", "amount": 299, "currency": "eur"}]},
    {"emergent_product_id": "atelier_family", "name": "My Atelier · Family 30 giorni", "tax_code": "txcd_10103001",
     "prices": [{"lookup_key": "atelier_family_30d", "amount": 499, "currency": "eur"}]},
]


def get_or_create_product(entry):
    for p in stripe.Product.list(active=True).auto_paging_iter():
        if p.to_dict().get("metadata", {}).get("emergent_product_id") == entry["emergent_product_id"]:
            return p
    return stripe.Product.create(name=entry["name"], tax_code=entry["tax_code"],
                                 metadata={"emergent_product_id": entry["emergent_product_id"]})


def ensure_catalog():
    for entry in CATALOG:
        product = get_or_create_product(entry)
        for p in entry["prices"]:
            existing = stripe.Price.list(lookup_keys=[p["lookup_key"]], active=True, limit=1).data
            if existing and (existing[0].unit_amount != p["amount"] or existing[0].currency != p["currency"] or existing[0].tax_behavior != "inclusive"):
                stripe.Price.modify(existing[0].id, active=False)
                existing = []
            if not existing:
                stripe.Price.create(product=product.id, unit_amount=p["amount"], currency=p["currency"],
                                    lookup_key=p["lookup_key"], transfer_lookup_key=True, tax_behavior="inclusive")
            print("ok", p["lookup_key"])


if __name__ == "__main__":
    ensure_catalog()
