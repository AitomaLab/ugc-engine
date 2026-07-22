"""Versioned industry taxonomy — the routing key for brand intelligence.

Three mechanisms lean on this enum (market-intelligence bucketing, research
query selection, extraction confidence gating), so it is fixed in code and
versioned: re-bucketing silently re-routes brands that were already
classified, so any change that renames/merges/splits a bucket MUST bump
TAXONOMY_VERSION and map old ids forward in LEGACY_ALIASES.

The extractor is constrained to these ids — off-list answers are rejected,
which is what makes its confidence score mean anything.

Shared module: imported by ugc_backend AND services/creative-os (repo root is
on PYTHONPATH in both deployments — see railway.toml startCommands).
"""
from __future__ import annotations

TAXONOMY_VERSION = 1

# id -> (label, example cues for the classifier prompt)
INDUSTRIES: dict[str, tuple[str, str]] = {
    "beauty-skincare":      ("Beauty & Skincare", "cosmetics, makeup, skincare routines, haircare"),
    "fashion-apparel":      ("Fashion & Apparel", "clothing, footwear, streetwear, fashion accessories"),
    "jewelry-accessories":  ("Jewelry & Accessories", "jewelry, watches, bags, eyewear"),
    "health-wellness":      ("Health & Wellness", "mental health, sleep, mindfulness, self-care, habit apps"),
    "fitness-sports":       ("Fitness & Sports", "gyms, training programs, sportswear, equipment"),
    "supplements-nutrition":("Supplements & Nutrition", "vitamins, protein, greens powders, nootropics"),
    "food-beverage":        ("Food & Beverage", "snacks, drinks, coffee, restaurants, meal kits"),
    "home-living":          ("Home & Living", "furniture, decor, kitchenware, organization, cleaning"),
    "baby-kids":            ("Baby & Kids", "baby gear, toys, parenting products, kids clothing"),
    "pets":                 ("Pets", "pet food, pet accessories, grooming, vet services"),
    "consumer-electronics": ("Consumer Electronics", "gadgets, audio, smart home, phone accessories"),
    "software-apps":        ("Consumer Software & Apps", "B2C mobile/web apps, productivity tools, utilities"),
    "b2b-saas":             ("B2B SaaS", "business software, dev tools, APIs, enterprise platforms"),
    "education-learning":   ("Education & Learning", "courses, exam prep, tutoring, study tools, edtech"),
    "finance-fintech":      ("Finance & Fintech", "banking, investing, credit, insurance, crypto"),
    "travel-hospitality":   ("Travel & Hospitality", "hotels, tours, booking, travel gear"),
    "real-estate":          ("Real Estate", "agencies, proptech, property investment"),
    "automotive":           ("Automotive", "cars, detailing, parts, EV, rentals"),
    "entertainment-media":  ("Entertainment & Media", "streaming, podcasts, publishers, creators-as-brand"),
    "gaming":               ("Gaming", "games, gaming gear, esports"),
    "arts-crafts":          ("Arts & Crafts", "art supplies, handmade goods, hobby kits"),
    "professional-services":("Professional Services", "accounting, legal, IT services, contractors"),
    "marketing-agency":     ("Marketing & Creative Agencies", "ad agencies, content studios, social media management"),
    "hr-benefits":          ("HR & Employee Benefits", "employee wellness, benefits platforms, recruiting, HR tech"),
    "ecommerce-retail":     ("E-commerce & Retail (general)", "multi-category stores, marketplaces, retail brands"),
    "events-weddings":      ("Events & Weddings", "event planning, venues, wedding services, photography"),
    "sustainability-green": ("Sustainability & Green", "eco products, refillables, circular economy"),
    "coaching-consulting":  ("Coaching & Consulting", "business coaching, life coaching, courses by experts"),
    "healthcare-medical":   ("Healthcare & Medical", "clinics, telehealth, medical devices, dental"),
    "nonprofit":            ("Nonprofit & Causes", "charities, NGOs, community organizations"),
}

# old id -> current id; grows only when TAXONOMY_VERSION bumps
LEGACY_ALIASES: dict[str, str] = {}


def is_valid_industry(industry_id: str | None) -> bool:
    return bool(industry_id) and industry_id in INDUSTRIES


def normalize_industry(industry_id: str | None) -> str | None:
    """Resolve an id (or legacy alias) to a current id, else None."""
    if not industry_id:
        return None
    iid = industry_id.strip().lower()
    iid = LEGACY_ALIASES.get(iid, iid)
    return iid if iid in INDUSTRIES else None


def classifier_menu() -> str:
    """The exact allowed-values block for extraction prompts."""
    lines = [f'- "{iid}" — {label} (e.g. {cues})' for iid, (label, cues) in INDUSTRIES.items()]
    return "\n".join(lines)
