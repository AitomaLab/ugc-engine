-- 037_social_posts_image_schedule.sql
-- Allow scheduling standalone images (product_shots), not only video_jobs.
--
-- Prior schema (012) REQUIRED video_job_id FK — the Schedule modal reuses asset
-- UUIDs but image assets are rows in product_shots, so bulk schedule never
-- inserted social_posts rows and the calendar stayed empty.

ALTER TABLE public.social_posts
    DROP CONSTRAINT IF EXISTS chk_social_posts_media_source;

ALTER TABLE public.social_posts
    ALTER COLUMN video_job_id DROP NOT NULL;

ALTER TABLE public.social_posts
    ADD COLUMN IF NOT EXISTS product_shot_id UUID REFERENCES public.product_shots(id) ON DELETE SET NULL;

ALTER TABLE public.social_posts
    ADD COLUMN IF NOT EXISTS media_kind TEXT NOT NULL DEFAULT 'video'
        CHECK (media_kind IN ('video', 'image'));

-- Exactly one FK must be populated (video XOR image).
ALTER TABLE public.social_posts
    ADD CONSTRAINT chk_social_posts_media_source CHECK (
        (media_kind = 'video' AND video_job_id IS NOT NULL AND product_shot_id IS NULL)
        OR (media_kind = 'image' AND product_shot_id IS NOT NULL AND video_job_id IS NULL)
    );

CREATE INDEX IF NOT EXISTS idx_social_posts_product_shot_id ON public.social_posts (product_shot_id);
