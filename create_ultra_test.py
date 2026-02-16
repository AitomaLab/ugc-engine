import requests
import config

def create_ultra_test():
    print("🚀 Creating Ultra-Realistic test record for Max...")
    url = f"{config.AIRTABLE_API_URL}/{config.TABLE_CONTENT_CALENDAR}"
    headers = config.AIRTABLE_HEADERS
    
    data = {
        "fields": {
            "Influencer Name": "Max",
            "Hook": "¡No vas a creer los precios que he encontrado para este móvil!",
            "AI Assistant": "Shop",
            "Theme": "gadget shopping",
            "Caption": "Max me ha ahorrado 200 euros en un iPhone. Tienes que probarlo.",
            "Length": "15s",
            "Status": "Ready"
        }
    }
    
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code == 200:
        print(f"✅ Success: Record created with ID {resp.json()['id']}")
    else:
        print(f"❌ Failed: {resp.text}")

if __name__ == "__main__":
    create_ultra_test()
