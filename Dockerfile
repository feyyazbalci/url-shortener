FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# gRPC proto files compilation
RUN python -m grpc_tools.protoc -I./protos --python_out=./app --grpc_python_out=./app ./protos/*.proto

# Make the migration script executable
RUN chmod +x migrate.py

# Expose the port
EXPOSE 8000 50051

# Create data folder
RUN mkdir -p /app/data

# Add Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]