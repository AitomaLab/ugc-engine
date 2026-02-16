"""
Naiara Content Distribution Engine — Main Pipeline

The "run" button. Fetches ready items from Airtable, generates all scenes
using Veo 3.1 Fast, assembles the final UGC video, and uploads it back.

Usage:
    python pipeline.py --single          # Process one video
    python pipeline.py --batch           # Process all ready items
    python pipeline.py --dry-run         # Show what would happen (no API calls)
    python pipeline.py --no-music        # Skip music generation (saves $0.10)
"""
import sys
import json
import time
from datetime import datetime
from pathlib import Path

import config
import airtable_client
import scene_builder
import generate_scenes
import subtitle_engine
import assemble_video
import elevenlabs_client
import storage_helper
import core_engine


def process_single(record, skip_music=False, dry_run=False):
    """
    Process a single Content Calendar record into a finished UGC video.

    Args:
        record: Airtable record dict with 'id' and 'fields'
        skip_music: If True, don't generate background music
        dry_run: If True, show the plan but don't call any paid APIs

    Returns:
        Path to the final video, or None if dry run
    """
    record_id = record["id"]
    fields = record["fields"]
    hook = fields.get("Hook", "Check this out!")
    influencer_name = fields.get("Influencer Name") or fields.get("Influencer", "Sofia")
    assistant_type = fields.get("AI Assistant", "Travel")
    length = fields.get("Length", "15s")
    if length not in config.VALID_LENGTHS:
        length = "15s"

    # Create a clean project name for this video
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_name = f"{influencer_name.lower()}_{length}_{timestamp}"

    print(f"\n{'#'*60}")
    print(f"# 🎬 GENERATING VIDEO: {project_name}")
    print(f"# Hook: \"{hook[:50]}...\"")
    print(f"# Influencer: {influencer_name} | Assistant: {assistant_type} | Length: {length}")
    print(f"{'#'*60}")

    # ----- Step 1: Update status -----
    if not dry_run:
        airtable_client.update_status(record_id, "Generating")

    # ----- Step 2: Fetch influencer data -----
    print(f"\n📌 Step 1/6: Fetching influencer data...")
    # Prioritize category-based selection to ensure niche matching
    influencer = airtable_client.get_influencer_by_category(assistant_type)
    if not influencer:
        print(f"   ⚠️ Falling back to name-based lookup for '{influencer_name}'")
        influencer = airtable_client.get_influencer(influencer_name)
    
    if dry_run:
        # Just mock the description for brevity if needed, but keep the rest
        influencer["description"] = f"(dry-run) {influencer['description'][:100]}..."
    
    print(f"   ✅ Influencer: {influencer['name']} ({influencer.get('gender')}, {influencer.get('accent')})")

    # ----- Step 3: Fetch app clip -----
    print(f"\n📌 Step 2/6: Finding app clip...")
    app_clip_attachment = fields.get("App Clip")
    specific_url = None
    if app_clip_attachment and len(app_clip_attachment) > 0:
        specific_url = app_clip_attachment[0].get("url")

    if dry_run:
        app_clip = {
            "name": f"(mock) {assistant_type} demo",
            "video_url": "https://example.com/demo.mp4",
            "duration": 8,
        }
    else:
        app_clip = airtable_client.get_app_clip(assistant_type, specific_url)
    print(f"   ✅ App clip: {app_clip['name']}")

    # ----- Step 4: Build scene structure -----
    print(f"\n📌 Step 3/6: Building scene structure...")
    scenes = scene_builder.build_scenes(fields, influencer, app_clip)
    scene_builder.print_scene_summary(scenes, length)

    if dry_run:
        print("\n🏁 DRY RUN — stopping here. No API calls made.")
        # Mock scenes for summary
        for s in scenes:
            if s["type"] == "veo":
                print(f"      [DRY-RUN] Would generate ElevenLabs audio for: \"{s['subtitle_text'][:30]}...\"")
                print(f"      [DRY-RUN] Would upload to temp storage.")
                print(f"      [DRY-RUN] Would generate lip-sync video via {config.LIPSYNC_MODEL}")
        return None

    # ----- Step 5: Execute Core Generation Pipeline -----
    print(f"\n📌 Step 4/6: Running Core Engine (ElevenLabs + InfiniteTalk)...")
    
    try:
        def status_update(msg):
            airtable_client.update_status(record_id, msg)
        
        final_video_path = core_engine.run_generation_pipeline(
            project_name=project_name,
            influencer=influencer,
            app_clip=app_clip,
            fields=fields,
            status_callback=status_update,
            skip_music=skip_music
        )
        
        # We need the list of scenes for subtitles/cost calculation if we didn't return them
        # Re-generating them locally to match core_engine internal logic
        scenes = scene_builder.build_scenes(fields, influencer, app_clip)

    except Exception as e:
        print(f"   ❌ Core Engine Error: {e}")
        raise RuntimeError(f"Generation failed: {e}")

    # Step 6, 7, 8 are now handled or bypassed by the core engine's assembly
    # We just need to finalize Airtable logging
    final_path = Path(final_video_path)
    
    # Calculate total cost
    veo_scenes = sum(1 for s in scenes if s["type"] == "veo")
    # New hybrid cost: ElevenLabs (~$0.04) + LipSync ($0.60)
    clip_cost = 0.64 if config.ELEVENLABS_API_KEY else 0.28
    total_cost = (veo_scenes * clip_cost) + (0.10 if music_path else 0)
    
    # Log the final video in Generated Assets
    airtable_client.log_asset(
        content_title=project_name,
        scene_name="final",
        asset_type="Final Video",
        source_url=f"file://{final_path}",
        duration=config.get_max_duration(length),
        cost=total_cost,
        status="Ready"
    )

    # Link the final video to the Content Calendar record
    airtable_client.attach_final_video(record_id, f"file://{final_path}")

    # ----- Step 9: Upload to Airtable -----
    # NOTE: Airtable attachment upload requires the file to be hosted at a URL.
    # For now, we update status to "Review" — you can manually attach the file
    # or we can add a file-hosting step later (e.g., upload to S3/Cloudinary).
    print(f"\n📌 Updating Airtable status...")
    airtable_client.update_status(record_id, "Review")

    # Cleanup temp files
    assemble_video.cleanup_temp(project_name)

    print(f"\n{'='*60}")
    print(f"🎉 VIDEO COMPLETE: {final_path}")
    print(f"💰 Estimated cost: ${total_cost:.2f}")
    print(f"{'='*60}\n")

    return final_path


def run_batch(skip_music=False, dry_run=False, limit=None):
    """Process all 'Ready' items in the Content Calendar."""
    print("🚀 BATCH MODE: Processing all ready items...\n")

    items = airtable_client.get_ready_items(limit=limit)
    if not items:
        print("📭 No items with status 'Ready' found in Content Calendar.")
        return []

    results = []
    for i, record in enumerate(items, 1):
        hook = record["fields"].get("Hook", "?")
        print(f"\n{'━'*60}")
        print(f"📋 Item {i}/{len(items)}: \"{hook[:50]}...\"")
        print(f"{'━'*60}")

        try:
            result = process_single(record, skip_music=skip_music, dry_run=dry_run)
            results.append({"record_id": record["id"], "video": result, "status": "ok"})
        except Exception as e:
            print(f"\n❌ Error: {e}")
            results.append({"record_id": record["id"], "video": None, "status": f"error: {e}"})
            if not dry_run:
                try:
                    airtable_client.update_status(record["id"], "Ready")  # Reset
                except:
                    pass

    # Summary
    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n{'='*60}")
    print(f"📊 Batch complete: {ok}/{len(results)} videos generated")
    print(f"{'='*60}\n")

    return results


def main():
    """CLI entry point."""
    args = sys.argv[1:]

    dry_run = "--dry-run" in args
    skip_music = "--no-music" in args

    if not dry_run:
        if not config.validate():
            sys.exit(1)

    if "--batch" in args:
        run_batch(skip_music=skip_music, dry_run=dry_run)

    elif "--single" in args:
        items = airtable_client.get_ready_items(limit=1)
        if items:
            process_single(items[0], skip_music=skip_music, dry_run=dry_run)
        else:
            print("📭 No items with status 'Ready' found.")

    elif "--dry-run" in args:
        # Dry run — supports --length flag
        print("🏜️  DRY RUN MODE — no API calls will be made\n")

        length = "15s"
        for i, arg in enumerate(args):
            if arg == "--length" and i + 1 < len(args):
                length = args[i + 1]

        mock_record = {
            "id": "rec_dry_run",
            "fields": {
                "Hook": "This app just planned my entire trip in 30 seconds",
                "AI Assistant": "Travel",
                "Theme": "beach vacation planning",
                "Caption": "Naiara is the AI travel assistant you didn't know you needed. Download now!",
                "Influencer": "Sofia",
                "Length": length,
            }
        }
        process_single(mock_record, skip_music=skip_music, dry_run=True)

    else:
        print("""
Naiara Content Distribution Engine
====================================

Usage:
    python pipeline.py --single          Process the next 'Ready' item
    python pipeline.py --batch           Process ALL 'Ready' items
    python pipeline.py --dry-run         Show plan without API calls (default: 15s)
    python pipeline.py --dry-run --length 30s   Dry-run a 30-second video
    python pipeline.py --no-music        Skip music generation ($0.10 savings)

Combine flags:
    python pipeline.py --batch --no-music
    python pipeline.py --single --dry-run
        """)


if __name__ == "__main__":
    main()
