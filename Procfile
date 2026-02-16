web: PYTHONPATH=. uvicorn app:app --host 0.0.0.0 --port $PORT
worker: PYTHONPATH=. celery -A worker.tasks worker --loglevel=info
