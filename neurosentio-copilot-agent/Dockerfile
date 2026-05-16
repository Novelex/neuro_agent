# ──────────────────────────────────────────────
# NeuroSentio Copilot Agent — Dockerfile
# ──────────────────────────────────────────────
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy and install dependencies first (layer cache optimisation)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Run the server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
