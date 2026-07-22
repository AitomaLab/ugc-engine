-- Hook-type on video breakdowns (Slice 2.5) — closes the self-improvement loop.
--
-- Each analyzed post's opening hook gets classified into the same fixed
-- 6-type enum used by the G0 study and the suggestion engine (question /
-- claim / pattern-interrupt / demo / stat / pov). The nightly reflection
-- loop then sees hook_type alongside engagement per post, so "X hooks work
-- on THIS account" can graduate from hypothesis to confirmed rule in
-- creative_guidelines.md — which feeds the brand brief — which feeds the
-- next round of suggestions. Per-user, additive, no creation-pipeline
-- changes.
--
-- Code tolerates this column being absent (optional-column strip in
-- update_breakdown), so ordering of deploy vs migration doesn't matter.

ALTER TABLE public.analytics_video_breakdowns
    ADD COLUMN IF NOT EXISTS hook_type text
    CHECK (hook_type IS NULL OR hook_type IN
        ('question', 'claim', 'pattern-interrupt', 'demo', 'stat', 'pov'));

COMMENT ON COLUMN public.analytics_video_breakdowns.hook_type IS 'Classified opening-hook style (fixed 6-type enum). Model-assigned label; feeds the per-user reflection loop as a grouping input, never as a metric.';
