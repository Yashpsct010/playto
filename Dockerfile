# ==========================================
# Stage 1: Build React Frontend
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# We need to ensure Vite uses absolute paths for assets, which is the default (/)
# The build output goes to /app/frontend/dist
RUN npm run build

# ==========================================
# Stage 2: Build Django Backend + Celery
# ==========================================
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for psycopg2
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy Django project files
COPY backend/ .

# Copy built React files from Stage 1 into the location Django expects
# We configured settings.py to look in BASE_DIR/frontend_build
COPY --from=frontend-builder /app/frontend/dist /app/frontend_build

# Collect static files (combines Django admin + React assets)
RUN python manage.py collectstatic --noinput 2>/dev/null || true

# Make the startup script executable
RUN chmod +x start.sh

EXPOSE 8000

# Run the unified entrypoint script (Django + Celery Worker + Celery Beat)
CMD ["./start.sh"]
