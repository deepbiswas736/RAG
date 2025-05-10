import { NextRequest, NextResponse } from 'next/server';

export async function DELETE(
  req: NextRequest,
  { params }: { params: { id: string } }
) {
  const documentId = params.id;
  const documentServiceUrl = process.env.NEXT_PUBLIC_DOCUMENT_SERVICE_URL || '/api/documents';
  const backendUrl = `${documentServiceUrl}/${documentId}`;

  try {
    const res = await fetch(backendUrl, {
      method: 'DELETE',
    });
    
    if (!res.ok) {
      return NextResponse.json(
        { error: `Failed to delete document: ${res.statusText}` }, 
        { status: res.status }
      );
    }

    return NextResponse.json({ success: true, message: 'Document deleted successfully' });
  } catch (error) {
    console.error('Error deleting document:', error);
    return NextResponse.json(
      { error: 'Failed to delete document' },
      { status: 500 }
    );
  }
}