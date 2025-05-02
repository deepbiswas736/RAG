import { NextRequest, NextResponse } from 'next/server';

// GET /api/query/async/[id] - get async query result
export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const backendUrl = process.env.BACKEND_URL || `http://localhost:8000/query/async/${params.id}`;
  const res = await fetch(backendUrl);
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
