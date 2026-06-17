-- Speed calendar range queries on GET /api/schedule.
CREATE INDEX IF NOT EXISTS idx_social_posts_user_scheduled_at
  ON social_posts (user_id, scheduled_at);
