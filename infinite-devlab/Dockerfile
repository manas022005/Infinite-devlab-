FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

# Backend deps
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Code
COPY backend /app/backend
COPY frontend /app/frontend

ENV FRONTEND_DIR=/app/frontend
ENV PORT=8000
EXPOSE 8000

WORKDIR /app/backend
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:8000", "app:app"]
