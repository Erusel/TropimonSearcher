# ===========================
# ⚡ Tropimon Stats – Dockerfile
# ===========================

# Base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . /app

# Expose port for Uvicorn
EXPOSE 8000

# FastAPI launch command
CMD ["uvicorn", "tropimon_service:app", "--host", "0.0.0.0", "--port", "8000"]
