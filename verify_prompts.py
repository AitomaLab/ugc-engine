import scene_builder
import json

content = {
    "Hook": "Esta app es increíble",
    "AI Assistant": "Travel",
    "Theme": "beach vacation",
    "Caption": "Download now",
    "Length": "15s"
}
inf = {
    "name": "Sofia",
    "description": "A woman",
    "reference_image_url": "https://example.com/ref.jpg",
    "gender": "Female",
    "accent": "Castilian Spanish (Spain)",
    "tone": "Enthusiastic"
}
clip = {"video_url": "url"}

scenes = scene_builder.build_scenes(content, inf, clip)
print(json.dumps(scenes[0]["prompt"], indent=2, ensure_ascii=False))
