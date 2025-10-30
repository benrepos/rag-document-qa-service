# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for PDF processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port (Cloud Run uses 8080, local dev uses 8000)
EXPOSE 8000 8080

# Health check (using urllib, no extra dependencies)
# Uses PORT env var, defaults to 8000 for local dev
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.getenv(\"PORT\", \"8000\")}/', timeout=5)"

# Run with production settings
# Use PORT environment variable (Cloud Run sets this to 8080)
CMD uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1

