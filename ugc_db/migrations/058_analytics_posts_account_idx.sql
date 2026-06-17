-- Speed per-account analytics aggregates (GET /accounts, list_account_posts).
CREATE INDEX IF NOT EXISTS idx_analytics_posts_user_platform_username
  ON analytics_posts (user_id, platform, username);
