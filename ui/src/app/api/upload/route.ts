import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  console.log('API route /api/upload called');
  try {
    const formData = await req.formData();
    const file = formData.get('file') as File;
    
    if (!file) {
      console.error('No file provided in form data');
      return NextResponse.json({ error: 'No file uploaded' }, { status: 400 });
    }
    
    console.log(`File received: ${file.name}, size: ${file.size} bytes`);
    
    // Forward to FastAPI backend
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:8000/document/upload';
    console.log(`Uploading file to backend: ${backendUrl}`);
    
    try {
      const uploadRes = await fetch(backendUrl, {
        method: 'POST',
        body: formData,
      });
      
      console.log(`Backend response status: ${uploadRes.status}`);
      
      if (!uploadRes.ok) {
        console.error(`Backend upload failed with status: ${uploadRes.status}, ${uploadRes.statusText}`);
        const errorText = await uploadRes.text().catch(() => 'No response body');
        console.error(`Error response: ${errorText}`);
        return NextResponse.json(
          { error: `Upload failed: ${uploadRes.statusText}` }, 
          { status: uploadRes.status }
        );
      }
      
      const data = await uploadRes.json();
      console.log(`Upload successful, response:`, data);
      return NextResponse.json(data);
    } catch (error) {
      console.error('Error communicating with backend:', error);
      return NextResponse.json({ 
        error: 'Failed to upload file: Backend communication error',
        details: error instanceof Error ? error.message : String(error)
      }, { status: 500 });
    }
  } catch (error) {
    console.error('Error processing upload request:', error);
    return NextResponse.json({ 
      error: 'Failed to process upload request',
      details: error instanceof Error ? error.message : String(error)
    }, { status: 500 });
  }
}
