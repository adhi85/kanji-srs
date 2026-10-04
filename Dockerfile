# Stage 1: Build frontend
FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Production image
FROM python:3.12-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY --from=frontend /app/frontend/dist frontend/dist
COPY entrypoint.sh .

# Bake the current DB into the image as seed data
COPY data/kanji-srs.db data-seed/kanji-srs.db

RUN mkdir -p /app/data
EXPOSE 8000
ENV PYTHONPATH=""

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
