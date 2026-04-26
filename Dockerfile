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
# scripts/ are dev-only utilities (migrations, exports) — not needed at runtime.
# Removed to unblock Railway builds that were failing on cache-key mismatch.

# Create uploads directories
RUN mkdir -p uploads/menus uploads/attachments

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Start command - Railway provides $PORT
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
