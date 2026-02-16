"""
Fix Content Calendar by re-creating hooks with correct influencer/category mapping.
Categories:
- Meg -> Travel
- Max -> Shop
"""
import requests
import config

url = f"{config.AIRTABLE_API_URL}/Content Calendar"

# 1. Delete all current 'Draft' items to clean up
print("🧹 Cleaning up Draft items...")
resp = requests.get(url, headers=config.AIRTABLE_HEADERS, params={"filterByFormula": "{Status} = 'Draft'"})
if resp.status_code == 200:
    records = resp.json().get("records", [])
    for r in records:
        requests.delete(f"{url}/{r['id']}", headers=config.AIRTABLE_HEADERS)
        print(f"  Deleted: {r['id']}")

# 2. Re-create with correct mapping
hooks = [
    # --- TRAVEL (Meg) ---
    {
        "Influencer Name": "Meg",
        "AI Assistant": "Travel",
        "Hook": "¡Esta app me organizó un viaje completo a Barcelona en 30 segundos!",
        "Caption": "Naiara es el asistente de viajes que no sabías que necesitabas",
        "Length": "15s",
        "Status": "Draft",
    },
    {
        "Influencer Name": "Meg",
        "AI Assistant": "Travel",
        "Hook": "Quería ir a Japón pero no tenía idea por dónde empezar... hasta que encontré esta app",
        "Caption": "Planifica tu viaje soñado en segundos con Naiara",
        "Length": "15s",
        "Status": "Draft",
    },
    {
        "Influencer Name": "Meg",
        "AI Assistant": "Travel",
        "Hook": "Le di mi presupuesto y en 10 segundos me armó el viaje perfecto a Roma",
        "Caption": "Tu asistente de viajes con inteligencia artificial",
        "Length": "15s",
        "Status": "Draft",
    },

    # --- SHOP (Max) ---
    {
        "Influencer Name": "Max",
        "AI Assistant": "Shop",
        "Hook": "Encontré las zapatillas que buscaba al mejor precio en 5 segundos con esta app",
        "Caption": "Compra inteligente con Naiara — tu asistente de shopping con IA",
        "Length": "15s",
        "Status": "Draft",
    },
    {
        "Influencer Name": "Max",
        "AI Assistant": "Shop",
        "Hook": "¿Sabías que esta app compara precios en todas las tiendas por ti? ¡Mira esto!",
        "Caption": "Naiara te ayuda a encontrar los mejores precios en segundos",
        "Length": "15s",
        "Status": "Draft",
    },
    {
        "Influencer Name": "Max",
        "AI Assistant": "Shop",
        "Hook": "Me ahorré 40 euros en mi última compra gracias a esta app de IA",
        "Caption": "Ahorra dinero en cada compra con Naiara",
        "Length": "15s",
        "Status": "Draft",
    },
]

print("\n📝 Re-creating 6 hooks with correct mapping...")
for i, hook in enumerate(hooks, 1):
    resp = requests.post(url, headers=config.AIRTABLE_HEADERS, json={"fields": hook})
    if resp.status_code == 200:
        print(f"  ✅ {i}/6 | {hook['Influencer Name']:4s} | {hook['AI Assistant']:6s} | {hook['Hook'][:60]}")
    else:
        print(f"  ❌ {i}/6 | Failed: {resp.status_code}")

print("\nDone!")
