import requests
import config

def create_ultra_batch():
    print("🚀 Creating Ultra-Realistic 15s test records for Meg and Max...")
    url = f"{config.AIRTABLE_API_URL}/{config.TABLE_CONTENT_CALENDAR}"
    headers = config.AIRTABLE_HEADERS
    
    records = [
        {
            "fields": {
                "Influencer Name": "Meg",
                "Hook": "¡Tío, no te lo vas a creer! He encontrado la manera más BARATA de viajar este año.",
                "AI Assistant": "Travel",
                "Theme": "budget travel hacks",
                "Caption": "Naiara me ha ahorrado una pasta en mi próximo viaje a Madrid. ¡Brutal!",
                "Length": "15s",
                "Status": "Ready"
            }
        },
        {
            "fields": {
                "Influencer Name": "Max",
                "Hook": "¡Oye, PARA TODO! Si compras online habitualmente, tienes que ver esto.",
                "AI Assistant": "Shop",
                "Theme": "online shopping savings",
                "Caption": "He ahorrado un 40% en tecnología usando Max. De verdad, es flipante.",
                "Length": "15s",
                "Status": "Ready"
            }
        }
    ]
    
    for record in records:
        resp = requests.post(url, headers=headers, json=record)
        if resp.status_code == 200:
            print(f"✅ Success: Created record for {record['fields']['Influencer Name']} (ID {resp.json()['id']})")
        else:
            print(f"❌ Failed for {record['fields']['Influencer Name']}: {resp.text}")

if __name__ == "__main__":
    create_ultra_batch()
