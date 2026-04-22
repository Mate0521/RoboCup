FROM python:3.10-slim

WORKDIR /app

COPY config/requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY config/ /app/config/

ENV PYTHONPATH=/app/src

CMD ["python", "src/main.py"]