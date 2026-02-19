
import os
from dotenv import load_dotenv
load_dotenv(".env.saas")

from ugc_db.db_manager import list_products, get_supabase

print("--- Testing Database: list_products ---")
try:
    products = list_products()
    print(f"✅ Success! Found {len(products)} products.")
    print(products)
except Exception as e:
    print(f"❌ Database Error: {e}")

print("\n--- Testing Storage: product-images bucket ---")
try:
    sb = get_supabase()
    bucket_name = "product-images"
    # Try to list files in bucket (or just check if it exists via a dummy op)
    files = sb.storage.from_(bucket_name).list()
    print(f"✅ Success! Bucket '{bucket_name}' is accessible.")
except Exception as e:
    print(f"❌ Storage Error: {e}")

print("\n--- Testing Database: create_product ---")
try:
    from ugc_db.db_manager import create_product, delete_product
    test_data = {
        "name": "DEBUG_TEST_PRODUCT",
        "image_url": "https://example.com/test.jpg",
        "category": "Debug"
    }
    created = create_product(test_data)
    if created:
        print(f"✅ Create Success! Created: {created['id']}")
        # Clean up
        delete_product(created['id'])
        print("✅ Cleanup Success (Deleted test product)")
    else:
        print("❌ Create Failed: returned None (likely RLS or Schema issue)")
except Exception as e:
    print(f"❌ Create Error: {e}")
