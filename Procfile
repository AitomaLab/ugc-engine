web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
worker: celery -A worker.tasks worker --loglevel=info
