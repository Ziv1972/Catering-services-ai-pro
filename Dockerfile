FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir aiosqlite

# Copy backend code
COPY backend/ ./backend/
COPY scripts/ ./scripts/

# Create uploads directory
RUN mkdir -p uploads/menus

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Start command - Railway provides $PORT
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
