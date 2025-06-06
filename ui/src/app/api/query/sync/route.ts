import { NextRequest, NextResponse } from 'next/server';

// POST /api/query/sync - sync query with streaming response
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    
    if (!body || typeof body.query !== 'string') {
      console.error('Invalid request body for sync query. "query" field is required and must be a string.');
      return NextResponse.json({ error: 'Invalid request body. "query" field is required.' }, { status: 400 });
    }    console.log(`Received sync streaming query: ${body.query}`);    // Service Discovery Approach:
    // 1. First check if we should use Traefik routing (from environment variable)
    // 2. If not using Traefik, use service-to-service direct communication via internal network
    // 3. Fall back to localhost direct port for local development without Docker
    
    // Get configuration from environment variables
    const useTraefikRouting = process.env.USE_TRAEFIK_ROUTING === 'true';
    
    let queryUrl;
    if (useTraefikRouting) {
      // Use Traefik routing - this would be the API gateway approach
      const traefik = process.env.TRAEFIK_URL || 'http://traefik';
      queryUrl = `${traefik}/api/query/stream`;
      console.log('Using Traefik routing for query service');
    } else {
      // Direct service-to-service communication via internal Docker network
      // This is more reliable for streaming responses between services
      const QUERY_SERVICE_URL = process.env.QUERY_SERVICE_URL || 'http://localhost:8003';
      const baseUrl = QUERY_SERVICE_URL.startsWith('http') ? QUERY_SERVICE_URL : `http://${QUERY_SERVICE_URL}`;
      queryUrl = `${baseUrl}/query/stream`;
      console.log('Using direct service-to-service communication');
    }
    
    console.log(`Connecting to query service at: ${queryUrl}`);
    
    const response = await fetch(queryUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        text: body.query,
        query_type: "hybrid",
      }),
    });
    
    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Error from query service: ${response.status} - ${errorText}`);
      return NextResponse.json({ 
        error: `Query service returned error: ${response.statusText}`,
        details: errorText
      }, { status: response.status });
    }
    
    // Return the streaming response directly
    return new NextResponse(response.body, { 
      status: response.status, 
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive'
      }
    });
  } catch (error: unknown) {
    console.error('Error in /api/query/sync route:', error);
    
    // Type guard for ApiServiceError-like objects
    if (typeof error === 'object' && error !== null && 'status' in error && 'error' in error) {
      const apiError = error as { status: number; error: string; details?: unknown };
      return NextResponse.json(
        { error: apiError.error, details: apiError.details },
        { status: apiError.status || 500 }
      );
    }
    
    // Generic error handling
    return NextResponse.json({ 
      error: 'Failed to process streaming query request',
      details: error instanceof Error ? error.message : String(error)
    }, { status: 500 });
  }
}
