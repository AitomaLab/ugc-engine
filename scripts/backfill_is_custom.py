"""One-time backfill: flag existing user-created influencers as is_custom=true.

Run AFTER migration 056 (which adds the is_custom column, default false).

Custom influencers are user-uploaded personas that should be visible across all
of a user's projects. Template clones are auto-seeded per project from the admin
template roster and stay project-scoped. There is no explicit marker on legacy
rows, so we infer:

    is_custom = NOT in the admin template project
                AND normalized name NOT in the admin template name set

Caveat: a custom persona that happens to reuse a template name (e.g. a user
named their own persona "Lila") cannot be auto-detected and will stay
is_custom=false. This is rare; such rows can be fixed manually if needed.

Idempotent: re-running only sets is_custom=true on rows that aren't already true.
Pass --dry-run to preview without writing.
"""
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


def _norm(name: str | None) -> str:
    return (name or "").strip().lower()


def _fetch_all(sb, select: str, **filters):
    """Paginate through PostgREST's default 1000-row cap."""
    rows = []
    start = 0
    page_size = 1000
    while True:
        q = sb.table("influencers").select(select)
        for key, val in filters.items():
            q = q.eq(key, val)
        batch = q.range(start, start + page_size - 1).execute().data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return rows


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    sb = get_supabase()

    admin_pid = _find_template_admin_project_id(sb)
    if not admin_pid:
        print("ERROR: Could not locate admin template project. Aborting.")
        return 1
    print(f"Admin template project: {admin_pid[:8]}...")

    template_rows = _fetch_all(sb, "name", project_id=admin_pid)
    template_names = {_norm(r.get("name")) for r in template_rows if _norm(r.get("name"))}
    print(f"Template names: {len(template_names)}")

    all_rows = _fetch_all(sb, "id,name,project_id,is_custom")

    to_flag = []
    for row in all_rows:
        if row.get("is_custom"):
            continue
        if row.get("project_id") == admin_pid:
            continue
        if _norm(row.get("name")) in template_names:
            continue
        to_flag.append(row)

    print(f"Rows to mark is_custom=true: {len(to_flag)}")
    for r in to_flag[:50]:
        print(f"  - {r.get('name')}  (project {str(r.get('project_id'))[:8]}...)")
    if len(to_flag) > 50:
        print(f"  ... and {len(to_flag) - 50} more")

    if dry_run:
        print("\nDry run — no changes written.")
        return 0

    updated = 0
    for r in to_flag:
        sb.table("influencers").update({"is_custom": True}).eq("id", r["id"]).execute()
        updated += 1
    print(f"\nUpdated {updated} rows to is_custom=true.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
