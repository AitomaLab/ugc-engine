import airtable_client
import config
import requests
import json

def create_test_records():
    print("=== CREATING TEST RECORDS ===")
    
    records = [
        {
            "fields": {
                "Hook": "Esta app me ahorró horas planeando mi viaje a Madrid, ¡tienes que probarla!",
                "AI Assistant": "Travel",
                "Theme": "viaje a España",
                "Caption": "Naiara es la mejor asistente de viajes. ¡Descárgala ya!",
                "Influencer Name": "Meg",
                "Length": "30s",
                "Status": "Ready"
            }
        },
        {
            "fields": {
                "Hook": "Encontré las mejores ofertas en tecnología usando esta app, es una pasada.",
                "AI Assistant": "Shop",
                "Theme": "compras inteligentes",
                "Caption": "Ahorra dinero en tus compras con Max. ¡Enlace en bio!",
                "Influencer Name": "Max",
                "Length": "30s",
                "Status": "Ready"
            }
        }
    ]
    
    url = f"{config.AIRTABLE_API_URL}/{config.TABLE_CONTENT_CALENDAR.replace(' ', '%20')}"
    resp = requests.post(url, headers=config.AIRTABLE_HEADERS, json={"records": records})
    if resp.status_code == 200:
        print(f"  Successfully created {len(records)} records.")
    else:
        print(f"  Error creating records: {resp.status_code}")
        print(resp.json())

if __name__ == "__main__":
    create_test_records()
