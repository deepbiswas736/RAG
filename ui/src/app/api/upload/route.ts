import { NextRequest, NextResponse } from 'next/server';
import { uploadFileToDocumentService } from '@/lib/apiService'; // Import the centralized API service

export async function POST(req: NextRequest) {
  console.log('API route /api/upload called');
  try {
    const formData = await req.formData();
    const file = formData.get('file') as File;
    
    if (!file) {
      console.error('No file provided in form data');
      return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
    }
    
    console.log(`File received: ${file.name}, size: ${file.size} bytes`);
    
    // Use the centralized API service to upload the file
    const data = await uploadFileToDocumentService(formData);
    
    console.log(`Upload successful, response:`, data);
    return NextResponse.json(data);

  } catch (error: unknown) {
    console.error('Error in /api/upload route:', error);
    // Check if the error is from our apiService, which includes a status
    if (error && typeof error === 'object' && 'error' in error && 'status' in error && typeof error.status === 'number') {
      return NextResponse.json(
        { error: (error as {error: string}).error, details: (error as {details?: string}).details },
        { status: error.status }
      );
    }
    // Generic error handling for other types of errors
    return NextResponse.json({ 
      error: 'Failed to process upload request',
      details: error instanceof Error ? error.message : String(error)
    }, { status: 500 });
  }
}
