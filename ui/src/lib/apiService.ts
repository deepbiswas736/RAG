// lib/apiService.ts
const DOCUMENT_SERVICE_INTERNAL_HOST = process.env.DOCUMENT_SERVICE_INTERNAL_HOST || 'http://localhost';
const DOCUMENT_SERVICE_BASE_PATH = process.env.DOCUMENT_SERVICE_BASE_PATH || '/api/documents';
const DOC_SERVICE_BASE_URL = `${DOCUMENT_SERVICE_INTERNAL_HOST}${DOCUMENT_SERVICE_BASE_PATH}`;

// Query Service Configuration
const QUERY_SERVICE_URL = process.env.QUERY_SERVICE_URL || 'http://localhost/api/query'; // Default for Traefik setup

// Error interface
export interface ApiServiceError {
  error: string;
  details?: string;
  status?: number;
}

// DTOs based on the Python backend
export interface DocumentDTO {
  id: string; // Assuming 'id' is the primary identifier, could be '_id'
  filename: string;
  content_type: string;
  size: number;
  upload_date: string; // Consider using Date type and parsing
  user_id?: string;
  metadata?: Record<string, unknown>; // Changed: any to unknown
  processing_status?: string;
  is_processed?: boolean;
  is_chunked?: boolean;
  // Add any other fields that are part of DocumentDTO
}

export interface ListDocumentsParams {
  skip?: number;
  limit?: number;
  status?: string;
  processed?: boolean;
  chunked?: boolean;
}

export interface ListDocumentsResponse {
  documents: DocumentDTO[];
  total: number;
  skip: number;
  limit: number;
}

export interface DocumentChunk {
  // Define the structure of a chunk based on your backend
  // For example:
  // id: string;
  // document_id: string;
  // text: string;
  // order: number;
  [key: string]: unknown; // Changed: any to unknown
}

export interface DocumentChunksResponse {
  chunks: DocumentChunk[];
  count: number;
}

// Helper function to handle API responses and errors
async function handleResponse<T>(response: Response, isBlob: boolean = false): Promise<T> {
  if (!response.ok) {
    let errorText = 'No response body or failed to read response body';
    try {
      errorText = await response.text();
    } catch (_e) { // Changed e to _e
      console.warn('Failed to read error response text', _e);
    }
    console.error(`API Service: Request failed with status: ${response.status}, ${response.statusText}`);
    console.error(`API Service: Error response: ${errorText}`);
    throw {
      error: `API request failed: ${response.statusText}`,
      details: errorText,
      status: response.status,
    } as ApiServiceError;
  }
  if (isBlob) {
    return response.blob() as Promise<T>;
  }
  // Handle cases where response might be empty (e.g., 204 No Content for DELETE)
  if (response.status === 204) {
    return null as T; // Or an appropriate representation for no content
  }
  const contentType = response.headers.get("content-type");
  if (contentType && contentType.indexOf("application/json") !== -1) {
    return response.json() as Promise<T>;
  }
  // For non-JSON responses that are not blobs (e.g. plain text)
  return response.text() as Promise<T>; 
}

/**
 * Uploads a file to the document service.
 * @param formData The FormData object containing the file and any other metadata.
 * @returns The JSON response from the server (DocumentDTO).
 * @throws ApiServiceError if the request fails.
 */
export async function uploadFileToDocumentService(formData: FormData): Promise<DocumentDTO> {
  const uploadUrl = `${DOC_SERVICE_BASE_URL}/`; // Changed: removed "/documents"
  console.log(`Uploading file to document service: ${uploadUrl}`);
  try {
    const response = await fetch(uploadUrl, {
      method: 'POST',
      body: formData,
    });
    return await handleResponse<DocumentDTO>(response);
  } catch (error: unknown) { // Changed any to unknown
    if (error && typeof error === 'object' && 'status' in error) {
        const apiError = error as ApiServiceError;
        if (apiError.status) throw apiError; 
    }
    console.error('API Service: Error uploading file:', error);
    throw { 
      error: 'Failed to upload file: Network or unexpected error',
      details: error instanceof Error ? error.message : String(error),
      status: undefined // Status might not be available for network errors
    } as ApiServiceError;
  }
}

/**
 * Lists documents with optional filtering and pagination.
 * @param params Filtering and pagination parameters.
 * @returns A list of documents and pagination info.
 * @throws ApiServiceError if the request fails.
 */
export async function listDocuments(params?: ListDocumentsParams): Promise<ListDocumentsResponse> {
  const query = new URLSearchParams();
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        query.append(key, String(value));
      }
    });
  }
  const queryString = query.toString();
  const listUrl = `${DOC_SERVICE_BASE_URL}/${queryString ? '?' + queryString : ''}`; // Changed: removed "/documents"
  console.log(`Listing documents from: ${listUrl}`);
  try {
    const response = await fetch(listUrl, { method: 'GET' });
    return await handleResponse<ListDocumentsResponse>(response);
  } catch (error: unknown) { // Changed any to unknown
    if (error && typeof error === 'object' && 'status' in error) {
        const apiError = error as ApiServiceError;
        if (apiError.status) throw apiError; 
    }
    console.error('API Service: Error listing documents:', error);
    throw { 
      error: 'Failed to list documents: Network or unexpected error',
      details: error instanceof Error ? error.message : String(error)
    } as ApiServiceError;
  }
}

/**
 * Gets a single document by its ID.
 * @param documentId The ID of the document.
 * @returns Document metadata.
 * @throws ApiServiceError if the request fails.
 */
export async function getDocumentById(documentId: string): Promise<DocumentDTO> {
  const getUrl = `${DOC_SERVICE_BASE_URL}/${documentId}`; // Changed: removed "/documents"
  console.log(`Getting document by ID: ${getUrl}`);
  try {
    const response = await fetch(getUrl, { method: 'GET' });
    return await handleResponse<DocumentDTO>(response);
  } catch (error: unknown) { // Changed any to unknown
    if (error && typeof error === 'object' && 'status' in error) {
        const apiError = error as ApiServiceError;
        if (apiError.status) throw apiError; 
    }
    console.error(`API Service: Error getting document ${documentId}:`, error);
    throw { 
      error: `Failed to get document ${documentId}: Network or unexpected error`,
      details: error instanceof Error ? error.message : String(error)
    } as ApiServiceError;
  }
}

/**
 * Deletes a document by its ID.
 * @param documentId The ID of the document to delete.
 * @returns Success message or null.
 * @throws ApiServiceError if the request fails.
 */
export async function deleteDocumentById(documentId: string): Promise<{ status: string; message: string } | null> {
  const deleteUrl = `${DOC_SERVICE_BASE_URL}/${documentId}`; // Changed: removed "/documents"
  console.log(`Deleting document by ID: ${deleteUrl}`);
  try {
    const response = await fetch(deleteUrl, { method: 'DELETE' });
    // DELETE might return 200 with body or 204 No Content
    if (response.status === 204) return null;
    return await handleResponse<{ status: string; message: string }>(response);
  } catch (error: unknown) { // Changed any to unknown
    if (error && typeof error === 'object' && 'status' in error) {
        const apiError = error as ApiServiceError;
        if (apiError.status) throw apiError; 
    }
    console.error(`API Service: Error deleting document ${documentId}:`, error);
    throw { 
      error: `Failed to delete document ${documentId}: Network or unexpected error`,
      details: error instanceof Error ? error.message : String(error)
    } as ApiServiceError;
  }
}

/**
 * Downloads a document file by its ID.
 * @param documentId The ID of the document to download.
 * @returns A Blob containing the file content and the filename.
 * @throws ApiServiceError if the request fails.
 */
export async function downloadDocumentById(documentId: string): Promise<{ blob: Blob, filename: string }> {
  const downloadUrl = `${DOC_SERVICE_BASE_URL}/${documentId}/download`; // Changed: removed "/documents"
  console.log(`Downloading document from: ${downloadUrl}`);
  try {
    const response = await fetch(downloadUrl, { method: 'GET' });
    if (!response.ok) {
      // Use handleResponse for consistent error throwing, but it expects JSON by default
      // So we manually throw for non-ok blob responses before calling handleResponse
      let errorText = 'Failed to download file';
      try { errorText = await response.text(); } catch {} // Removed _e
      throw {
        error: `Download failed: ${response.statusText}`,
        details: errorText,
        status: response.status,
      } as ApiServiceError;
    }
    const blob = await response.blob();
    const contentDisposition = response.headers.get('content-disposition');
    let filename = 'downloaded-file'; // Default filename
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1];
      }
    }
    return { blob, filename };
  } catch (error: unknown) { // Changed any to unknown
    if (error && typeof error === 'object' && 'status' in error) {
        const apiError = error as ApiServiceError;
        if (apiError.status) throw apiError; 
    }
    console.error(`API Service: Error downloading document ${documentId}:`, error);
    throw { 
      error: `Failed to download document ${documentId}: Network or unexpected error`,
      details: error instanceof Error ? error.message : String(error)
    } as ApiServiceError;
  }
}

/**
 * Gets chunks for a document by its ID.
 * @param documentId The ID of the document.
 * @returns Document chunks information.
 * @throws ApiServiceError if the request fails.
 */
export async function getDocumentChunks(documentId: string): Promise<DocumentChunksResponse> {
  const chunksUrl = `${DOC_SERVICE_BASE_URL}/${documentId}/chunks`; // Changed: removed "/documents"
  console.log(`Getting document chunks from: ${chunksUrl}`);
  try {
    const response = await fetch(chunksUrl, { method: 'GET' });
    return await handleResponse<DocumentChunksResponse>(response);
  } catch (error: unknown) { // Changed any to unknown
    if (error && typeof error === 'object' && 'status' in error) {
        const apiError = error as ApiServiceError;
        if (apiError.status) throw apiError; 
    }
    console.error(`API Service: Error getting chunks for document ${documentId}:`, error);
    throw { 
      error: `Failed to get chunks for document ${documentId}: Network or unexpected error`,
      details: error instanceof Error ? error.message : String(error)
    } as ApiServiceError;
  }
}

/**
 * Converts a document to PDF.
 * @param file The file to convert.
 * @returns A Blob containing the PDF content and the filename.
 * @throws ApiServiceError if the request fails.
 */
export async function convertFileToPdf(file: File): Promise<{ blob: Blob, filename: string }> {
  const convertUrl = `${DOC_SERVICE_BASE_URL}/convert`; // Changed: removed "/documents"
  console.log(`Converting file to PDF: ${convertUrl}`);
  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch(convertUrl, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      let errorText = 'Failed to convert file to PDF';
      try { errorText = await response.text(); } catch {} // Removed _e
      throw {
        error: `PDF conversion failed: ${response.statusText}`,
        details: errorText,
        status: response.status,
      } as ApiServiceError;
    }
    const blob = await response.blob();
    const contentDisposition = response.headers.get('content-disposition');
    let filename = 'converted.pdf'; // Default filename
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1];
      }
    }
    return { blob, filename };
  } catch (error: unknown) { // Changed any to unknown
    if (error && typeof error === 'object' && 'status' in error) {
        const apiError = error as ApiServiceError;
        if (apiError.status) throw apiError; 
    }
    console.error('API Service: Error converting file to PDF:', error);
    throw { 
      error: 'Failed to convert file to PDF: Network or unexpected error',
      details: error instanceof Error ? error.message : String(error)
    } as ApiServiceError;
  }
}

/**
 * Submits an asynchronous query to the query service.
 * @param payload The query payload, e.g., { query: string }.
 * @returns The JSON response from the server.
 * @throws ApiServiceError if the request fails.
 */
export async function submitAsyncQuery(payload: { query: string }): Promise<unknown> { // Changed any to unknown
  const queryUrl = `${QUERY_SERVICE_URL}/async`; // Query service's async endpoint
  console.log(`Submitting async query to: ${queryUrl} with payload:`, payload);

  try {
    const response = await fetch(queryUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    return await handleResponse<unknown>(response); // Changed any to unknown
  } catch (error: unknown) { // Changed any to unknown
    if (error && typeof error === 'object' && 'status' in error && 'error' in error) { // Added type check for error property
        const apiError = error as ApiServiceError;
        if (apiError.status && apiError.error) throw apiError; 
    }
    console.error('API Service: Error submitting async query:', error);
    throw {
      error: 'Failed to submit async query: Network or unexpected error',
      details: error instanceof Error ? error.message : String(error),
      status: undefined // Status might not be available for network errors
    } as ApiServiceError;
  }
}
