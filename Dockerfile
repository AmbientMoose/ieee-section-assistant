# IEEE Section Operations Assistant - container image
FROM python:3.12-slim

# Keep Python output unbuffered; no .pyc; no pip cache bloat.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source.
COPY . .

# The index is built on first request (or mount a volume at /app/data to persist
# it across restarts). Streamlit serves on 8501.
EXPOSE 8501

# Container health: Streamlit's built-in health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
