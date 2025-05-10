import { NextRequest, NextResponse } from 'next/server';

// POST /api/query/sync - sync query
export async function POST(req: NextRequest) {
  const body = await req.json();
  const queryServiceUrl = process.env.NEXT_PUBLIC_QUERY_SERVICE_URL || '/api/query';
  const backendUrl = `${queryServiceUrl}/sync`;
  const res = await fetch(backendUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: body.query }),
  });
  const text = await res.text();
  return new NextResponse(text, { status: res.status });
}
