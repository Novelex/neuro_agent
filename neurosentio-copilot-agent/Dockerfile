# ──────────────────────────────────────────────
# NeuroSentio Copilot Agent — Hardened Dockerfile
# ──────────────────────────────────────────────
FROM python:3.12-slim

# Set environment defaults
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Set working directory
WORKDIR /app

# Install system dependencies (curl for healthchecks, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies first (layer cache optimisation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and scripts
COPY . .

# Copy and configure entrypoint
RUN chmod +x entrypoint.sh

# Expose FastAPI port
EXPOSE 8000

# Set entrypoint to run migrations automatically
ENTRYPOINT ["/app/entrypoint.sh"]

# Run the server (can be overridden in docker-compose.yml or Render/Koyeb)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

