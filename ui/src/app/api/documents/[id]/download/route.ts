import { NextRequest, NextResponse } from 'next/server';

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const documentId = params.id;
  const backendUrl = process.env.BACKEND_URL || `http://localhost:8000/documents/${documentId}/download`;

  try {
    const res = await fetch(backendUrl);
    
    if (!res.ok) {
      return NextResponse.json(
        { error: `Failed to download document: ${res.statusText}` }, 
        { status: res.status }
      );
    }

    // Get content type from the response
    const contentType = res.headers.get('content-type') || 'application/octet-stream';
    // Get original filename if available
    const contentDisposition = res.headers.get('content-disposition');
    let filename = `document-${documentId}`;
    
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="(.+)"/);
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1];
      }
    }

    // Get the document content as blob
    const blob = await res.blob();
    
    // Return the document as a response with appropriate headers
    const response = new NextResponse(blob, {
      status: 200,
      headers: {
        'Content-Type': contentType,
        'Content-Disposition': `attachment; filename="${filename}"`,
      },
    });
    
    return response;
  } catch (error) {
    console.error('Error downloading document:', error);
    return NextResponse.json(
      { error: 'Failed to download document' },
      { status: 500 }
    );
  }
}