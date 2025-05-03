import { NextResponse } from 'next/server';

// GET /api/query/completed - get list of completed queries
export async function GET() {
  try {
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000/query/completed';
    console.log(`Fetching completed queries from: ${backendUrl}`);
    
    const res = await fetch(backendUrl, {
      headers: {
        'Accept': 'application/json',
      },
      cache: 'no-store',
    });
    
    if (!res.ok) {
      console.error(`Backend returned status: ${res.status}`);
      return NextResponse.json({ error: `Failed to fetch completed queries: ${res.statusText}` }, { status: res.status });
    }
    
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching completed queries:', error);
    return NextResponse.json({ error: 'Failed to fetch completed queries' }, { status: 500 });
  }
}