FROM python:3.10-slim

WORKDIR /app

COPY config/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src/ /app/src/
COPY config/ /app/config/

CMD ["python", "src/main.py"]