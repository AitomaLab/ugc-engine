
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

import scene_builder
import config

def test_physical_product_flow():
    print("🧪 Testing Physical Product Scene Building...")

    # Mock Data
    mock_content = {
        "Hook": "This cream saved my skin!",
        "AI Assistant": "Beauty",
        "Theme": "Skincare routine",
        "Caption": "Get that glow! Link in bio.",
        "Length": "15s",
    }
    
    mock_inf = {
        "name": "Sofia",
        "age": "25-year-old",
        "gender": "Female",
        "visual_description": "glowing skin, casual white robe",
        "personality": "friendly beauty guru",
        "energy_level": "High",
        "accent": "American English",
        "tone": "Enthusiastic",
        "reference_image_url": "https://example.com/sofia.jpg",
        "elevenlabs_voice_id": "12345"
    }

    mock_product = {
        "name": "GlowUp Moisturizer",
        "description": "A hydrating face cream with vitamin C",
        "image_url": "https://example.com/product.png",
        "category": "Beauty"
    }

    # Build Scenes
    scenes = scene_builder.build_scenes(
        content_row=mock_content,
        influencer=mock_inf,
        app_clip=None, # No app clip for physical
        product=mock_product
    )

    # Verify
    print(f"\n✅ Generated {len(scenes)} scenes.")
    
    has_error = False
    for i, scene in enumerate(scenes, 1):
        print(f"\n🎬 Scene {i}: {scene['name']}")
        print(f"   Type: {scene['type']}")
        print(f"   Prompt: {scene['prompt'][:100]}...")
        
        if scene["type"] != "physical_composite":
            print(f"   ❌ ERROR: Expected type 'physical_composite', got '{scene['type']}'")
            has_error = True
            
        if "GlowUp Moisturizer" not in scene["prompt"]:
            print(f"   ❌ ERROR: Product name not found in prompt")
            has_error = True
            
        if scene["product_image_url"] != mock_product["image_url"]:
            print(f"   ❌ ERROR: Product image URL mismatch")
            has_error = True

    if not has_error:
        print("\n✨ Physical Product Flow Verification PASSED!")
    else:
        print("\n❌ Verification FAILED.")

if __name__ == "__main__":
    test_physical_product_flow()
