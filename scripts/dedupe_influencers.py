"""One-time dedupe of influencers table via Supabase REST API.

Mirrors ugc_db/migrations/054_dedupe_influencers_and_unique_name.sql for environments
where SQL Editor access is inconvenient. Idempotent.
"""
import sys
from collections import defaultdict
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from dotenv import load_dotenv

load_dotenv(root / ".env.saas")
load_dotenv(root / "env.saas")
load_dotenv(root / ".env")
load_dotenv(root / "env")

from ugc_db.db_manager import get_supabase


def _norm(name: str | None) -> str:
    return (name or "").strip().lower()


def _row_score(row: dict) -> tuple:
    img = row.get("image_url") or ""
    has_img = 1 if img.strip() else 0
    created = row.get("created_at") or ""
    return (-has_img, created, row.get("id") or "")


def dedupe() -> int:
    sb = get_supabase()
    rows = (
        sb.table("influencers")
        .select("id,user_id,project_id,name,image_url,created_at")
        .execute()
        .data
        or []
    )

    groups: dict[tuple, list] = defaultdict(list)
    for row in rows:
        uid = row.get("user_id")
        pid = row.get("project_id")
        name = _norm(row.get("name"))
        if not uid or not pid or not name:
            continue
        groups[(uid, pid, name)].append(row)

    to_delete: list[str] = []
    for _key, members in groups.items():
        if len(members) <= 1:
            continue
        members.sort(key=_row_score)
        to_delete.extend(m["id"] for m in members[1:])

    removed = 0
    for row_id in to_delete:
        sb.table("influencers").delete().eq("id", row_id).execute()
        removed += 1

    # Backfill orphan project_id from default project
    orphans = (
        sb.table("influencers")
        .select("id,user_id")
        .is_("project_id", "null")
        .not_.is_("user_id", "null")
        .execute()
        .data
        or []
    )
    for orphan in orphans:
        uid = orphan["user_id"]
        orphan_name = (
            sb.table("influencers")
            .select("name")
            .eq("id", orphan["id"])
            .limit(1)
            .execute()
            .data
            or [{}]
        )[0].get("name", "")
        projects = (
            sb.table("projects")
            .select("id")
            .eq("user_id", uid)
            .eq("is_default", True)
            .limit(1)
            .execute()
            .data
        )
        if not projects:
            projects = (
                sb.table("projects")
                .select("id")
                .eq("user_id", uid)
                .order("created_at")
                .limit(1)
                .execute()
                .data
            )
        if not projects:
            continue
        target_pid = projects[0]["id"]
        conflict = (
            sb.table("influencers")
            .select("id")
            .eq("user_id", uid)
            .eq("project_id", target_pid)
            .ilike("name", orphan_name)
            .limit(1)
            .execute()
            .data
        )
        if conflict:
            # Orphan duplicates an existing scoped row — drop the orphan.
            sb.table("influencers").delete().eq("id", orphan["id"]).execute()
            removed += 1
            continue
        sb.table("influencers").update({"project_id": target_pid}).eq("id", orphan["id"]).execute()

    return removed


if __name__ == "__main__":
    n = dedupe()
    print(f"Removed {n} duplicate influencer row(s).")
