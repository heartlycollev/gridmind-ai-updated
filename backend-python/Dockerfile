# Use Python 3.12 slim base image
FROM python:3.12-slim

# Prevent Python from writing pyc files and buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory inside container
WORKDIR /app

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements from backend-python
COPY backend-python/requirements.txt ./

# Install python packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy Python backend code
COPY backend-python/ ./

# Expose port 8000
EXPOSE 8000

# Start command running uvicorn, binding to 0.0.0.0 and reading dynamic PORT if present
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
