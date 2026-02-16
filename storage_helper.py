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
    Note: Files are deleted after 60 minutes.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    print(f"   ☁️ Uploading to temporary storage...")
    
    url = "https://tmpfiles.org/api/v1/upload"
    with open(file_path, 'rb') as f:
        files = {'file': f}
        resp = requests.post(url, files=files)
    
    if resp.status_code != 200:
        raise RuntimeError(f"Upload failed ({resp.status_code}): {resp.text}")

    # Example response: {"status":"success","data":{"url":"https://tmpfiles.org/12345/filename"}}
    data = resp.json()
    if data.get("status") != "success":
        raise RuntimeError(f"Upload error: {data}")

    # The API returns the viewing URL, but InfiniteTalk needs the DIRECT download link.
    # tmpfiles.org direct link pattern: https://tmpfiles.org/dl/12345/filename
    viewing_url = data["data"]["url"]
    direct_url = viewing_url.replace("https://tmpfiles.org/", "https://tmpfiles.org/dl/")
    
    print(f"      🔗 Public URL: {direct_url}")
    return direct_url

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
