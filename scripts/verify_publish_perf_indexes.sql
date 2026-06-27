-- Verify / apply indexes for Publish page performance (Calendar + Analytics).
-- Run in Supabase SQL Editor for each environment (local project + production).

-- 058: analytics per-account queries
CREATE INDEX IF NOT EXISTS idx_analytics_posts_user_platform_username
  ON analytics_posts (user_id, platform, username);

-- 059: calendar range queries
CREATE INDEX IF NOT EXISTS idx_social_posts_user_scheduled_at
  ON social_posts (user_id, scheduled_at);

-- Confirm indexes exist
SELECT indexname, tablename
FROM pg_indexes
WHERE indexname IN (
  'idx_analytics_posts_user_platform_username',
  'idx_social_posts_user_scheduled_at'
)
ORDER BY tablename, indexname;
