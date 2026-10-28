# Stage 1: Build React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY . .
COPY --from=frontend-builder /app/frontend/dist frontend/dist

ENV DEMO_LIVE_UPLOAD=0

WORKDIR /app/backend

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
