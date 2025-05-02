# RAG Application Backend (app)

This directory contains the backend service for the RAG (Retrieval-Augmented Generation) application. It is responsible for document ingestion, processing, storage, and query handling using Python and MongoDB.

## Features
- Document ingestion and storage
- Embedding and metadata management
- Query processing and vector search
- Integration with MongoDB for persistence
- Modular architecture (application, domain, infrastructure layers)

## Directory Structure
- `main.py` — Entry point for the backend service
- `application/` — Application services (business logic)
- `domain/` — Domain entities, repositories, services, and value objects
- `infrastructure/` — Integrations (MongoDB, LLM, messaging, blob storage)
- `data/` — Data storage (fallback, OCR, PDF processing)
- `keyfile/` — MongoDB keyfile for authentication

## Getting Started

### Prerequisites
- Python 3.12+
- MongoDB (local or Docker)
- (Optional) Docker & Docker Compose

### Installation
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Set up MongoDB (see `docker-compose.yml` for example setup).

### Running the Application
- To start the backend service:
  ```bash
  python main.py
  ```
- Or use Docker Compose:
  ```bash
  docker-compose up --build
  ```

### Testing
- Run tests (if available):
  ```bash
  python -m unittest discover
  ```

## Configuration
- MongoDB connection and other settings can be configured in environment variables or directly in the code.

## License
MIT License

## Contact
For questions or support, please open an issue or contact the maintainer.
