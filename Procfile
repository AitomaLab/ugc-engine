web: PYTHONPATH=. uvicorn app:app --host 0.0.0.0 --port $PORT
worker: PYTHONPATH=. celery -A ugc_worker.tasks worker --loglevel=info
