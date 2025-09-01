FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \ 
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# gRPC proto files compilation
RUN python -m grpc_tools.protoc -I./protos --python_out=./app --grpc_python_out=./app ./protos/*.proto

# Expose the port
EXPOSE 8000 50051

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]