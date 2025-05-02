import { useRef, useState, useEffect } from "react";
import { useDocuments } from "../lib/documents";

export default function DocumentsPage() {
  const { documents, uploadStatus, fileInputRef, handleUpload } = useDocuments();

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Documents</h1>
      <form onSubmit={handleUpload} className="mb-4 flex flex-col gap-2">
        <label className="font-semibold">Upload a document</label>
        <input type="file" ref={fileInputRef} required />
        <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded">Upload</button>
        {uploadStatus && <span className="ml-2 text-sm">{uploadStatus}</span>}
      </form>
      <div className="mt-8">
        <h2 className="text-xl font-semibold mb-2">Uploaded Documents</h2>
        <ul className="list-disc pl-5">
          {documents.map((doc, idx) => (
            <li key={idx}>{doc.title || doc.file || JSON.stringify(doc)}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
