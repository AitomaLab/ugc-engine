from backend.main import app
import os

if __name__ == "__main__":
    import uvicorn
    # Use the port provided by Railway or fallback to 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
