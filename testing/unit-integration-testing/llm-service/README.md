# LLM Service Unit Tests

This directory contains unit tests for the LLM service, particularly for the document summarizer functionality.

## Test Files

- `tests/unit/domain/services/test_document_summarizer.py`: Basic tests for the document summarizer
- `tests/unit/domain/services/test_document_summarizer_enhanced.py`: Enhanced tests for handling different JSON response formats

## Key Features Tested

The tests validate the document summarizer's ability to:

1. Parse different response formats:
   - Markdown-formatted JSON
   - Raw JSON (without markdown)
   - Text format responses
   - Dictionary responses

2. Handle error cases:
   - Incomplete JSON
   - Malformed JSON
   - JSON with nested braces

3. Provide fallback mechanisms:
   - Extract data from incomplete JSON
   - Parse unstructured text
   - Handle dictionary responses with different formats

## Running Tests

To run these tests, navigate to the llm-service directory and execute:

```bash
python -m pytest tests/unit/domain/services/test_document_summarizer.py -v
python -m pytest tests/unit/domain/services/test_document_summarizer_enhanced.py -v
```

These tests help ensure the document summarizer can correctly handle various response formats from LLM models, especially the Phi model which may return incomplete JSON responses.
