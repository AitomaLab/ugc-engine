"""
Create prompts and log scenes to Airtable for Naiara video clone
Based on detailed UGC video analysis provided by user
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import requests

# Load environment
load_dotenv('.agent/.env')
AIRTABLE_TOKEN = os.getenv('AIRTABLE_TOKEN')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')

headers = {
    'Authorization': f'Bearer {AIRTABLE_TOKEN}',
    'Content-Type': 'application/json'
}

PROJECT_NAME = "Naiara UGC Clone"

# Scene definitions based on user's detailed analysis
scenes = [
    {
        "scene": "Scene 1 - The Hook (Airplane)",
        "start_image_prompt": """A young female influencer standing in an airplane aisle, POV high-angle shot looking down. She's holding a passport in her right hand, wearing casual travel clothes. Bright overhead airplane cabin lighting with diagonal shadows on the floor. Airplane seats visible on sides. Clean, modern, photorealistic style. 9:16 vertical aspect ratio.""",
        "video_prompt": """Slight natural hand movement showing the passport. Camera is steady, POV perspective. Bright cabin lighting. Subtle movement only."""
    },
    {
        "scene": "Scene 2 - Naiara App Home Screen",
        "start_image_prompt": """Mobile phone screen showing Naiara travel app home screen. Clean modern UI with light background. Top shows travel destination images. Center has three colorful buttons: 'New trip', 'Enter code', 'Discover places'. Each button has 3D icon. Professional app design, naiara.jpeg app screenshot as reference. 9:16 vertical.""",
        "video_prompt": """Static screen display, maybe slight finger tap animation on 'New trip' button. Clean, professional app interface."""
    },
    {
        "scene": "Scene 3 - Destination Selection",
        "start_image_prompt": """Naiara app screen titled 'Where are we going?'. Vertical list of countries with flags: Spain (Barcelona, Madrid), France, Italy, Japan (selected with checkmark). Each entry shows flag and city count. Clean white background, modern typography. Naiara branding. 9:16 vertical.""",
        "video_prompt": """Finger taps on Japan entry, checkmark appears. Smooth tap animation, professional UI interaction."""
    },
    {
        "scene": "Scene 4 - Kyoto Attractions",
        "start_image_prompt": """Naiara app screen 'Choose spots in Kyoto'. Scrollable list of attractions: Fushimi Inari Shrine, Kinkaku-ji Temple, Arashiyama Bamboo Grove (all checked). Each has thumbnail photo and description. Clean layout, professional travel app design. 9:16 vertical.""",
        "video_prompt": """Screen scrolls smoothly through the list of attractions. Checkmarks are visible. Smooth scrolling animation."""
    },
    {
        "scene": "Scene 5 - Trip Duration Selector",
        "start_image_prompt": """Naiara app screen asking 'How long are you staying?'. Large scrollable number wheel in center showing '14'. Numbers above and below are slightly blurred. Modern app UI, clean design. Naiara branding at top. 9:16 vertical.""",
        "video_prompt": """Number wheel scrolls from 10 to 14, settling on 14. Smooth iOS-style picker animation."""
    },
    {
        "scene": "Scene 6 - AI Optimization Prompt",
        "start_image_prompt": """Naiara app modal popup: 'Let Naiara AI optimize your trip?'. Shows simplified map with illustrated route connecting landmarks. Two buttons: 'Yes, plan for me!' (highlighted) and 'I'll do it myself'. Map shows iconic locations connected by dotted lines. 9:16 vertical.""",
        "video_prompt": """Finger taps 'Yes, plan for me!' button. Button changes to 'Optimizing...' with loading spinner. Smooth button press animation."""
    },
    {
        "scene": "Scene 7 - Generated 14-Day Itinerary Map",
        "start_image_prompt": """Naiara app showing '14-Day Kyoto Trip' itinerary. Top half: map of Japan with colored route pins across Kyoto-Tokyo-Osaka. Bottom half: scrollable day-by-day schedule with dates and locations. Professional travel planning interface. 9:16 vertical.""",
        "video_prompt": """Map smoothly zooms out from Kyoto city view to full Japan regional view. Route pins become visible. Elegant zoom animation."""
    },
    {
        "scene": "Scene 8 - Location Details",
        "start_image_prompt": """Naiara app location detail page for 'Arashiyama Bamboo Grove'. High-quality photo of bamboo forest at top, 4.8-star rating, description text, 'Community Tips' section with traveler notes. Professional travel guide layout. 9:16 vertical.""",
        "video_prompt": """Smooth scroll through the location page, showing photo, rating, and community tips. Professional app interaction."""
    }
]

print("🎬 Creating Naiara Video Clone Prompts")
print("=" * 60)
print(f"Project: {PROJECT_NAME}")
print(f"Total Scenes: {len(scenes)}")
print()

# Log scenes to Airtable
url = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Scenes'

for i, scene in enumerate(scenes, 1):
    print(f"Scene {i}: {scene['scene']}")
    
    data = {
        "fields": {
            "Project Name": PROJECT_NAME,
            "scene": scene["scene"],
            "start_image_prompt": scene["start_image_prompt"],
            "video_prompt": scene["video_prompt"]
        }
    }
    
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        print(f"  ✅ Logged to Airtable")
    else:
        print(f"  ⚠️ Failed to log: {response.text}")
    print()

print("=" * 60)
print("✅ All scenes created and logged to Airtable!")
print()
print("📋 CHECKPOINT: Review the scene breakdown")
print("Next steps:")
print("  1. Generate images ($0.09 × 8 = $0.72)")
print("  2. Generate videos ($0.28 × 8 = $2.24)")
print("  Total estimated cost: ~$3.00")
