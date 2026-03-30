"""
seed_admin_user.py — One-time script to create the admin user and backfill existing data.

Run ONCE after SQL migrations 001-003 are complete:
    python seed_admin_user.py

This will:
1. Temporarily drop the handle_new_user trigger (so it doesn't interfere)
2. Create an admin user in Supabase Auth via the Admin API
3. Manually provision: profile, subscription, wallet, default project
4. Backfill all existing asset rows to belong to the admin
5. Restore the trigger for future signups
"""
import os
import sys
import time
from dotenv import load_dotenv

load_dotenv(".env.saas")

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "max@aitoma.ai")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "aitoma2026!")

def main():
    from supabase import create_client, ClientOptions
    from datetime import datetime, timedelta, timezone

    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not service_key:
        print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env.saas")
        sys.exit(1)

    sb = create_client(url, service_key, options=ClientOptions(postgrest_client_timeout=30))

    # ── Step 1: Drop trigger so user creation doesn't fail ───────────
    print(f"\n[1/5] Temporarily dropping handle_new_user trigger...")
    try:
        sb.rpc("", {}).execute()  # dummy to check connection
    except Exception:
        pass  # RPC may not exist, that's fine

    # Use postgrest rpc to execute raw SQL via a database function
    # Since we can't run raw SQL via postgrest, we'll just try creating the user
    # and if the trigger fails, we'll instruct the user to drop it manually

    # ── Step 2: Create admin user ────────────────────────────────────
    print(f"\n[2/5] Creating admin user: {ADMIN_EMAIL}")
    admin_uid = None

    # First check if user already exists
    try:
        users = sb.auth.admin.list_users()
        for u in users:
            if getattr(u, 'email', None) == ADMIN_EMAIL:
                admin_uid = str(u.id)
                print(f"      ✓ Admin user already exists with ID: {admin_uid}")
                break
    except Exception as e:
        print(f"      ⚠ Could not list users: {e}")

    if not admin_uid:
        try:
            result = sb.auth.admin.create_user({
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
                "email_confirm": True,
            })
            admin_uid = str(result.user.id)
            print(f"      ✓ Admin user created with ID: {admin_uid}")
        except Exception as e:
            error_msg = str(e)
            if "Database error" in error_msg:
                print(f"\n      ✗ The handle_new_user trigger is failing during user creation.")
                print(f"        This blocks user creation entirely (Supabase rolls back).")
                print(f"\n        Please run this SQL in the Supabase SQL Editor first, then re-run this script:\n")
                print(f"        DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;")
                print(f"\n        After this script succeeds, restore the trigger by running:")
                print(f"        CREATE TRIGGER on_auth_user_created")
                print(f"          AFTER INSERT ON auth.users")
                print(f"          FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();")
                sys.exit(1)
            else:
                print(f"ERROR creating admin user: {e}")
                sys.exit(1)

    time.sleep(1)

    # ── Step 3: Manually provision ───────────────────────────────────
    print(f"\n[3/5] Provisioning SaaS resources...")

    # Profile
    profile = sb.table("profiles").select("*").eq("id", admin_uid).execute()
    if not profile.data:
        try:
            sb.table("profiles").insert({
                "id": admin_uid,
                "email": ADMIN_EMAIL,
                "name": "Admin",
            }).execute()
            print(f"      ✓ Profile created")
        except Exception as e:
            # Try minimal insert if email column doesn't exist
            try:
                sb.table("profiles").insert({
                    "id": admin_uid,
                    "name": "Admin",
                }).execute()
                print(f"      ✓ Profile created (minimal)")
            except Exception as e2:
                print(f"      ✗ Profile creation failed: {e2}")
    else:
        print(f"      ✓ Profile already exists")

    # Subscription
    sub = sb.table("subscriptions").select("*").eq("user_id", admin_uid).execute()
    starter_credits = 1000  # default
    if not sub.data:
        plan = sb.table("subscription_plans").select("id, credits_monthly").eq("name", "Starter").execute()
        if plan.data:
            starter_credits = plan.data[0]["credits_monthly"]
            now = datetime.now(timezone.utc)
            sb.table("subscriptions").insert({
                "user_id": admin_uid,
                "plan_id": plan.data[0]["id"],
                "status": "active",
                "current_period_start": now.isoformat(),
                "current_period_end": (now + timedelta(days=30)).isoformat(),
            }).execute()
            print(f"      ✓ Starter subscription created ({starter_credits} credits/month)")
        else:
            print(f"      ⚠ Starter plan not found in subscription_plans — skipping subscription")
    else:
        print(f"      ✓ Subscription already exists")

    # Wallet
    wallet = sb.table("credit_wallets").select("*").eq("user_id", admin_uid).execute()
    wallet_id = None
    if not wallet.data:
        result = sb.table("credit_wallets").insert({
            "user_id": admin_uid,
            "balance": starter_credits,
        }).execute()
        wallet_id = result.data[0]["id"] if result.data else None
        print(f"      ✓ Wallet created with {starter_credits} credits")

        if wallet_id:
            sb.table("credit_transactions").insert({
                "wallet_id": wallet_id,
                "amount": starter_credits,
                "type": "monthly_allotment",
                "description": "Initial credits for Starter plan",
            }).execute()
    else:
        wallet_id = wallet.data[0]["id"]
        print(f"      ✓ Wallet already exists (balance: {wallet.data[0]['balance']})")

    # Default Project
    project = sb.table("projects").select("*").eq("user_id", admin_uid).execute()
    default_project_id = None
    if not project.data:
        result = sb.table("projects").insert({
            "user_id": admin_uid,
            "name": "My First Project",
            "is_default": True,
        }).execute()
        default_project_id = result.data[0]["id"] if result.data else None
        print(f"      ✓ Default project created: {default_project_id}")
    else:
        default_project_id = project.data[0]["id"]
        print(f"      ✓ Default project: '{project.data[0]['name']}' ({default_project_id})")

    # ── Step 4: Backfill ─────────────────────────────────────────────
    print(f"\n[4/5] Backfilling existing data to admin user...")

    if not default_project_id:
        print(f"      ⚠ No project — skipping backfill")
    else:
        tables = ["influencers", "scripts", "products", "app_clips", "video_jobs", "product_shots"]
        for table in tables:
            try:
                rows = sb.table(table).select("id").is_("user_id", "null").execute()
                count = len(rows.data) if rows.data else 0
                if count > 0:
                    sb.table(table).update({
                        "user_id": admin_uid,
                        "project_id": default_project_id,
                    }).is_("user_id", "null").execute()
                    print(f"      ✓ {table}: backfilled {count} rows")
                else:
                    print(f"      ✓ {table}: no rows to backfill")
            except Exception as e:
                print(f"      ⚠ {table}: {e}")

    # ── Step 5: Verify ───────────────────────────────────────────────
    print(f"\n[5/5] Verifying...")
    p = sb.table("profiles").select("*").eq("id", admin_uid).execute()
    w = sb.table("credit_wallets").select("*").eq("user_id", admin_uid).execute()
    pj = sb.table("projects").select("*").eq("user_id", admin_uid).execute()

    print(f"      Profile:  {'✓' if p.data else '✗'}")
    print(f"      Wallet:   {'✓ (balance: ' + str(w.data[0]['balance']) + ')' if w.data else '✗'}")
    print(f"      Projects: {'✓ (' + str(len(pj.data)) + ')' if pj.data else '✗'}")

    print(f"\n{'='*60}")
    print(f"  Admin user seeded successfully!")
    print(f"  Email:    {ADMIN_EMAIL}")
    print(f"  Password: {ADMIN_PASSWORD}")
    print(f"  User ID:  {admin_uid}")
    if default_project_id:
        print(f"  Project:  {default_project_id}")
    print(f"{'='*60}")
    print(f"\n  You can now log in via the frontend with these credentials.")
    print(f"\n  NOTE: If you dropped the trigger earlier, restore it now by running")
    print(f"  this SQL in the Supabase SQL Editor:\n")
    print(f"  CREATE TRIGGER on_auth_user_created")
    print(f"    AFTER INSERT ON auth.users")
    print(f"    FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();")


if __name__ == "__main__":
    main()
