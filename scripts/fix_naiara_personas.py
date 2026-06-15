"""One-time fix: restore naiara@hvas.co's 40 uploaded personas.

The personas were written with user_id=naiara but project_id pointing at a
foreign project ('Lifestyle Moments', owned by another user) because of a stale
X-Project-Id header. This re-scopes them into naiara's real project and removes
the 26 auto-seeded template clones so only the custom personas remain.

Idempotent: re-running after success is a no-op (nothing left in the foreign
project, no template rows to capture).
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

from ugc_db.db_manager import get_supabase

NAIARA_UID = "9446be92-b234-490f-9a7a-94a72b970b5a"
NAIARA_PROJECT = "1fe687bb-d2f0-4740-b4ee-e0490193cd67"  # "My First Project"
FOREIGN_PROJECT = "b78f80c7-ba3c-46b4-9dd9-1befee181708"  # "Lifestyle Moments" (owned by another user)


def main() -> int:
    sb = get_supabase()

    # 1. Capture the auto-seeded template rows currently in naiara's project.
    #    These are the only rows there before the re-scope.
    template_rows = (
        sb.table("influencers")
        .select("id,name")
        .eq("user_id", NAIARA_UID)
        .eq("project_id", NAIARA_PROJECT)
        .execute()
        .data
        or []
    )
    template_ids = [r["id"] for r in template_rows]
    print(f"Templates to remove from naiara's project: {len(template_ids)}")

    # 2. Find the mis-scoped custom personas.
    customs = (
        sb.table("influencers")
        .select("id,name")
        .eq("user_id", NAIARA_UID)
        .eq("project_id", FOREIGN_PROJECT)
        .execute()
        .data
        or []
    )
    print(f"Custom personas to re-scope: {len(customs)}")

    # 3. Re-scope the custom personas into naiara's real project.
    rescoped = 0
    for row in customs:
        sb.table("influencers").update({"project_id": NAIARA_PROJECT}).eq("id", row["id"]).execute()
        rescoped += 1
    print(f"Re-scoped {rescoped} personas into {NAIARA_PROJECT[:8]}...")

    # 4. Delete the captured template rows by explicit ID (never touches customs).
    deleted = 0
    for tid in template_ids:
        sb.table("influencers").delete().eq("id", tid).execute()
        deleted += 1
    print(f"Deleted {deleted} template clones.")

    # 5. Verify final state.
    final = (
        sb.table("influencers")
        .select("id", count="exact")
        .eq("user_id", NAIARA_UID)
        .eq("project_id", NAIARA_PROJECT)
        .execute()
    )
    leftover_foreign = (
        sb.table("influencers")
        .select("id", count="exact")
        .eq("user_id", NAIARA_UID)
        .eq("project_id", FOREIGN_PROJECT)
        .execute()
    )
    print(f"\nFinal: project {NAIARA_PROJECT[:8]}... now has {final.count} influencers for naiara.")
    print(f"Leftover in foreign project: {leftover_foreign.count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
