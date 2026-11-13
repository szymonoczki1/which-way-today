FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # SQLite lives on a volume mounted at /data (see docker-compose.yml).
    DATABASE_URL=sqlite:////data/whichway.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Non-root user. /data is created and owned here so a fresh named volume,
# which Docker initialises from the image's directory, is writable by it.
RUN useradd --create-home --uid 10001 app \
    && mkdir /data \
    && chown app:app /data
USER app

EXPOSE 8000

# python:slim has no curl; urllib is enough for a liveness probe.
# --start-interval: probe every 1 s during start-up so the frontend (which waits
# for "healthy") isn't held back by the 10 s steady-state interval.
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --start-interval=1s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
