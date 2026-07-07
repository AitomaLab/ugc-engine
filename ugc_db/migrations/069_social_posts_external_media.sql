-- 069_social_posts_external_media.sql
-- Allow scheduling Brand Studio / external URL images and carousels
-- (no video_job_id or product_shot_id FK).

ALTER TABLE public.social_posts
    DROP CONSTRAINT IF EXISTS chk_social_posts_media_source;

ALTER TABLE public.social_posts
    DROP CONSTRAINT IF EXISTS social_posts_media_kind_check;

ALTER TABLE public.social_posts
    ADD COLUMN IF NOT EXISTS media_urls JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE public.social_posts
    ADD CONSTRAINT social_posts_media_kind_check CHECK (
        media_kind IN ('video', 'image', 'carousel')
    );

ALTER TABLE public.social_posts
    ADD CONSTRAINT chk_social_posts_media_source CHECK (
        (
            media_kind = 'video'
            AND video_job_id IS NOT NULL
            AND product_shot_id IS NULL
            AND (media_urls IS NULL OR media_urls = '[]'::jsonb)
        )
        OR (
            media_kind = 'image'
            AND product_shot_id IS NOT NULL
            AND video_job_id IS NULL
            AND (media_urls IS NULL OR media_urls = '[]'::jsonb)
        )
        OR (
            media_kind IN ('image', 'carousel')
            AND video_job_id IS NULL
            AND product_shot_id IS NULL
            AND media_urls IS NOT NULL
            AND jsonb_typeof(media_urls) = 'array'
            AND jsonb_array_length(media_urls) > 0
        )
    );

CREATE INDEX IF NOT EXISTS idx_social_posts_media_urls ON public.social_posts USING gin (media_urls);
