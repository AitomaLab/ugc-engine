"""
Create 6 new Content Calendar entries with Spanish hooks.
- 3 hooks for Travel AI assistant
- 3 hooks for Shop AI assistant
- Distributed across both influencers (Meg + Max)
- All 15-second format
- Status: Draft (for user review before generating)
"""
import requests
import config

url = f"{config.AIRTABLE_API_URL}/Content Calendar"

hooks = [
    # --- TRAVEL hooks (3) ---
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
        "Influencer Name": "Max",
        "AI Assistant": "Travel",
        "Hook": "Le di mi presupuesto y en 10 segundos me armó el viaje perfecto a Roma",
        "Caption": "Tu asistente de viajes con inteligencia artificial",
        "Length": "15s",
        "Status": "Draft",
    },

    # --- SHOP hooks (3) ---
    {
        "Influencer Name": "Max",
        "AI Assistant": "Shop",
        "Hook": "Encontré las zapatillas que buscaba al mejor precio en 5 segundos con esta app",
        "Caption": "Compra inteligente con Naiara — tu asistente de shopping con IA",
        "Length": "15s",
        "Status": "Draft",
    },
    {
        "Influencer Name": "Meg",
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

print("📝 Creating 6 hooks in Content Calendar...\n")

created = 0
for i, hook in enumerate(hooks, 1):
    resp = requests.post(url, headers=config.AIRTABLE_HEADERS, json={"fields": hook})
    if resp.status_code == 200:
        record_id = resp.json()["id"]
        print(f"  ✅ {i}/6 | {hook['Influencer Name']:4s} | {hook['AI Assistant']:6s} | {hook['Hook'][:60]}")
        created += 1
    else:
        print(f"  ❌ {i}/6 | Failed: {resp.status_code} | {resp.text[:200]}")

print(f"\n{'='*60}")
print(f"✅ Created {created}/6 hooks (Status: Draft)")
print(f"   Change Status to 'Ready' on the ones you want to generate.")
