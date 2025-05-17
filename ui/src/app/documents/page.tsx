"use client";
import { useDocuments } from "../lib/documents";

export default function DocumentsPage() {
  const { 
    documents, 
    uploadStatus, 
    fileInputRef, 
    handleUpload, 
    deleteDocument, 
    downloadDocument,
    isLoading
  } = useDocuments();

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Document Management</h1>
      <p className="mb-4 text-gray-600">
        Upload and manage documents for use with the RAG system. Uploaded documents will be processed, chunked, and indexed for efficient retrieval.
      </p>
      
      <div className="bg-white shadow-md rounded-lg p-6 mb-8">
        <h2 className="text-xl font-semibold mb-4">Upload New Document</h2>
        <p className="mb-4 text-sm text-gray-600">
          Upload documents in any format (PDF, DOCX, TXT, etc.). All documents will be automatically converted to PDF format for consistent processing and storage.
        </p>
        <form onSubmit={handleUpload} className="space-y-4">
          <div>
            <label htmlFor="document" className="block text-sm font-medium text-gray-700 mb-1">
              Select Document
            </label>
            <input 
              id="document"
              type="file" 
              ref={fileInputRef} 
              required 
              className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3"
              disabled={isLoading}
            />
          </div>
          <button 
            type="submit" 
            className={`inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white ${
              isLoading ? 'bg-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700'
            }`}
            disabled={isLoading}
          >
            {isLoading ? 'Processing...' : 'Upload Document'}
          </button>
          {uploadStatus && (
            <div className={`mt-2 text-sm ${uploadStatus.includes("successful") ? "text-green-600" : "text-red-600"}`}>
              {uploadStatus}
            </div>
          )}
        </form>
      </div>
      
      <div className="bg-white shadow-md rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Uploaded Documents</h2>
        
        {documents.length === 0 && !isLoading && (
          <div className="text-center py-8 text-gray-500">
            No documents uploaded yet
          </div>
        )}
        
        {isLoading && documents.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            Loading documents...
          </div>
        )}
        
        {documents.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Document Name
                  </th>
                  <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {documents.map((doc) => (
                  <tr key={doc.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {doc.title || doc.file || `Document ${doc.id}`}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={() => downloadDocument(doc.id, doc.title)}
                        className="text-blue-600 hover:text-blue-900 mr-4"
                        disabled={isLoading}
                      >
                        Download
                      </button>
                      <button
                        onClick={() => deleteDocument(doc.id)}
                        className="text-red-600 hover:text-red-900"
                        disabled={isLoading}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
