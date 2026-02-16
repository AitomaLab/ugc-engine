import airtable_client
import config
import scene_builder
import json

def debug_prompts():
    # Fetch content
    records = airtable_client.get_ready_items()
    if not records:
        print("No ready items found.")
        return

    for rec in records:
        fields = rec["fields"]
        influencer_name = fields.get("Influencer Name", "Meg")
        influencer = airtable_client.get_influencer(influencer_name)
        app_clip = airtable_client.get_app_clip(fields.get("AI Assistant", "Shop"))
        
        scenes = scene_builder.build_scenes(fields, influencer, app_clip)
        
        for i, scene in enumerate(scenes):
            if scene["type"] == "veo":
                prompt = scene["prompt"]
                print(f"\n--- Project: {fields.get('Hook')[:30]}... ---")
                print(f"Scene {i+1} ({scene['name']})")
                print(f"Prompt Length: {len(prompt)}")
                print(f"Prompt: {prompt}")

if __name__ == "__main__":
    debug_prompts()
