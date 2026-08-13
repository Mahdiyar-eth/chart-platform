# Chart Platform — FastAPI web app + ARQ worker (same image, different CMD)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: weasyprint (PDF rendering) + psycopg2 (libpq)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b \
    libgdk-pixbuf-2.0-0 libcairo2 libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8767

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8767", \
     "--proxy-headers", "--forwarded-allow-ips=127.0.0.1", "--workers", "2", "--no-access-log"]
