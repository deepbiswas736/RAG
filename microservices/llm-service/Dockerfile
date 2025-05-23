FROM python:3.10-slim

WORKDIR /app

# Install required system packages
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    findutils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY llm-service/app/requirements.txt ./llm-requirements.txt
COPY kafka_utility/requirements.txt ./kafka_utility_requirements.txt
RUN pip install uv && \
    uv pip install --system --no-cache-dir -r llm-requirements.txt -r kafka_utility_requirements.txt uvicorn \
        opentelemetry-api \
        opentelemetry-sdk \
        opentelemetry-exporter-otlp \
        opentelemetry-exporter-otlp-proto-grpc \
        opentelemetry-exporter-otlp-proto-http \
        opentelemetry-instrumentation-logging

# Create a directory structure first and add __init__.py files
RUN mkdir -p /app/application/services \
    && mkdir -p /app/domain/entities \
    && mkdir -p /app/domain/interfaces \
    && mkdir -p /app/domain/models \
    && mkdir -p /app/domain/services \
    && mkdir -p /app/domain/value_objects \
    && mkdir -p /app/infrastructure/llm \
    && mkdir -p /app/infrastructure/messaging \
    && mkdir -p /app/infrastructure/resilience \
    && touch /app/__init__.py \
    && touch /app/application/__init__.py \
    && touch /app/application/services/__init__.py \
    && touch /app/domain/__init__.py \
    && touch /app/domain/entities/__init__.py \
    && touch /app/domain/interfaces/__init__.py \
    && touch /app/domain/models/__init__.py \
    && touch /app/domain/services/__init__.py \
    && touch /app/domain/value_objects/__init__.py \
    && touch /app/infrastructure/__init__.py \
    && touch /app/infrastructure/llm/__init__.py \
    && touch /app/infrastructure/messaging/__init__.py \
    && touch /app/infrastructure/resilience/__init__.py

# Copy kafka_utility microservice code
COPY kafka_utility /app/kafka_utility

# Copy document_service microservice code
COPY document_service /app/document_service

# Copy application code
COPY llm-service/app/ /app/

# Environment variable for Ollama URL
ENV OLLAMA_BASE_URL="http://ollama:11434"

# Expose the port the app runs on
EXPOSE 8002

# Make sure main.py is in the correct location and properly formatted
RUN if [ -f /app/main.py ]; then \
        echo "main.py exists"; \
    else \
        echo "Creating main.py"; \
        echo 'from fastapi import FastAPI\\n\\napp = FastAPI()\\n\\n@app.get("/")\\nasync def root():\\n    return {"message": "LLM Service is running"}' > /app/main.py; \
    fi

# List all files to debug
RUN find /app -type f | sort

# Set Python path to include the parent directory of the 'app' package and /app for kafka_utility
ENV PYTHONPATH=/:/app

# Command to run the application
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
