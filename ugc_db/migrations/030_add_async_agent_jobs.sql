-- Async agent module — fire-and-return job tracking.
-- Two additive tables that the new async_agent module owns end-to-end.
-- Existing video_jobs and product_shots are not touched.
-- Both tables are exposed via Supabase Realtime so the frontend can swap
-- chat-bubble placeholders to thumbnails on terminal status without polling.

CREATE TABLE IF NOT EXISTS public.async_video_jobs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id          uuid NOT NULL,
    agent_session_id    text,
    modal_job_id        text,
    tool_name           text NOT NULL,
    status              text NOT NULL DEFAULT 'dispatched'
                          CHECK (status IN ('dispatched','running','finishing','success','failed','cancelled')),
    params              jsonb NOT NULL DEFAULT '{}'::jsonb,
    artifact_url        text,
    error               text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS async_video_jobs_project_status_idx
    ON public.async_video_jobs(project_id, status);
CREATE INDEX IF NOT EXISTS async_video_jobs_user_created_idx
    ON public.async_video_jobs(user_id, created_at DESC);

ALTER TABLE public.async_video_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS async_video_jobs_owner_select ON public.async_video_jobs;
CREATE POLICY async_video_jobs_owner_select ON public.async_video_jobs
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS async_video_jobs_owner_insert ON public.async_video_jobs;
CREATE POLICY async_video_jobs_owner_insert ON public.async_video_jobs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS async_video_jobs_owner_update ON public.async_video_jobs;
CREATE POLICY async_video_jobs_owner_update ON public.async_video_jobs
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS async_video_jobs_owner_delete ON public.async_video_jobs;
CREATE POLICY async_video_jobs_owner_delete ON public.async_video_jobs
    FOR DELETE USING (auth.uid() = user_id);

COMMENT ON TABLE  public.async_video_jobs        IS 'Async agent module — fire-and-return video job tracking. Owned by services/creative-os/services/async_agent. Independent from video_jobs.';
COMMENT ON COLUMN public.async_video_jobs.tool_name IS 'create_ugc_video | create_clone_video | caption_video';
COMMENT ON COLUMN public.async_video_jobs.modal_job_id IS 'Modal worker job id for cancel/poll.';

CREATE TABLE IF NOT EXISTS public.async_image_jobs (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    project_id          uuid NOT NULL,
    agent_session_id    text,
    kie_task_id         text,
    prompt              text NOT NULL,
    status              text NOT NULL DEFAULT 'dispatched'
                          CHECK (status IN ('dispatched','running','finishing','success','failed','cancelled')),
    image_url           text,
    error               text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS async_image_jobs_project_status_idx
    ON public.async_image_jobs(project_id, status);
CREATE INDEX IF NOT EXISTS async_image_jobs_user_created_idx
    ON public.async_image_jobs(user_id, created_at DESC);

ALTER TABLE public.async_image_jobs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS async_image_jobs_owner_select ON public.async_image_jobs;
CREATE POLICY async_image_jobs_owner_select ON public.async_image_jobs
    FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS async_image_jobs_owner_insert ON public.async_image_jobs;
CREATE POLICY async_image_jobs_owner_insert ON public.async_image_jobs
    FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS async_image_jobs_owner_update ON public.async_image_jobs;
CREATE POLICY async_image_jobs_owner_update ON public.async_image_jobs
    FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS async_image_jobs_owner_delete ON public.async_image_jobs;
CREATE POLICY async_image_jobs_owner_delete ON public.async_image_jobs
    FOR DELETE USING (auth.uid() = user_id);

COMMENT ON TABLE  public.async_image_jobs           IS 'Async agent module — fire-and-return image job tracking. Owned by services/creative-os/services/async_agent. Independent from product_shots.';
COMMENT ON COLUMN public.async_image_jobs.kie_task_id IS 'KIE.ai NanoBanana taskId for cancel/poll.';

-- Trigger: bump updated_at on row update.
CREATE OR REPLACE FUNCTION public.async_agent_jobs_set_updated_at()
RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS async_video_jobs_set_updated_at ON public.async_video_jobs;
CREATE TRIGGER async_video_jobs_set_updated_at
    BEFORE UPDATE ON public.async_video_jobs
    FOR EACH ROW EXECUTE FUNCTION public.async_agent_jobs_set_updated_at();

DROP TRIGGER IF EXISTS async_image_jobs_set_updated_at ON public.async_image_jobs;
CREATE TRIGGER async_image_jobs_set_updated_at
    BEFORE UPDATE ON public.async_image_jobs
    FOR EACH ROW EXECUTE FUNCTION public.async_agent_jobs_set_updated_at();

-- Realtime publication. Wrapped in DO blocks for idempotency so the
-- migration succeeds whether or not the publication already includes the table.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE public.async_video_jobs;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END;
        BEGIN
            ALTER PUBLICATION supabase_realtime ADD TABLE public.async_image_jobs;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END;
    END IF;
END $$;
