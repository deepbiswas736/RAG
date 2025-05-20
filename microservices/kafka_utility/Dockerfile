FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libc-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create a non-root user
RUN useradd -m kafkauser
USER kafkauser

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    KAFKA_BOOTSTRAP_SERVERS=kafka:29092 \
    KAFKA_SECURITY_PROTOCOL=PLAINTEXT

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import socket; socket.socket().connect((os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092').split(':')[0], int(os.environ.get('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092').split(':')[1])))"

# Command to run the service
CMD ["python", "-m", "app.main"]
