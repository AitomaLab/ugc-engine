-- Cache translated analytics AI content per locale (ES toggle support).
ALTER TABLE analytics_video_breakdowns
  ADD COLUMN IF NOT EXISTS output_locale TEXT DEFAULT 'en',
  ADD COLUMN IF NOT EXISTS locale_variants JSONB DEFAULT '{}'::jsonb;

ALTER TABLE analytics_tracked_accounts
  ADD COLUMN IF NOT EXISTS ai_strategy_report_locale TEXT DEFAULT 'en',
  ADD COLUMN IF NOT EXISTS ai_strategy_report_i18n JSONB DEFAULT '{}'::jsonb;

COMMENT ON COLUMN analytics_video_breakdowns.output_locale IS 'Locale of primary summary/hook/scenes columns: en | es';
COMMENT ON COLUMN analytics_video_breakdowns.locale_variants IS 'Cached translations keyed by locale, e.g. {"es": {"summary": "..."}}';
COMMENT ON COLUMN analytics_tracked_accounts.ai_strategy_report_locale IS 'Locale of ai_strategy_report markdown: en | es';
COMMENT ON COLUMN analytics_tracked_accounts.ai_strategy_report_i18n IS 'Cached strategy report translations keyed by locale';
