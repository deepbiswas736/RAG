"use client";

import { useRef, useState, useEffect } from "react";

export default function Home() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [syncQuery, setSyncQuery] = useState("");
  const [asyncQuery, setAsyncQuery] = useState("");
  const [syncResult, setSyncResult] = useState("");
  const [asyncResult, setAsyncResult] = useState("");
  const [asyncId, setAsyncId] = useState("");
  const [documents, setDocuments] = useState<any[]>([]);

  // Upload handler
  async function handleUpload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setUploadStatus("Please select a file.");
      return;
    }
    const formData = new FormData();
    formData.append("file", file);
    setUploadStatus("Uploading...");
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });
    if (res.ok) {
      setUploadStatus("Upload successful!");
      fetchDocuments();
    } else {
      setUploadStatus("Upload failed.");
    }
  }

  // Sync query handler
  async function handleSyncQuery(e: React.FormEvent) {
    e.preventDefault();
    setSyncResult("Loading...");
    const res = await fetch("/api/query/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: syncQuery }),
    });
    setSyncResult(await res.text());
  }

  // Async query handler
  async function handleAsyncQuery(e: React.FormEvent) {
    e.preventDefault();
    setAsyncResult("Submitting...");
    const res = await fetch("/api/query/async", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: asyncQuery }),
    });
    const data = await res.json();
    setAsyncId(data.query_id);
    setAsyncResult("Processing...");
    pollAsyncResult(data.query_id);
  }

  // Poll async result
  async function pollAsyncResult(id: string) {
    const interval = setInterval(async () => {
      const res = await fetch(`/api/query/async/${id}`);
      const data = await res.json();
      if (data.status === "completed" || data.status === "error") {
        setAsyncResult(data.answer || "No answer");
        clearInterval(interval);
      }
    }, 2000);
  }

  // Fetch documents
  async function fetchDocuments() {
    const res = await fetch("/api/documents");
    if (res.ok) {
      setDocuments(await res.json());
    }
  }

  useEffect(() => { fetchDocuments(); }, []);

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">RAG Document UI</h1>
      <form onSubmit={handleUpload} className="mb-4 flex flex-col gap-2">
        <label className="font-semibold">Upload a document</label>
        <input type="file" ref={fileInputRef} required />
        <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded">Upload</button>
        {uploadStatus && <span className="ml-2 text-sm">{uploadStatus}</span>}
      </form>
      <form onSubmit={handleSyncQuery} className="mb-4 flex flex-col gap-2">
        <label className="font-semibold">Sync Query</label>
        <input value={syncQuery} onChange={e => setSyncQuery(e.target.value)} placeholder="Enter query" className="border px-2 py-1" />
        <button type="submit" className="px-4 py-2 bg-green-600 text-white rounded">Sync Query</button>
        {syncResult && <div className="mt-2 text-sm">Sync Result: {syncResult}</div>}
      </form>
      <form onSubmit={handleAsyncQuery} className="mb-4 flex flex-col gap-2">
        <label className="font-semibold">Async Query</label>
        <input value={asyncQuery} onChange={e => setAsyncQuery(e.target.value)} placeholder="Enter query" className="border px-2 py-1" />
        <button type="submit" className="px-4 py-2 bg-purple-600 text-white rounded">Async Query</button>
        {asyncResult && <div className="mt-2 text-sm">Async Result: {asyncResult}</div>}
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
