"""
Naiara Content Distribution Engine — Storage Helper

Provides temporary public hosting for assets using tmpfiles.org.
Used to give Kie.ai access to ElevenLabs audio files.
"""
import requests
import os

def upload_temporary_file(file_path):
    """
    Upload a local file to tmpfiles.org.
    Returns the direct download URL.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    print(f"   ☁️ Uploading to temporary storage (tmpfiles.org)...")
    
    url = "https://tmpfiles.org/api/v1/upload"
    with open(file_path, 'rb') as f:
        files = {'file': f}
        resp = requests.post(url, files=files)
    
    if resp.status_code != 200:
        raise RuntimeError(f"Upload failed ({resp.status_code}): {resp.text}")

    data = resp.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Upload error: {data}")

    # The API returns the viewing URL: https://tmpfiles.org/12345/filename
    # We need the DIRECT download link: https://tmpfiles.org/dl/12345/filename
    viewing_url = data["data"]["url"]
    direct_url = viewing_url.replace("tmpfiles.org/", "tmpfiles.org/dl/")
    
    # Force HTTPS and strip
    direct_url = direct_url.strip().replace("http://", "https://")
    
    print(f"      🔗 Public URL: {direct_url}")
    return direct_url

def upload_to_supabase_storage(file_path, bucket="generated-videos", destination_path=None):
    """
    Upload a local file to Supabase Storage.
    Returns the public URL for the uploaded file.
    """
    from ugc_db.db_manager import get_supabase
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    sb = get_supabase()
    if not destination_path:
        destination_path = os.path.basename(file_path)

    with open(file_path, "rb") as f:
        file_data = f.read()

    # Upload (upsert to overwrite if exists)
    sb.storage.from_(bucket).upload(
        destination_path,
        file_data,
        {"content-type": "video/mp4", "upsert": "true"},
    )

    supabase_url = os.getenv("SUPABASE_URL", "")
    public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{destination_path}"
    print(f"      ☁️ Uploaded to Supabase Storage: {public_url}")
    return public_url


if __name__ == "__main__":
    # Test upload
    test_file = "test.txt"
    with open(test_file, "w") as f:
        f.write("test")
    try:
        url = upload_temporary_file(test_file)
        print(f"Test success: {url}")
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
