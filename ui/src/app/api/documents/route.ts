import { NextRequest, NextResponse } from 'next/server';

// GET /api/documents - list documents
export async function GET() {
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000/documents/list';
  const res = await fetch(backendUrl);
  const data = await res.json();
  return NextResponse.json(data, { status: res.status });
}
