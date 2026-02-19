
import requests
import json
import time

BASE_URL = "http://localhost:8000"

print(f"--- Testing API: {BASE_URL} ---")

# 1. Test GET Products
print("\n1. GET /api/products")
try:
    r = requests.get(f"{BASE_URL}/api/products")
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
except Exception as e:
    print(f"❌ GET Failed: {e}")

# 2. Test POST Product
print("\n2. POST /api/products")
payload = {
    "name": "API_TEST_PRODUCT",
    "image_url": "https://pub-f4c0df2e98a141a2884b2a3a8309c856.r2.dev/test_product.jpg",
    "category": "Test"
}
try:
    r = requests.post(f"{BASE_URL}/api/products", json=payload)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
    
    if r.status_code == 200:
        new_id = r.json().get("id")
        print(f"✅ Created Product ID: {new_id}")
        
        # 3. Verify it appears in List
        print("\n3. Verify in List")
        r2 = requests.get(f"{BASE_URL}/api/products")
        products = r2.json()
        found = any(p['id'] == new_id for p in products)
        if found:
            print("✅ Product found in list!")
            
            # 4. Cleanup
            print("\n4. DELETE Product")
            r3 = requests.delete(f"{BASE_URL}/api/products/{new_id}")
            print(f"Delete Status: {r3.status_code}")
        else:
            print("❌ Product created but NOT found in list!")
    else:
        print("❌ POST Failed")

except Exception as e:
    print(f"❌ POST Exception: {e}")
