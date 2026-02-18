import requests
r = requests.get('http://localhost:8000/influencers')
data = r.json()
print(f"Influencers ({len(data)}):")
for i in data:
    print(f"  {i['name']} | image: {str(i.get('image_url','none'))[:60]} | voice: {i.get('elevenlabs_voice_id','none')}")

r2 = requests.get('http://localhost:8000/app-clips')
data2 = r2.json()
print(f"\nApp Clips ({len(data2)}):")
for c in data2:
    print(f"  {c['name']} | video: {str(c.get('video_url','none'))[:60]}")

r3 = requests.get('http://localhost:8000/scripts')
data3 = r3.json()
print(f"\nScripts ({len(data3)}):")
for s in data3:
    print(f"  {s['text'][:60]}...")

r4 = requests.get('http://localhost:8000/stats')
print(f"\nStats: {r4.json()}")
