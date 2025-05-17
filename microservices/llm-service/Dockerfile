FROM python:3.10-slim

WORKDIR /app

# Install required system packages
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    findutils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn

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

# Copy application code
COPY app/ /app/

# Make sure main.py is in the correct location and properly formatted
RUN if [ -f /app/main.py ]; then \
        echo "main.py exists"; \
    else \
        echo "Creating main.py"; \
        echo 'from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get("/")\nasync def root():\n    return {"message": "LLM Service is running"}' > /app/main.py; \
    fi

# List all files to debug
RUN find /app -type f | sort

# Expose the port the app will run on
EXPOSE 8000

# Set Python path to include the current directory
ENV PYTHONPATH=/app

# Command to run the application
CMD ["python", "-m", "uvicorn", "simple_main:app", "--host", "0.0.0.0", "--port", "8000"]
