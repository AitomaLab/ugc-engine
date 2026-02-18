from dotenv import load_dotenv
load_dotenv(".env.saas")
from ugc_db.db_manager import get_influencer

ID = "79a5ebec-aea1-4791-9dd2-e3709a39c073"

print(f"🔎 Fetching Influencer ID: {ID}")
inf = get_influencer(ID)

if inf:
    print(f"✅ Found: {inf['name']}")
    print(f"   Image URL: '{inf.get('image_url')}'")
    print(f"   Type of Image URL: {type(inf.get('image_url'))}")
else:
    print("❌ Not found!")
