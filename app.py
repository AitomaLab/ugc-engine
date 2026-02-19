import os
from dotenv import load_dotenv

# Load SaaS production environment if present
load_dotenv(".env.saas")
import sys
from pathlib import Path

# Force the project root into the path
root_dir = str(Path(__file__).parent.absolute())
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from ugc_backend.main import app

if __name__ == "__main__":
    import uvicorn
    # Use the port provided by Railway or fallback to 8000
    port = int(os.environ.get("PORT", 8000))
    # Enable reload for better development experience
    uvicorn.run("ugc_backend.main:app", host="0.0.0.0", port=port, reload=True)
