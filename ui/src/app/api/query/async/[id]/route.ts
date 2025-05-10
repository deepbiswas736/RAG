import { NextRequest, NextResponse } from 'next/server';

// GET /api/query/async/[id] - get async query result
export async function GET(req: NextRequest, { params }: { params: { id: string } }) {
  const queryServiceUrl = process.env.NEXT_PUBLIC_QUERY_SERVICE_URL || '/api/query';
  const backendUrl = `${queryServiceUrl}/async/${params.id}`;
  const res = await fetch(backendUrl);
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
