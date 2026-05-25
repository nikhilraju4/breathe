# Stage 1: build React frontend
FROM node:20-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python API + serve built SPA
FROM python:3.12-slim
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY sample_data/ sample_data/
COPY --from=frontend /app/frontend/dist frontend/dist

WORKDIR /app/backend
ENV PYTHONUNBUFFERED=1
ENV RENDER=true

COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

EXPOSE 8000
CMD ["/app/start.sh"]
