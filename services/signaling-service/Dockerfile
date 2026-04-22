FROM python:3.11-slim

WORKDIR /app

COPY services/signaling-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/shared /app/shared
COPY services/signaling-service/app /app/app

EXPOSE 8001

ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
