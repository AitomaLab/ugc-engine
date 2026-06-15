"""Run influencer table diagnostics against production Supabase (read-only)."""
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from dotenv import load_dotenv

load_dotenv(root / ".env.saas")
load_dotenv(root / "env.saas")
load_dotenv(root / ".env")
load_dotenv(root / "env")

from ugc_db.db_manager import get_supabase, _find_template_admin_project_id


def main():
    sb = get_supabase()
    admin_pid = _find_template_admin_project_id(sb)

    rows = sb.table("influencers").select("id,user_id,project_id,name,created_at", count="exact").limit(1).execute()
    total = rows.count or 0
    print(f"=== 5) Table size: total_rows={total} ===")

    all_rows = sb.table("influencers").select("user_id,project_id").execute().data or []
    users = {r["user_id"] for r in all_rows if r.get("user_id")}
    projects = {r["project_id"] for r in all_rows if r.get("project_id")}
    print(f"    distinct_users={len(users)}, distinct_projects={len(projects)}")
    print(f"    admin_template_project_id={admin_pid}")

    orphans = (
        sb.table("influencers")
        .select("id,name,user_id,project_id,created_at")
        .or_("user_id.is.null,project_id.is.null")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
        .data
        or []
    )
    print(f"\n=== 3) Orphans (null user_id or project_id): {len(orphans)} shown (max 20) ===")
    for r in orphans[:10]:
        print(f"    {r.get('name')!r} user={str(r.get('user_id'))[:8]}... proj={str(r.get('project_id'))[:8]}... created={r.get('created_at')}")

    recent = (
        sb.table("influencers")
        .select("id,name,user_id,project_id,created_at")
        .gte("created_at", "2026-06-13T00:00:00Z")
        .order("created_at", desc=True)
        .limit(30)
        .execute()
        .data
        or []
    )
    print(f"\n=== 2) Recent rows (since 2026-06-13): {len(recent)} ===")
    for r in recent[:15]:
        print(f"    {r.get('name')!r} user={str(r.get('user_id'))[:8]}... proj={str(r.get('project_id'))[:8]}...")

    # Duplicate counts via Python (PostgREST has no GROUP BY HAVING)
    from collections import defaultdict

    dup_key_counts: dict[tuple, int] = defaultdict(int)
    full = sb.table("influencers").select("user_id,project_id,name").execute().data or []
    for r in full:
        key = (r.get("user_id"), r.get("project_id"), (r.get("name") or "").strip().lower())
        dup_key_counts[key] += 1

    dups = [(k, c) for k, c in dup_key_counts.items() if c > 1]
    dups.sort(key=lambda x: -x[1])
    extra_rows = sum(c - 1 for _, c in dups)
    print(f"\n=== 1) Duplicate (user_id, project_id, name) groups: {len(dups)} groups, {extra_rows} extra rows to remove ===")
    for (uid, pid, name), cnt in dups[:15]:
        print(f"    {name!r} cnt={cnt} user={str(uid)[:8]}... proj={str(pid)[:8]}...")


if __name__ == "__main__":
    main()
