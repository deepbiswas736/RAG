import { NextRequest, NextResponse } from 'next/server';

// GET /api/documents - list documents
export async function GET() {
  console.log('API route /api/documents called');
  try {
    const documentServiceUrl = process.env.NEXT_PUBLIC_DOCUMENT_SERVICE_URL || '/api/documents';
    const backendUrl = `${documentServiceUrl}/list`;
    console.log(`Fetching documents from backend: ${backendUrl}`);
    
    try {
      const res = await fetch(backendUrl, {
        headers: {
          'Accept': 'application/json',
        },
        cache: 'no-store',
      });
      
      console.log(`Backend response status: ${res.status}`);
      
      if (!res.ok) {
        console.error(`Backend returned error status: ${res.status}, ${res.statusText}`);
        const errorText = await res.text().catch(() => 'No response body');
        console.error(`Error response: ${errorText}`);
        return NextResponse.json({ 
          error: `Failed to fetch documents: ${res.statusText}` 
        }, { status: res.status });
      }
      
      const data = await res.json();
      console.log(`Documents retrieved successfully. Count: ${Array.isArray(data) ? data.length : 'N/A'}`);
      return NextResponse.json(data);
    } catch (error) {
      console.error('Error communicating with backend:', error);
      return NextResponse.json({ 
        error: 'Failed to fetch documents: Backend communication error',
        details: error instanceof Error ? error.message : String(error)
      }, { status: 500 });
    }
  } catch (error) {
    console.error('Error processing documents request:', error);
    return NextResponse.json({ 
      error: 'Failed to process documents request',
      details: error instanceof Error ? error.message : String(error)
    }, { status: 500 });
  }
}
