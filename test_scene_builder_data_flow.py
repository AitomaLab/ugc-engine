import scene_builder
import config

# Mimic data from tasks.py / test_generation_loop.py
influencer = {
    "name": "Meg",
    "reference_image_url": "https://example.com/meg.jpg", # Explicit test URL
    "image_url": "https://example.com/meg.jpg",
    "elevenlabs_voice_id": "123",
    # Add defaults scene_builder expects
    "age": "25", "gender": "Female", "visual_description": "desc",
    "personality": "nice", "energy_level": "High", "accent": "Spanish", "tone": "Happy"
}

content_row = {"Length": "15s", "Hook": "Hook", "AI Assistant": "Travel", "Theme": "Travel"}
app_clip = {"video_url": "http://clip.mp4", "duration": 5}

print("🧪 Testing build_scenes...")
scenes = scene_builder.build_scenes(content_row, influencer, app_clip)

scene1 = scenes[0]
print(f"Scene 1 Type: {scene1['type']}")
print(f"Scene 1 Ref Image: '{scene1.get('reference_image_url')}'")

if scene1.get("reference_image_url") == "https://example.com/meg.jpg":
    print("✅ Scene Builder correctly preserved the URL.")
else:
    print("❌ Scene Builder LOST the URL!")
