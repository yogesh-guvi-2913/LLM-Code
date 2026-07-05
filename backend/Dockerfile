FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install -r requirements.txt

RUN playwright install chromium --with-deps

COPY backend/ /app/
COPY sandbox/sdk/python/flash/ /app/flash_sdk/flash/

ENV PYTHONPATH="/app/flash_sdk:${PYTHONPATH}"

EXPOSE 7000

CMD ["sh", "-c", "uvicorn app.app:app --host 0.0.0.0 --port 7000"]
