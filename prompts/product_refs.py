"""Shared helpers for product shot URLs and per-view visual descriptions."""

IMAGE_FIRST_PRODUCT_DESC = (
    "product exactly as shown in reference image 2; reproduce open/closed state, "
    "cap, colors, and proportions precisely; do not add or remove packaging elements"
)


def resolve_product_visual_description(
    product: dict | None,
    image_url: str | None = None,
    *,
    hero_image_url: str | None = None,
) -> str:
    """Return visual description text for a specific product shot URL."""
    if not product:
        return "the product"

    url = image_url or product.get("image_url") or ""
    hero_url = hero_image_url or product.get("_db_hero_image_url") or product.get("image_url") or ""
    shot_map = product.get("product_view_descriptions") or {}

    if url and url in shot_map:
        entry = shot_map[url]
        if isinstance(entry, dict):
            return entry.get("visual_description") or product.get("name") or "the product"
        return str(entry)

    if url and hero_url and url != hero_url:
        print(
            f"[product_refs] No per-shot description for {url[:80]}... "
            f"(hero={hero_url[:80]}...); using image-first prompt line"
        )
        return IMAGE_FIRST_PRODUCT_DESC

    vd = product.get("visual_description") or {}
    if isinstance(vd, str):
        return vd or product.get("name", "the product")
    return vd.get("visual_description", product.get("name", "the product"))
