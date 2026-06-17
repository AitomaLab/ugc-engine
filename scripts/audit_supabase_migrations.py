#!/usr/bin/env python3
"""
Audit (and optionally apply) Supabase migrations 043–057 on a shared DB.

Usage:
  python scripts/audit_supabase_migrations.py                    # audit (postgres or REST fallback)
  python scripts/audit_supabase_migrations.py --apply          # run MISSING migration files (needs DATABASE_URL)
  python scripts/audit_supabase_migrations.py --apply --include-057  # also restore strict invite hook
  python scripts/audit_supabase_migrations.py --print-missing-sql    # paste into Supabase SQL Editor

Requires DATABASE_URL for postgres audit/apply. Falls back to Supabase REST column probes when
postgres auth fails but SUPABASE_URL + SUPABASE_SERVICE_KEY are set.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "ugc_db" / "migrations"

# Ordered migration files to check (042/051 skipped — base tables assumed present).
AUDIT_ORDER: list[tuple[str, Path | None, str]] = [
    ("043", MIGRATIONS / "043_analytics_added_at_and_storage.sql", "analytics_posts.added_at"),
    ("044", MIGRATIONS / "044_analytics_upgrade.sql", "analytics_tracked_accounts.scrape_frequency"),
    ("045", MIGRATIONS / "045_analytics_studio_connections.sql", "analytics_tracked_accounts.linked_via_connections"),
    ("046", MIGRATIONS / "046_social_posts_image_schedule.sql", "social_posts.product_shot_id"),
    ("047", MIGRATIONS / "047_analytics_metrics_refresh.sql", "analytics_settings.last_metrics_refreshed_at"),
    ("048", MIGRATIONS / "048_analytics_funnel_metrics.sql", "analytics_posts.impressions"),
    ("049", MIGRATIONS / "049_ayrshare_ref_id.sql", "ayrshare_profiles.ayrshare_ref_id"),
    ("050", MIGRATIONS / "050_analytics_strategy_report.sql", "analytics_tracked_accounts.ai_strategy_report"),
    ("052_hook", None, "function validate_invite_code"),
    ("054", MIGRATIONS / "054_dedupe_influencers_and_unique_name.sql", "idx_influencers_project_name_unique"),
    ("055", MIGRATIONS / "055_default_model_api_veo.sql", "video_jobs.model_api default veo-3.1-fast"),
    ("056", MIGRATIONS / "056_influencer_is_custom.sql", "influencers.is_custom"),
]

OPTIONAL_STRICT_HOOK = ("057", MIGRATIONS / "057_restore_strict_invite_hook.sql", "strict invite hook (re-closes gate)")

# REST column probes when direct postgres is unavailable.
REST_CHECKS: list[tuple[str, str, str, str]] = [
    ("043", "analytics_posts", "added_at", "analytics_posts.added_at"),
    ("044", "analytics_tracked_accounts", "scrape_frequency", "analytics_tracked_accounts.scrape_frequency"),
    ("045", "analytics_tracked_accounts", "linked_via_connections", "analytics_tracked_accounts.linked_via_connections"),
    ("046", "social_posts", "product_shot_id", "social_posts.product_shot_id + media_kind"),
    ("047", "analytics_settings", "last_metrics_refreshed_at", "analytics_settings.last_metrics_refreshed_at"),
    ("048", "analytics_posts", "impressions", "analytics_posts.impressions/reach/clicks/ctr"),
    ("049", "ayrshare_profiles", "ayrshare_ref_id", "ayrshare_profiles.ayrshare_ref_id"),
    ("050", "analytics_tracked_accounts", "ai_strategy_report", "analytics_tracked_accounts.ai_strategy_report"),
    ("056", "influencers", "is_custom", "influencers.is_custom"),
]

DIAGNOSTIC_SQL = """
SELECT migration, status, detail FROM (
  SELECT '043' AS migration,
         CASE WHEN EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='analytics_posts' AND column_name='added_at'
         ) THEN 'OK' ELSE 'MISSING' END AS status,
         'analytics_posts.added_at' AS detail
  UNION ALL
  SELECT '044',
         CASE WHEN EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='analytics_tracked_accounts' AND column_name='scrape_frequency'
         ) THEN 'OK' ELSE 'MISSING' END,
         'analytics_tracked_accounts.scrape_frequency'
  UNION ALL
  SELECT '045',
         CASE WHEN EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='analytics_tracked_accounts' AND column_name='linked_via_connections'
         ) THEN 'OK' ELSE 'MISSING' END,
         'analytics_tracked_accounts.linked_via_connections'
  UNION ALL
  SELECT '046',
         CASE WHEN EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='social_posts' AND column_name='product_shot_id'
         ) THEN 'OK' ELSE 'MISSING' END,
         'social_posts.product_shot_id + media_kind'
  UNION ALL
  SELECT '047',
         CASE WHEN EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='analytics_settings' AND column_name='last_metrics_refreshed_at'
         ) THEN 'OK' ELSE 'MISSING' END,
         'analytics_settings.last_metrics_refreshed_at'
  UNION ALL
  SELECT '048',
         CASE WHEN EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='analytics_posts' AND column_name='impressions'
         ) THEN 'OK' ELSE 'MISSING' END,
         'analytics_posts.impressions/reach/clicks/ctr'
  UNION ALL
  SELECT '049',
         CASE WHEN EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='ayrshare_profiles' AND column_name='ayrshare_ref_id'
         ) THEN 'OK' ELSE 'MISSING' END,
         'ayrshare_profiles.ayrshare_ref_id'
  UNION ALL
  SELECT '050',
         CASE WHEN EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='analytics_tracked_accounts' AND column_name='ai_strategy_report'
         ) THEN 'OK' ELSE 'MISSING' END,
         'analytics_tracked_accounts.ai_strategy_report'
  UNION ALL
  SELECT '052_hook',
         CASE WHEN EXISTS (
           SELECT 1 FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid
           WHERE n.nspname='public' AND p.proname='validate_invite_code'
         ) THEN 'OK' ELSE 'MISSING' END,
         'function validate_invite_code'
  UNION ALL
  SELECT '054',
         CASE WHEN EXISTS (
           SELECT 1 FROM pg_indexes
           WHERE schemaname='public' AND indexname='idx_influencers_project_name_unique'
         ) THEN 'OK' ELSE 'MISSING' END,
         'idx_influencers_project_name_unique'
  UNION ALL
  SELECT '055',
         CASE WHEN (
           SELECT column_default FROM information_schema.columns
           WHERE table_schema='public' AND table_name='video_jobs' AND column_name='model_api'
         ) ILIKE '%veo-3.1-fast%' THEN 'OK' ELSE 'MISSING' END,
         'video_jobs.model_api default = veo-3.1-fast'
  UNION ALL
  SELECT '056',
         CASE WHEN EXISTS (
           SELECT 1 FROM information_schema.columns
           WHERE table_schema='public' AND table_name='influencers' AND column_name='is_custom'
         ) THEN 'OK' ELSE 'MISSING' END,
         'influencers.is_custom'
) t
ORDER BY migration;
"""

HOOK_STRICT_CHECK_SQL = """
SELECT CASE
  WHEN pg_get_functiondef(p.oid) ILIKE '%An invite code is required to sign up%'
    AND pg_get_functiondef(p.oid) NOT ILIKE '%Open signup while invite gate is disabled%'
  THEN 'STRICT'
  WHEN pg_get_functiondef(p.oid) ILIKE '%Open signup while invite gate is disabled%'
    OR (
      pg_get_functiondef(p.oid) ILIKE '%if v_code is null or v_code = ''''%'
      AND pg_get_functiondef(p.oid) ILIKE '%return ''{}''::jsonb;%'
      AND pg_get_functiondef(p.oid) NOT ILIKE '%An invite code is required%'
    )
  THEN 'OPEN'
  ELSE 'UNKNOWN'
END AS hook_mode
FROM pg_proc p
JOIN pg_namespace n ON p.pronamespace = n.oid
WHERE n.nspname = 'public' AND p.proname = 'validate_invite_code'
LIMIT 1;
"""


def run_rest_audit() -> list[tuple[str, str, str]]:
    """Probe columns via PostgREST (no DDL). 052/054/055 need postgres."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("REST audit unavailable: SUPABASE_URL + SUPABASE_SERVICE_KEY required.", file=sys.stderr)
        return []

    from supabase import create_client

    sb = create_client(url, key)
    results: list[tuple[str, str, str]] = []
    for mid, table, col, detail in REST_CHECKS:
        try:
            sb.table(table).select(col).limit(1).execute()
            results.append((mid, "OK", detail))
        except Exception as e:
            msg = str(e).lower()
            if "column" in msg or "42703" in msg or "does not exist" in msg or "pgrst204" in msg:
                results.append((mid, "MISSING", detail))
            else:
                results.append((mid, "ERROR", f"{detail} ({str(e)[:80]})"))

    # 052 hook — not visible via REST; mark as UNKNOWN unless postgres checked later.
    results.append(("052_hook", "UNKNOWN", "function validate_invite_code (use postgres or --probe-hook)"))
    results.append(("054", "UNKNOWN", "idx_influencers_project_name_unique (postgres only)"))
    results.append(("055", "UNKNOWN", "video_jobs.model_api default (postgres only)"))
    results.sort(key=lambda r: r[0])
    return results


def probe_invite_hook() -> str:
    """Sign up without invite code; infer hook strictness."""
    url = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    anon = os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not anon:
        return "UNKNOWN (no anon key)"

    import uuid

    from supabase import create_client

    sb = create_client(url, anon)
    email = f"hook-probe-{uuid.uuid4().hex[:12]}@invalid.example"
    try:
        r = sb.auth.sign_up(
            {
                "email": email,
                "password": "ProbeTest123!@#Probe",
                "options": {"data": {}},
            }
        )
        if r.user:
            return "OPEN or DISABLED (signup without invite code succeeded)"
    except Exception as e:
        msg = str(e).lower()
        if "invite" in msg or "403" in msg:
            return "STRICT (invite required)"
        if "hook" in msg:
            return f"HOOK_ERROR ({str(e)[:120]})"
        return f"UNKNOWN ({str(e)[:120]})"
    return "UNKNOWN"


def load_env() -> None:
    from dotenv import load_dotenv

    for name in (".env.saas", "env.saas", ".env", "env"):
        path = ROOT / name
        if path.is_file():
            load_dotenv(path)


def get_connection(*, required: bool = True):
    url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if not url:
        if required:
            print(
                "ERROR: DATABASE_URL not set.\n"
                "Add it to env.saas (Supabase → Settings → Database → Connection string URI)\n"
                "Or use REST fallback (SUPABASE_URL + SUPABASE_SERVICE_KEY).",
                file=sys.stderr,
            )
            sys.exit(1)
        return None
    try:
        import psycopg2
    except ImportError:
        if required:
            print("ERROR: psycopg2 not installed. pip install psycopg2-binary", file=sys.stderr)
            sys.exit(1)
        return None
    try:
        return psycopg2.connect(url)
    except Exception as e:
        if required:
            raise
        print(f"Postgres unavailable ({type(e).__name__}); using REST audit fallback.", file=sys.stderr)
        return None


def run_audit(conn) -> list[tuple[str, str, str]]:
    with conn.cursor() as cur:
        cur.execute(DIAGNOSTIC_SQL)
        rows = cur.fetchall()
    return [(str(r[0]), str(r[1]), str(r[2])) for r in rows]


def check_hook_mode(conn) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON p.pronamespace = n.oid "
            "WHERE n.nspname='public' AND p.proname='validate_invite_code'"
        )
        if not cur.fetchone():
            return None
        cur.execute(HOOK_STRICT_CHECK_SQL)
        row = cur.fetchone()
        return str(row[0]) if row else "UNKNOWN"


def apply_migration(conn, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    print(f"  Applying {path.name} ...")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print(f"  OK: {path.name}")


def migration_file_for_id(mid: str) -> Path | None:
    if mid == "052_hook":
        return MIGRATIONS / "052_invite_code_hook.sql"
    for m, path, _ in AUDIT_ORDER:
        if m == mid:
            return path
    return None


def print_missing_sql(missing_ids: list[str], include_057: bool) -> None:
    print("\n=== SQL to paste in Supabase SQL Editor ===\n")
    for mid in missing_ids:
        path = migration_file_for_id(mid)
        if path and path.is_file():
            print(f"-- {path.name}")
            print(path.read_text(encoding="utf-8").strip())
            print()
    if include_057:
        p = MIGRATIONS / "057_restore_strict_invite_hook.sql"
        if p.is_file() and "057" not in missing_ids:
            print(f"-- {p.name}")
            print(p.read_text(encoding="utf-8").strip())
            print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit/apply Supabase migrations on shared DB")
    parser.add_argument("--apply", action="store_true", help="Run SQL files for MISSING markers")
    parser.add_argument(
        "--include-057",
        action="store_true",
        help="When applying, also run 057_restore_strict_invite_hook.sql (invite-only gate)",
    )
    parser.add_argument(
        "--print-missing-sql",
        action="store_true",
        help="Print SQL for MISSING migrations (for Supabase SQL Editor)",
    )
    parser.add_argument("--probe-hook", action="store_true", help="Test signup without invite code")
    args = parser.parse_args()

    load_env()
    conn = get_connection(required=args.apply)

    print("=== Supabase migration audit (shared DB) ===\n")
    audit_via = "postgres"
    if conn is not None:
        results = run_audit(conn)
    else:
        audit_via = "REST"
        results = run_rest_audit()
        if not results:
            return 1

    missing = [r for r in results if r[1] == "MISSING"]

    print(f"Audit method: {audit_via}\n")
    print(f"{'Migration':<12} {'Status':<8} Detail")
    print("-" * 60)
    for mid, status, detail in results:
        print(f"{mid:<12} {status:<8} {detail}")

    hook_mode: str | None = None
    if conn is not None:
        hook_mode = check_hook_mode(conn)
    if args.probe_hook or hook_mode is None:
        probe = probe_invite_hook()
        print(f"\nAuth hook probe: {probe}")
        if hook_mode is None and "STRICT" in probe:
            hook_mode = "STRICT"
        elif hook_mode is None and "OPEN" in probe:
            hook_mode = "OPEN"

    print()
    if hook_mode == "STRICT":
        print("Auth hook: STRICT — ready for NEXT_PUBLIC_REQUIRE_INVITE_CODE=true")
    elif hook_mode == "OPEN":
        print("Auth hook: OPEN — run 057 + enable Before User Created hook before gating signup")
    elif hook_mode is None:
        print("Auth hook: not verified via postgres — enable hook in Dashboard after 057")
    else:
        print(f"Auth hook (postgres): {hook_mode}")

    print()
    print("Skipped by design: 042 (analytics tables exist), 051 (invite_codes exists), 053 (opens gate — do NOT run)")
    print()

    if not missing:
        print("All audited markers OK. No incremental migrations required.")
    else:
        print(f"MISSING ({len(missing)}): " + ", ".join(r[0] for r in missing))

    if args.print_missing_sql:
        print_missing_sql([r[0] for r in missing], args.include_057)

    if args.apply:
        if conn is None:
            print("\nERROR: --apply requires working DATABASE_URL.", file=sys.stderr)
            print("Update env.saas DATABASE_URL or use --print-missing-sql and run in SQL Editor.", file=sys.stderr)
            return 1
        if not missing and not args.include_057:
            print("\nNothing to apply.")
        else:
            print("\n=== Applying missing migrations ===")
            applied: list[str] = []
            for mid, _, _ in missing:
                path = migration_file_for_id(mid)
                if path and path.is_file():
                    try:
                        apply_migration(conn, path)
                        applied.append(mid)
                    except Exception as e:
                        conn.rollback()
                        print(f"  FAILED {path.name}: {e}", file=sys.stderr)
                        return 1
                elif mid == "052_hook":
                    p = MIGRATIONS / "052_invite_code_hook.sql"
                    apply_migration(conn, p)
                    applied.append(mid)

            if args.include_057:
                p = MIGRATIONS / "057_restore_strict_invite_hook.sql"
                if p.is_file():
                    apply_migration(conn, p)
                    applied.append("057")
                    print("\nAfter 057: enable Supabase Auth → Hooks → Before User Created → validate_invite_code")

            print(f"\nApplied: {', '.join(applied) if applied else '(none)'}")
            print("\n=== Post-apply audit ===")
            for mid, status, detail in run_audit(conn):
                print(f"{mid:<12} {status:<8} {detail}")

    if conn is not None:
        conn.close()

    print("\nManual checklist (Dashboard):")
    print("  1. Authentication → Hooks → Before User Created → pg-functions://postgres/public/validate_invite_code")
    print("  2. Vercel: NEXT_PUBLIC_REQUIRE_INVITE_CODE=true (only when hook is STRICT / 057 applied)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
