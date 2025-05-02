import { NextRequest, NextResponse } from 'next/server';

// POST /api/query/async - async query
export async function POST(req: NextRequest) {
  const body = await req.json();
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000/query/async';
  const res = await fetch(backendUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: body.query }),
  });
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
