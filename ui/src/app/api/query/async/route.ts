import { NextRequest, NextResponse } from 'next/server';

// POST /api/query/async - async query
export async function POST(req: NextRequest) {
  const body = await req.json();
  const queryServiceUrl = process.env.NEXT_PUBLIC_QUERY_SERVICE_URL || '/api/query';
  const backendUrl = `${queryServiceUrl}/async`;
  const res = await fetch(backendUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: body.query }),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
