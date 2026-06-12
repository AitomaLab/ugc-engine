-- Track when connected-account post metrics were last refreshed from Ayrshare.
ALTER TABLE public.analytics_settings
    ADD COLUMN IF NOT EXISTS last_metrics_refreshed_at TIMESTAMPTZ;
