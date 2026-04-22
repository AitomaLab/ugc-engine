-- 027_campaigns.sql
-- First-class campaigns + per-asset plan items for durable, multi-week
-- content pipelines orchestrated by the agent. Enables a single prompt to
-- plan, generate, and schedule heterogeneous assets (UGC videos, cinematic
-- shots, images) across N days without requiring user re-engagement.

-- ── 1. campaigns ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS campaigns (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  project_id      UUID REFERENCES projects(id) ON DELETE SET NULL,
  product_id      UUID REFERENCES products(id) ON DELETE SET NULL,

  name            TEXT NOT NULL,
  goal            TEXT,
  branding_notes  JSONB NOT NULL DEFAULT '{}'::jsonb,

  start_date      DATE,
  end_date        DATE,
  cadence         JSONB NOT NULL DEFAULT '{"interval":"daily","time_utc":"15:00"}'::jsonb,

  status          TEXT NOT NULL DEFAULT 'planning'
                  CHECK (status IN ('planning','approved','running','completed','failed','cancelled')),
  plan_json       JSONB,

  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_campaigns_user_status
  ON campaigns (user_id, status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaigns_project
  ON campaigns (project_id) WHERE project_id IS NOT NULL;

-- ── 2. campaign_plan_items ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS campaign_plan_items (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id         UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,

  slot_index          INT NOT NULL,
  scheduled_at        TIMESTAMPTZ NOT NULL,

  asset_type          TEXT NOT NULL
                      CHECK (asset_type IN ('ugc_video','clone_video','product_shot','generated_image','animated_image')),
  brief               JSONB NOT NULL DEFAULT '{}'::jsonb,

  platforms           TEXT[] NOT NULL DEFAULT '{}',
  caption             TEXT,
  hashtags            TEXT[] DEFAULT '{}',

  job_id              UUID,
  asset_url           TEXT,
  scheduled_post_id   UUID,

  status              TEXT NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending','generating','ready_to_post','scheduled','posted','failed','cancelled')),
  error               TEXT,

  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  UNIQUE (campaign_id, slot_index)
);

CREATE INDEX IF NOT EXISTS idx_campaign_items_campaign_status
  ON campaign_plan_items (campaign_id, status);
CREATE INDEX IF NOT EXISTS idx_campaign_items_job
  ON campaign_plan_items (job_id) WHERE job_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_campaign_items_watcher
  ON campaign_plan_items (status, updated_at)
  WHERE status IN ('generating','ready_to_post');

-- ── 3. self-update triggers (bump updated_at on any row change) ─────────
CREATE OR REPLACE FUNCTION set_campaigns_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_campaigns_set_updated_at ON campaigns;
CREATE TRIGGER trg_campaigns_set_updated_at
  BEFORE UPDATE ON campaigns
  FOR EACH ROW
  WHEN (OLD.updated_at IS NOT DISTINCT FROM NEW.updated_at)
  EXECUTE FUNCTION set_campaigns_updated_at();

DROP TRIGGER IF EXISTS trg_campaign_items_set_updated_at ON campaign_plan_items;
CREATE TRIGGER trg_campaign_items_set_updated_at
  BEFORE UPDATE ON campaign_plan_items
  FOR EACH ROW
  WHEN (OLD.updated_at IS NOT DISTINCT FROM NEW.updated_at)
  EXECUTE FUNCTION set_campaigns_updated_at();

-- ── 4. touch parent project when a campaign / item changes ──────────────
-- Reuses touch_parent_project() from migration 026.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'touch_parent_project') THEN
    EXECUTE 'DROP TRIGGER IF EXISTS trg_campaigns_touch_project ON campaigns';
    EXECUTE 'CREATE TRIGGER trg_campaigns_touch_project
               AFTER INSERT OR UPDATE OR DELETE ON campaigns
               FOR EACH ROW EXECUTE FUNCTION touch_parent_project()';
  END IF;
END $$;

-- ── 5. RLS ──────────────────────────────────────────────────────────────
ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaign_plan_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS campaigns_owner ON campaigns;
CREATE POLICY campaigns_owner ON campaigns
  FOR ALL TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS campaign_items_owner ON campaign_plan_items;
CREATE POLICY campaign_items_owner ON campaign_plan_items
  FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM campaigns c WHERE c.id = campaign_id AND c.user_id = auth.uid()))
  WITH CHECK (EXISTS (SELECT 1 FROM campaigns c WHERE c.id = campaign_id AND c.user_id = auth.uid()));
