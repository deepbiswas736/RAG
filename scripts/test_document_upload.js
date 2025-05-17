// Simple script to test document upload to RAG system
import fetch from 'node-fetch';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
import FormData from 'form-data';
import fs from 'fs';

// Configuration
const DOCUMENT_SERVICE_URL = 'http://localhost/api/documents';
const __dirname = dirname(fileURLToPath(import.meta.url));

async function uploadDocument(filePath) {
  // Verify file exists
  if (!fs.existsSync(filePath)) {
    console.error(`File not found: ${filePath}`);
    process.exit(1);
  }

  console.log(`Uploading document to: ${DOCUMENT_SERVICE_URL}`);
  console.log(`File path: ${filePath}`);
  
  // Create form data with proper fields for FastAPI
  const form = new FormData();
  const fileStream = fs.createReadStream(filePath);
  const fileName = filePath.split(/[\\/]/).pop();
  
  // Add file and metadata
  form.append('file', fileStream, {
    filename: fileName,
    contentType: 'text/plain'
  });

  try {
    // Add metadata as a JSON string
    const metadata = JSON.stringify({
      source: "test-upload",
      description: "Test document for RAG system validation"
    });
    
    // Add metadata to form data
    form.append('metadata', metadata);

    console.log('Sending request...');
    console.log('Request headers:', form.getHeaders());
    
    const response = await fetch(DOCUMENT_SERVICE_URL, {
      method: 'POST',
      body: form,
      headers: form.getHeaders()
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Upload failed with status ${response.status}: ${errorText}`);
    }

    const responseData = await response.json();
    console.log('Upload successful!');
    console.log('Response:', JSON.stringify(responseData, null, 2));

    if (responseData.id) {
      // Check document chunks after successful upload
      console.log('\nChecking document chunks...');
      const chunksResponse = await fetch(`${DOCUMENT_SERVICE_URL}/documents/${responseData.id}/chunks`);
      
      if (!chunksResponse.ok) {
        console.log('Note: Chunks not yet available (this is normal, as processing may take time)');
      } else {
        const chunksData = await chunksResponse.json();
        console.log('\nDocument Chunks:');
        console.log('-----------------');
        console.log('Number of chunks:', chunksData.count);
        if (chunksData.chunks && chunksData.chunks.length > 0) {
          chunksData.chunks.forEach((chunk, index) => {
            console.log(`\nChunk ${index + 1}:`);
            console.log('Content (preview):', chunk.text?.substring(0, 100) + '...');
            if (chunk.metadata) {
              console.log('Metadata:', JSON.stringify(chunk.metadata, null, 2));
            }
          });
        }
      }
    }

    return { status: response.status, data: responseData };
  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  }
}

// Execute if run directly
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const testFile = process.argv[2];
  if (!testFile) {
    console.error('Please provide a file path as argument');
    process.exit(1);
  }

  // Convert relative path to absolute if needed
  const fullPath = testFile.startsWith('/') ? testFile : join(process.cwd(), testFile);
  
  uploadDocument(fullPath)
    .catch(error => {
      console.error('Fatal error:', error);
      process.exit(1);
    });
}
