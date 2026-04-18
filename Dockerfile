FROM python:3.11-slim

WORKDIR /app

# Install deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY backend/ ./backend/
COPY frontend/ ./frontend/

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
