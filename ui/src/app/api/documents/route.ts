import { NextRequest, NextResponse } from 'next/server';
import {
  listDocuments,
  uploadFileToDocumentService,
  getDocumentById,
  deleteDocumentById,
  convertFileToPdf,
  downloadDocumentById,
  getDocumentChunks,
  ListDocumentsParams
} from '@/lib/apiService';

// Helper to handle errors consistently
function handleError(error: unknown, defaultMessage: string, documentId?: string) {
  console.error(`API Route: ${defaultMessage}${documentId ? ` for ID ${documentId}` : ''}:`, error);
  // Type guard for ApiServiceError-like objects
  if (typeof error === 'object' && error !== null && 'status' in error && 'error' in error) {
    const apiError = error as { status: number; error: string; details?: unknown };
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return NextResponse.json({ error: apiError.error, details: apiError.details as any }, { status: apiError.status });
  }
  return NextResponse.json({
    error: `${defaultMessage}${documentId ? ` for ID ${documentId}` : ''}: Internal server error`,
    details: error instanceof Error ? error.message : String(error)
  }, { status: 500 });
}

export async function GET(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  // Path segments: /api/documents/{documentId?}/{action?}
  const pathSegments = pathname.split('/').filter(Boolean); // e.g., ['api', 'documents', 'docId', 'download']

  try {
    // List documents: /api/documents
    if (pathSegments.length === 2 && pathSegments[1] === 'documents') {
      const params: ListDocumentsParams = {
        skip: parseInt(searchParams.get('skip') || '0', 10),
        limit: parseInt(searchParams.get('limit') || '100', 10), // Default limit increased
        status: searchParams.get('status') || undefined,
        processed: searchParams.has('processed') ? searchParams.get('processed') === 'true' : undefined,
        chunked: searchParams.has('chunked') ? searchParams.get('chunked') === 'true' : undefined,
      };
      console.log(`API Route: Listing documents with params:`, params);
      const data = await listDocuments(params);
      return NextResponse.json(data);
    }

    // Get document by ID: /api/documents/{documentId}
    if (pathSegments.length === 3 && pathSegments[1] === 'documents') {
      const documentId = pathSegments[2];
      console.log(`API Route: Getting document by ID: ${documentId}`);
      const data = await getDocumentById(documentId);
      return NextResponse.json(data);
    }

    // Download document: /api/documents/{documentId}/download
    if (pathSegments.length === 4 && pathSegments[1] === 'documents' && pathSegments[3] === 'download') {
      const documentId = pathSegments[2];
      console.log(`API Route: Downloading document: ${documentId}`);
      const { blob, filename } = await downloadDocumentById(documentId);
      return new NextResponse(blob, {
        headers: {
          'Content-Type': blob.type,
          'Content-Disposition': `attachment; filename="${filename}"`,
        },
      });
    }

    // Get document chunks: /api/documents/{documentId}/chunks
    if (pathSegments.length === 4 && pathSegments[1] === 'documents' && pathSegments[3] === 'chunks') {
      const documentId = pathSegments[2];
      console.log(`API Route: Getting document chunks: ${documentId}`);
      const data = await getDocumentChunks(documentId);
      return NextResponse.json(data);
    }

    return NextResponse.json({ error: 'Invalid GET route for documents' }, { status: 404 });

  } catch (error: unknown) {
    const documentId = pathSegments.length >= 3 ? pathSegments[2] : undefined;
    return handleError(error, 'Error processing GET request', documentId);
  }
}

export async function POST(request: NextRequest) {
  const { pathname } = request.nextUrl;
  // Path segments: /api/documents or /api/documents/convert
  const pathSegments = pathname.split('/').filter(Boolean);

  try {
    // Upload document: /api/documents
    if (pathSegments.length === 2 && pathSegments[1] === 'documents') {
      console.log('API Route: Uploading new document');
      const formData = await request.formData();
      const file = formData.get('file') as File; // Assuming 'file' is the field name

      if (!file) {
        console.error('No file provided in form data for upload');
        return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
      }
      console.log(`File received for upload: ${file.name}, size: ${file.size} bytes`);
      // Pass the whole formData, as apiService expects it
      const data = await uploadFileToDocumentService(formData); 
      return NextResponse.json(data);
    }

    // Convert document to PDF: /api/documents/convert
    if (pathSegments.length === 3 && pathSegments[1] === 'documents' && pathSegments[2] === 'convert') {
      console.log('API Route: Converting document to PDF');
      const formData = await request.formData();
      const file = formData.get('file') as File;

      if (!file) {
        console.error('No file provided in form data for conversion');
        return NextResponse.json({ error: 'No file provided for conversion' }, { status: 400 });
      }
      console.log(`File received for PDF conversion: ${file.name}, size: ${file.size} bytes`);
      const { blob, filename } = await convertFileToPdf(file);
      return new NextResponse(blob, {
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': `attachment; filename="${filename}"`,
        },
      });
    }
    
    return NextResponse.json({ error: 'Invalid POST route for documents' }, { status: 404 });

  } catch (error: unknown) {
    return handleError(error, 'Error processing POST request');
  }
}

export async function DELETE(request: NextRequest) {
  const { pathname } = request.nextUrl;
  // Path segments: /api/documents/{documentId}
  const pathSegments = pathname.split('/').filter(Boolean);
  
  try {
    if (pathSegments.length === 3 && pathSegments[1] === 'documents') {
      const documentId = pathSegments[2];
      console.log(`API Route: Deleting document by ID: ${documentId}`);
      const result = await deleteDocumentById(documentId);
      if (result === null) {
        return new NextResponse(null, { status: 204 }); // Successfully deleted
      }
      return NextResponse.json(result); // If backend sends a body
    }

    return NextResponse.json({ error: 'Invalid DELETE route for documents' }, { status: 404 });

  } catch (error: unknown) {
    const documentId = pathSegments.length >= 3 ? pathSegments[2] : undefined;
    return handleError(error, 'Error processing DELETE request', documentId);
  }
}
