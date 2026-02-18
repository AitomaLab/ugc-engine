import sqlite3
import os

db_path = "ugc_saas.db"
if not os.path.exists(db_path):
    print("Database not found")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Last 5 Video Jobs ---")
cursor.execute("SELECT id, status, error_message, created_at FROM video_jobs ORDER BY created_at DESC LIMIT 5")
rows = cursor.fetchall()
for row in rows:
    print(f"ID: {row[0]}")
    print(f"Status: {row[1]}")
    print(f"Error: {row[2]}")
    print(f"Created: {row[3]}")
    print("-" * 20)

print("\n--- Influencer Image URLs ---")
cursor.execute("SELECT name, reference_image_url FROM influencers")
rows = cursor.fetchall()
for row in rows:
    print(f"Name: {row[0]}")
    print(f"URL: {row[1]}")

conn.close()
