"""
Naiara Content Distribution Engine — Storage Helper

Provides temporary public hosting for assets using tmpfiles.org.
Used to give Kie.ai access to ElevenLabs audio files.
"""
import requests
import os

def upload_temporary_file(file_path):
    """
    Upload a local file to Supabase instead of tmpfiles.org (which blocks bots).
    Returns the direct download URL.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    print(f"   ☁️ Uploading to temporary storage (Supabase)...")
    
    # Use a 'temp/' prefix so we can clean these up later if we want
    filename = os.path.basename(file_path)
    # Add a timestamp to avoid collisions
    import time
    dest_path = f"temp/{int(time.time())}_{filename}"
    
    public_url = upload_to_supabase_storage(file_path, bucket="generated-videos", destination_path=dest_path)
    print(f"      🔗 Public URL: {public_url}")
    return public_url

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

    # Auto-detect content type from file extension
    import mimetypes
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = "application/octet-stream"

    # Upload (upsert to overwrite if exists)
    sb.storage.from_(bucket).upload(
        destination_path,
        file_data,
        {"content-type": content_type, "upsert": "true"},
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
