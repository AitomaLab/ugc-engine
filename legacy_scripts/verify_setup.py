import os
import sys
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv('.agent/.env')

# Get credentials
AIRTABLE_TOKEN = os.getenv('AIRTABLE_TOKEN')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')

if not AIRTABLE_TOKEN or not AIRTABLE_BASE_ID:
    print("❌ ERROR: Missing API keys in .env file")
    sys.exit(1)

# Check Airtable connection
print("🔍 Checking Airtable connection...")
headers = {
    'Authorization': f'Bearer {AIRTABLE_TOKEN}',
    'Content-Type': 'application/json'
}

try:
    # Try to list tables in the base
    url = f'https://api.airtable.com/v0/meta/bases/{AIRTABLE_BASE_ID}/tables'
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        tables = data.get('tables', [])
        
        print(f"✅ Connected to Airtable base: {AIRTABLE_BASE_ID}")
        print(f"\n📊 Found {len(tables)} table(s):")
        
        scenes_table_found = False
        for table in tables:
            table_name = table.get('name', 'Unknown')
            table_id = table.get('id', '')
            print(f"  • {table_name} (ID: {table_id})")
            
            if table_name.lower() == 'scenes':
                scenes_table_found = True
                print(f"\n✅ Found 'Scenes' table!")
        
        if not scenes_table_found:
            print("\n⚠️ WARNING: 'Scenes' table not found!")
    else:
        print(f"❌ Error connecting to Airtable: {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {str(e)}")
    sys.exit(1)
