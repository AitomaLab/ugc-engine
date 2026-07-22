"""Audience research sources per industry (Slice 2).

G-Lang findings (measured 2026-07) shape this module:
- Reddit KEYWORD SEARCH failed relevance in both EN and ES → we scrape
  NAMED subreddits per industry instead. Only well-known, verified-real
  subreddits are listed; inventing subreddit names would yield silently
  empty scrapes.
- Google People-Also-Ask passed in both languages at ~$0.001/query → PAA is
  a first-class audience-question source, promoted from Slice 4.
- ES Reddit coverage is unproven → ES lists stay empty until a subreddit is
  verified by hand; ES audience questions come from locale-scoped PAA. Thin
  coverage must look thin (low-confidence, omitted from the brief) rather
  than padded.
"""
from __future__ import annotations

# industry_id -> lang -> verified subreddit names (no r/ prefix)
SUBREDDITS: dict[str, dict[str, list[str]]] = {
    "education-learning":   {"en": ["studytips", "GetStudying", "college"]},
    "food-beverage":        {"en": ["HealthyFood", "EatCheapAndHealthy", "snacks"]},
    "beauty-skincare":      {"en": ["SkincareAddiction", "30PlusSkinCare", "MakeupAddiction"]},
    "fitness-sports":       {"en": ["Fitness", "loseit", "homegym"]},
    "health-wellness":      {"en": ["selfimprovement", "Mindfulness", "sleep"]},
    "supplements-nutrition": {"en": ["Supplements", "nutrition"]},
    "hr-benefits":          {"en": ["humanresources", "AskHR", "recruiting"]},
    "b2b-saas":             {"en": ["SaaS", "startups", "smallbusiness"]},
    "software-apps":        {"en": ["productivity", "androidapps", "iosapps"]},
    "fashion-apparel":      {"en": ["femalefashionadvice", "malefashionadvice", "streetwear"]},
    "pets":                 {"en": ["dogs", "cats", "puppy101"]},
    "marketing-agency":     {"en": ["marketing", "socialmedia", "DigitalMarketing"]},
    "finance-fintech":      {"en": ["personalfinance", "CreditCards"]},
    "travel-hospitality":   {"en": ["travel", "solotravel"]},
    "home-living":          {"en": ["InteriorDesign", "CleaningTips", "HomeDecorating"]},
    "baby-kids":            {"en": ["Parenting", "NewParents", "beyondthebump"]},
    "consumer-electronics": {"en": ["gadgets", "BuyItForLife", "headphones"]},
    "gaming":               {"en": ["pcgaming", "GameDeals"]},
    "jewelry-accessories":  {"en": ["jewelry", "Watches"]},
    "coaching-consulting":  {"en": ["getdisciplined", "Entrepreneur"]},
}

# static PAA seed queries per industry per language (locale-scoped at call time)
_PAA_STATIC: dict[str, dict[str, list[str]]] = {
    "education-learning": {
        "en": ["how to study effectively for exams"],
        "es": ["cómo estudiar mejor para un examen"],
    },
    "food-beverage": {
        "en": ["healthy soda alternatives"],
        "es": ["alternativas saludables a los refrescos"],
    },
    "hr-benefits": {
        "en": ["best employee wellness benefits"],
        "es": ["mejores beneficios para empleados"],
    },
}

# templates filled with the brand's own product categories (source-derived,
# never invented)
_PAA_TEMPLATES = {
    "en": ["best {cat}", "is {cat} worth it"],
    "es": ["mejor {cat}", "vale la pena {cat}"],
}

_PAA_LOCALES = {"en": ("us", "en"), "es": ("es", "es")}


def subreddits_for(industry: str | None, lang: str) -> list[str]:
    if not industry:
        return []
    return (SUBREDDITS.get(industry) or {}).get(lang, [])


def paa_queries_for(strategy: dict, lang: str, limit: int = 3) -> list[str]:
    """Locale-appropriate PAA queries: industry seed + product-derived."""
    industry = strategy.get("industry")
    out = list((_PAA_STATIC.get(industry or "") or {}).get(lang, []))
    cats = [c for c in (strategy.get("product_categories") or []) if isinstance(c, str)]
    for tpl in _PAA_TEMPLATES.get(lang, []):
        for cat in cats[:1]:
            out.append(tpl.format(cat=cat.lower()))
    # dedupe, cap
    seen, final = set(), []
    for q in out:
        if q not in seen:
            seen.add(q)
            final.append(q)
        if len(final) >= limit:
            break
    return final


def paa_locale(lang: str) -> tuple[str, str]:
    return _PAA_LOCALES.get(lang, ("us", "en"))
