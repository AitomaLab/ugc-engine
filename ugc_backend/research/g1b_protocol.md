# G1b — blind hook A/B (pre-registered protocol)

Written BEFORE any hooks are generated. Kill-only: this gate can stop the
brand-brief feature, it can never approve it (the judge wants the feature to
work; authorization came from the external G0 study).

## Setup

- Brand: the reference account's scraped brand (Poppi, food-beverage).
- 10 fixed hook prompts (below), written before generation.
- Condition A (control): model writes a short-form video hook from the prompt
  plus ONLY the brand name.
- Condition B (brief): identical call plus the current `/memories/brand_brief.md`
  content (which includes audience vocabulary from Slice 2 research).
- Same model, temperature, and max tokens for both conditions.
- Order within each pair randomized by coin flip; labels stripped; the judge
  sees "Hook 1 / Hook 2" per prompt and picks the better one (or "tie").
- The A/B mapping is stored in a file the judge does not open until all 10
  picks are recorded.

## Rubric (what "better" means — judge reads this before judging)

A better hook: (1) sounds like something this brand would actually say,
(2) speaks to a real pain or desire of this audience in their own words,
(3) would stop the scroll in the first 2 seconds. Ignore grammar polish and
length differences.

## Pass/fail (pre-registered)

- Count pairs where the WITH-BRIEF hook wins (ties excluded).
- **FAIL (kill): with-brief wins 3 or fewer of the non-tie pairs AND at
  least 6 pairs are non-tie.** Then: report which brief tier was thin
  (identity / audience / performance) so the right thing is fixed or killed.
- Any other outcome: no kill. The gate does NOT authorize anything either way.

## The 10 prompts (fixed)

1. A hook for a video introducing the brand to someone who has never heard of it.
2. A hook for a video answering the audience's most common doubt about this product category.
3. A hook for a video about an everyday moment where the product fits naturally.
4. A hook for a comparison against the "default" alternative people currently use.
5. A hook for a video aimed at someone who tried something similar and was disappointed.
6. A hook for a launch announcement of a new flavor/variant.
7. A hook for a video debunking a misconception in this category.
8. A hook for a "day in the life" style video featuring the product.
9. A hook for a video targeting the health-conscious segment of the audience.
10. A hook for a video that leans on social proof.
