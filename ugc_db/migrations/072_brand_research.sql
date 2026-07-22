-- Brand research store (Slice 2) — normalized market-intelligence records.
--
-- The data-integrity contract is enforced structurally here, not by prompts:
--   * Two record kinds. An OBSERVATION is a scraped fact and MUST carry
--     provenance (source_url + scraped_at) — enforced by CHECK, so an
--     unsourced row cannot exist, and the UI rule "no provenance, no
--     display" holds by construction.
--   * An INTERPRETATION is a model claim and MUST reference the observation
--     rows it derives from (refs). DB floor is >=1; application code
--     enforces the real support threshold (see research code, N=3).
--   * subject is the CANONICAL normalized key (lowercased, collapsed) —
--     this is what makes the cross-brand overlap instrument a GROUP BY
--     (industry, insight_type, subject) instead of a research project.
--
-- Per-user RLS for reads; writes go through the service-role client only.
-- The shared "industry commons" table does NOT exist yet by design — Slice 5
-- is parked until >=5 brands share an industry; this table quietly
-- accumulates the overlap evidence that would justify it.

-- Audience research output for the brief composer + persona viewer. Written
-- server-side only — deliberately NOT inside brand_state, which the Brand
-- Studio client round-trips wholesale on save (anything injected there
-- would be wiped by the next client save).
ALTER TABLE public.brand_profiles ADD COLUMN IF NOT EXISTS audience jsonb;

CREATE TABLE IF NOT EXISTS public.brand_research (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    kind        text NOT NULL CHECK (kind IN ('observation', 'interpretation')),
    insight_type text NOT NULL,   -- audience_phrase | audience_question | audience_pain | persona | hook_pattern | hashtag | ...
    subject     text NOT NULL,    -- canonical normalized subject (overlap key)
    language    text,             -- ISO 639-1 of the verbatim content
    industry    text,             -- taxonomy id at time of research
    source      text,             -- reddit | google_paa | brightdata | vision | ...
    source_url  text,
    scraped_at  timestamptz,
    dataset_id  text,             -- scraper run/dataset id for auditability
    payload     jsonb NOT NULL DEFAULT '{}'::jsonb,  -- verbatim text + metrics, never re-typed
    refs        jsonb NOT NULL DEFAULT '[]'::jsonb,  -- observation ids backing an interpretation
    created_at  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT observation_provenance CHECK (
        kind <> 'observation' OR (source_url IS NOT NULL AND scraped_at IS NOT NULL)
    ),
    CONSTRAINT interpretation_support CHECK (
        kind <> 'interpretation' OR jsonb_array_length(refs) >= 1
    )
);

CREATE INDEX IF NOT EXISTS brand_research_user_type
    ON public.brand_research(user_id, insight_type, created_at DESC);

-- the overlap instrument: GROUP BY (industry, insight_type, subject)
CREATE INDEX IF NOT EXISTS brand_research_overlap
    ON public.brand_research(industry, insight_type, subject);

ALTER TABLE public.brand_research ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS brand_research_owner_select ON public.brand_research;
CREATE POLICY brand_research_owner_select ON public.brand_research
    FOR SELECT USING (auth.uid() = user_id);

COMMENT ON TABLE public.brand_research IS 'Normalized market-intelligence records per user. Observations carry mandatory provenance; interpretations carry mandatory observation refs. Writes are service-role only.';
COMMENT ON COLUMN public.brand_research.subject IS 'Canonical normalized key — the cross-brand overlap instrument groups on (industry, insight_type, subject).';
