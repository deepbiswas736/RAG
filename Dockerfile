FROM python:3.9-slim

# Install system dependencies and ensure proper Poppler installation
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    curl\
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && update-ca-certificates \
    && which pdftoppm && pdftoppm -v  # Verify poppler installation

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]