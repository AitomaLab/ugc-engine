FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PORT=8000

# Expose port (for web process)
EXPOSE 8000

# Run command is specified in Procfile or via docker-compose
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
