"""One-shot migration: convert existing non-PNG image rows to opaque PNG.

For each configured (table, column, bucket) triple, find rows whose stored
image URL is not `.png` / `.jpg` / `.jpeg`, download the file, normalize via
`normalize_image_bytes`, upload the PNG to the same bucket, update the DB
column, and best-effort delete the original.

Usage:
    python -m scripts.migrate_images_to_png --dry-run
    python -m scripts.migrate_images_to_png

Run from /services/creative-os/ with the service-role Supabase key in env.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from ugc_db.db_manager import get_supabase
from ugc_db.image_normalize import normalize_image_bytes

TRIPLES = [
    ("products", "image_url", "product-images"),
    ("influencers", "reference_image_url", "influencer-images"),
    ("product_shots", "image_url", "product-images"),
]

OK_EXTS = {".png", ".jpg", ".jpeg"}


def _path_in_bucket(url: str, bucket: str) -> str | None:
    """Extract the object path inside `bucket` from a Supabase public URL."""
    parsed = urlparse(url)
    marker = f"/object/public/{bucket}/"
    idx = parsed.path.find(marker)
    if idx < 0:
        return None
    return parsed.path[idx + len(marker):]


def _ext(path: str) -> str:
    dot = path.rfind(".")
    return path[dot:].lower() if dot >= 0 else ""


def migrate(dry_run: bool) -> None:
    sb = get_supabase()

    for table, column, bucket in TRIPLES:
        print(f"\n=== {table}.{column} -> {bucket} ===")
        try:
            rows = sb.table(table).select(f"id,{column}").execute().data or []
        except Exception as e:
            print(f"  [skip] could not read {table}: {e}")
            continue

        candidates = []
        for row in rows:
            url = row.get(column)
            if not url:
                continue
            old_path = _path_in_bucket(url, bucket)
            if not old_path:
                continue
            if _ext(old_path) in OK_EXTS:
                continue
            candidates.append((row["id"], url, old_path))

        print(f"  {len(candidates)} row(s) need conversion")

        if dry_run:
            for rid, url, old_path in candidates[:10]:
                print(f"    [dry] {table}.id={rid}: {old_path}")
            if len(candidates) > 10:
                print(f"    [dry] ... and {len(candidates) - 10} more")
            continue

        ok = 0
        failed = 0
        for i, (rid, url, old_path) in enumerate(candidates):
            new_path = old_path.rsplit(".", 1)[0] + ".png"
            try:
                with httpx.Client(timeout=60.0, follow_redirects=True) as http:
                    resp = http.get(url)
                    resp.raise_for_status()
                    raw = resp.content

                png_bytes = normalize_image_bytes(raw)

                sb.storage.from_(bucket).upload(
                    new_path, png_bytes,
                    file_options={"content-type": "image/png", "upsert": "true"},
                )
                new_url = sb.storage.from_(bucket).get_public_url(new_path)

                sb.table(table).update({column: new_url}).eq("id", rid).execute()

                try:
                    if new_path != old_path:
                        sb.storage.from_(bucket).remove([old_path])
                except Exception as e:
                    print(f"    [warn] could not delete old {old_path}: {e}")

                ok += 1
                print(f"  [{i+1}/{len(candidates)}] {table}.{rid}: {old_path} -> {new_path}")
            except Exception as e:
                failed += 1
                print(f"  [{i+1}/{len(candidates)}] FAILED {table}.{rid} ({old_path}): {e}")

            if (i + 1) % 10 == 0:
                time.sleep(0.5)
            else:
                time.sleep(0.1)

        print(f"  done: {ok} converted, {failed} failed")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="Print what would change without writing")
    args = p.parse_args()

    print(f"{'DRY RUN' if args.dry_run else 'LIVE RUN'} — migrating non-PNG image rows")
    migrate(args.dry_run)


if __name__ == "__main__":
    main()
