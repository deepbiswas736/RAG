# GitHub Copilot Reference Guide for RAG Application

This guide helps GitHub Copilot understand the structure, patterns, and conventions used in our RAG (Retrieval-Augmented Generation) application. When generating code suggestions, Copilot should follow these guidelines to maintain consistency with the existing codebase.

## Project Architecture

This project follows a layered architecture with clear separation of concerns:

1. **Domain Layer** (`app/domain/`):
   - Contains core business logic, entities, value objects, and repository interfaces
   - Independent of external frameworks and infrastructure

2. **Application Layer** (`app/application/`):
   - Implements use cases and application services
   - Coordinates between domain logic and infrastructure components
   - Uses domain entities and interfaces

3. **Infrastructure Layer** (`app/infrastructure/`):
   - Provides implementations of domain interfaces
   - Contains external integrations (MongoDB, Kafka, LLM services, etc.)
   - Handles I/O, persistence, and communication with external systems

4. **UI Layer** (`ui/`):
   - Next.js-based React application for the frontend
   - Communicates with backend via API endpoints

## Coding Standards and Patterns

### General Guidelines

1. **Type Hints**: Always use proper Python type hints for function parameters and return values
2. **Error Handling**: Use try-except blocks with appropriate error logging
3. **Async/Await**: The application is built with async programming in mind - use `async`/`await` patterns
4. **Logging**: Use the logging module instead of print statements, with appropriate log levels

### Software Engineering Principles

#### SOLID Principles

1. **Single Responsibility Principle (SRP)**: Each class should have only one responsibility. For example:
   - `DocumentService` handles document operations but delegates processing to `DocumentProcessingService`
   - `LLMManager` focuses solely on LLM interactions, not document retrieval

2. **Open/Closed Principle (OCP)**: Software entities should be open for extension but closed for modification. Use:
   - Abstract base classes and interfaces (like `DocumentRepository`)
   - Strategy pattern for algorithms that might vary (e.g., embedding strategies)

3. **Liskov Substitution Principle (LSP)**: Derived classes must be substitutable for their base classes:
   - Implementations like `MongoDBDocumentRepository` should fully satisfy the `DocumentRepository` interface
   - No method should violate expected behavior of the interface contract

4. **Interface Segregation Principle (ISP)**: Clients should not depend on interfaces they don't use:
   - Define focused interfaces (e.g., separate `DocumentRepository` from `ChunkRepository` if needed)
   - Avoid "fat" interfaces that force implementations to provide unused methods

5. **Dependency Inversion Principle (DIP)**: Depend upon abstractions, not concretions:
   - Higher-level modules (e.g., `application/services`) should depend on abstractions
   - Inject dependencies through constructors rather than instantiating directly

#### Additional Principles

1. **DRY (Don't Repeat Yourself)**: Eliminate duplication by:
   - Extracting common functionality into helper methods
   - Using inheritance or composition to share behavior
   - Creating utility functions for repeated operations

2. **KISS (Keep It Simple, Stupid)**: Favor simplicity over complexity:
   - Start with the simplest solution that could possibly work
   - Add complexity only when proven necessary
   - Use clear naming and straightforward approaches

3. **YAGNI (You Aren't Gonna Need It)**: Don't add functionality until it's necessary:
   - Avoid speculative features or "future-proofing" without clear requirements
   - Focus on implementing only what's currently needed
   - Refactor when new requirements arise rather than overbuilding initially

### Gang of Four Design Patterns

When implementing code, consider these design patterns where appropriate:

#### Creational Patterns

1. **Factory Method**: Used for creating objects without specifying their concrete classes
   - Example: `ChunkFactory.create_chunk(content, embedding, metadata)` to create appropriate chunk types

2. **Abstract Factory**: Create families of related objects
   - Example: `EmbeddingProviderFactory` that can create different embedding service implementations

3. **Singleton**: Ensure a class has only one instance
   - Example: `LLMManager` could be a singleton to manage shared LLM resources
   - Use with caution; consider dependency injection alternatives

4. **Builder**: Construct complex objects step by step
   - Example: `DocumentBuilder` for creating documents with many optional properties

#### Structural Patterns

1. **Adapter**: Let classes work together despite incompatible interfaces
   - Example: Adapting different vector database APIs to work with our repository interface

2. **Bridge**: Separate abstraction from implementation
   - Example: Separating `DocumentProcessor` interface from concrete implementations

3. **Composite**: Compose objects into tree structures
   - Example: Representing nested document structures (documents containing sections)

4. **Decorator**: Add responsibilities to objects dynamically
   - Example: Adding caching or logging behavior to repository implementations

5. **Facade**: Provide simplified interface to complex subsystems
   - Example: `RAGService` that coordinates document retrieval, embedding, and LLM processing

6. **Proxy**: Represent another object to control access to it
   - Example: Lazy-loading proxy for document content

#### Behavioral Patterns

1. **Chain of Responsibility**: Pass requests along a chain of handlers
   - Example: Processing pipeline for document text extraction (PDF → Text → Chunks)

2. **Command**: Turn requests into objects
   - Example: `QueryCommand` objects that encapsulate different query types

3. **Observer**: Define a subscription mechanism for notifications
   - Example: Notifying subscribers when query processing is complete

4. **Strategy**: Define family of algorithms, make them interchangeable
   - Example: Different chunking strategies for document processing

5. **Template Method**: Define skeleton of algorithm, defer some steps to subclasses
   - Example: Base document processor with customizable text extraction methods

### Domain Layer

- **Entities**: Located in `domain/entities/`, represent business objects with identity
- **Value Objects**: Located in `domain/value_objects/`, immutable objects defined by their attributes
- **Repository Interfaces**: Located in `domain/repositories/`, define persistence abstractions
- **Domain Services**: Located in `domain/services/`, contain domain logic that doesn't fit naturally in entities

### Application Layer

- **DTOs**: Use data transfer objects for communication between layers
- **Services**: Application services orchestrate operations using domain components

### Infrastructure Layer

- **Repository Implementations**: Implement domain repository interfaces
- **External Services**: Wrap external APIs in dedicated service classes
- **Dependency Injection**: Components receive their dependencies via constructor parameters

## Key Components

### LLM Manager

The `LLMManager` class in `infrastructure/llm/llm_manager.py` handles interactions with Large Language Models. When generating code for LLM interactions:

- Always handle both streaming and non-streaming responses
- Include proper error handling for API failures
- Use fallback mechanisms when LLM services are unavailable
- Process chunks individually first, then combine results for final answer

### Document Processing

Document processing follows these steps:
1. Upload document via API
2. Extract and process text (including OCR for images if needed)
3. Split into chunks with appropriate overlap
4. Generate embeddings for each chunk
5. Store document metadata and chunks in MongoDB
6. Store raw document in blob storage (MinIO)

### Query Processing

Query processing follows a two-step approach:
1. Process each chunk individually with the LLM
2. Combine individual responses and send to LLM for final summarization

## Common Patterns

### Async Query Processing

```python
async def process_async_query(self, query_id: str, query: str):
    """Process an async query (called by Kafka consumer) using the two-step process"""
    try:
        # Get relevant chunks
        chunks = await self.document_service.search_similar_chunks(query)
        
        if not chunks:
            # Handle empty results case
            
        # Step 1: Process each chunk individually
        chunk_responses = []
        for context in contexts:
            chunk_response = await self._process_chunk_with_llm(query, context)
            chunk_responses.append(chunk_response)
        
        # Step 2: Generate summary from all chunk responses
        summary = await self._generate_summary_from_chunk_responses(query, chunk_responses, sources)
        
        # Store result
        self.query_results[query_id] = QueryResult(
            query_id=query_id,
            answer=summary,
            source_chunks=chunks,
            status="completed",
            chunk_responses=chunk_responses
        )
    except Exception as e:
        # Handle error case
```

### Repository Pattern

```python
class MongoDBDocumentRepository(DocumentRepository):
    """MongoDB implementation of the document repository interface"""
    
    async def save(self, document: Document) -> str:
        """Save a document and return its ID"""
        # Implementation
        
    async def search_similar(self, embedding: Embedding, limit: int = 5) -> List<Chunk]:
        """Find chunks similar to the given embedding"""
        # Vector search implementation
```

## Testing

- All code should be designed for testability
- Domain logic should be easily testable without infrastructure dependencies
- Use dependency injection to allow mocking external services in tests

## Error Handling and Logging

- Use appropriate exception types for different error scenarios
- Log exceptions with sufficient context for debugging
- Follow this pattern for error handling:

```python
try:
    # Operation that might fail
except SpecificException as e:
    logger.error(f"Specific error occurred: {e}")
    # Handle specific error case
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    # Handle general error case
```

## Configuration

- Use environment variables for configuration values
- Provide sensible defaults when environment variables are not present
- Example:

```python
self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
self.model = os.getenv("OLLAMA_MODEL", "llama2")
```

## Feedback

When generating code, prioritize:
1. Consistency with existing patterns and structures
2. Proper error handling and logging
3. Type safety and proper async handling
4. Adherence to the layered architecture

## commands
Windows use ; instead of && for running multiple commands

