import { NextRequest, NextResponse } from 'next/server';
import { submitAsyncQuery } from '@/lib/apiService'; // Import the centralized API service

// POST /api/query - Handles asynchronous queries
export async function POST(req: NextRequest) {
  console.log('API route /api/query called');
  try {
    const body = await req.json();
    
    if (!body || typeof body.query !== 'string') {
      console.error('Invalid request body for query. "query" field is required and must be a string.');
      return NextResponse.json({ error: 'Invalid request body. "query" field is required.' }, { status: 400 });
    }
    
    console.log(`Received query: ${body.query}`);
    
    // Use the centralized API service to submit the query
    const data = await submitAsyncQuery({ query: body.query });
    
    console.log(`Query submission successful, response:`, data);
    return NextResponse.json(data);

  } catch (error: unknown) {
    console.error('Error in /api/query route:', error);
    // Type guard for ApiServiceError-like objects
    if (typeof error === 'object' && error !== null && 'status' in error && 'error' in error) {
      const apiError = error as { status: number; error: string; details?: unknown };
      return NextResponse.json(
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        { error: apiError.error, details: apiError.details as any },
        { status: apiError.status }
      );
    }
    // Generic error handling for other types of errors
    return NextResponse.json({ 
      error: 'Failed to process query request',
      details: error instanceof Error ? error.message : String(error)
    }, { status: 500 });
  }
}
