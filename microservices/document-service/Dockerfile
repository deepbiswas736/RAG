FROM python:3.10-slim

WORKDIR /app

# Install required system packages
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ .

# Expose the port the app will run on
EXPOSE 8000

# Set Python path to include the current directory and parent directory
ENV PYTHONPATH="/app:/app/.."

# Command to run the application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]