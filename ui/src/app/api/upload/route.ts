import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  const formData = await req.formData();
  const file = formData.get('file') as File;
  if (!file) {
    return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
  }
  // Forward to FastAPI backend
  const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000/document/upload';
  const uploadRes = await fetch(backendUrl, {
    method: 'POST',
    body: formData,
  });
  const data = await uploadRes.json();
  return NextResponse.json(data, { status: uploadRes.status });
}
