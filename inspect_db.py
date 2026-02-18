import sqlite3
import os

db_path = "ugc_saas.db"
if not os.path.exists(db_path):
    print("Database not found")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("--- Influencers ---")
cursor.execute("SELECT id, name FROM influencers")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Name: {row[1]}")

print("\n--- App Clips ---")
cursor.execute("SELECT id, name FROM app_clips")
for row in cursor.fetchall():
    print(f"ID: {row[0]}, Name: {row[1]}")

conn.close()
