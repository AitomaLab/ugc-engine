-- 026_add_projects_updated_at.sql
-- Tracks last-edited time on projects so the "My Projects" dashboard tab
-- can order by most-recently-touched. Triggers keep it fresh whenever any
-- child asset (video_jobs, clone_video_jobs, product_shots, etc.) is
-- inserted/updated/deleted.

-- ── 1. Column + backfill ────────────────────────────────────────────────
ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

-- Make backfill equal created_at so pre-existing rows don't jump to "just edited"
UPDATE projects SET updated_at = created_at WHERE updated_at <> created_at;

CREATE INDEX IF NOT EXISTS idx_projects_user_updated_at
  ON projects (user_id, updated_at DESC);

-- ── 2. Self-update trigger (project rename / settings change) ───────────
CREATE OR REPLACE FUNCTION set_projects_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_projects_set_updated_at ON projects;
CREATE TRIGGER trg_projects_set_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW
  WHEN (OLD.updated_at IS NOT DISTINCT FROM NEW.updated_at)
  EXECUTE FUNCTION set_projects_updated_at();

-- ── 3. Child-bump function ──────────────────────────────────────────────
CREATE OR REPLACE FUNCTION touch_parent_project()
RETURNS TRIGGER AS $$
DECLARE
  pid uuid;
BEGIN
  pid := COALESCE(NEW.project_id, OLD.project_id);
  IF pid IS NOT NULL THEN
    UPDATE projects SET updated_at = NOW() WHERE id = pid;
  END IF;
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

-- ── 4. Attach to child tables that represent user creative work ─────────
-- Wrapped in DO blocks so the migration is idempotent on DBs where a table
-- may not yet exist (e.g. generated_images on a fresh install).

DO $$
DECLARE
  t text;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'video_jobs',
    'clone_video_jobs',
    'product_shots',
    'generated_images',
    'app_clips',
    'products',
    'scripts'
  ]
  LOOP
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = t) THEN
      EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_touch_project ON %I', t, t);
      EXECUTE format(
        'CREATE TRIGGER trg_%I_touch_project
           AFTER INSERT OR UPDATE OR DELETE ON %I
           FOR EACH ROW EXECUTE FUNCTION touch_parent_project()',
        t, t
      );
    END IF;
  END LOOP;
END $$;
