import { useState, useRef, useEffect } from "react";

export function useDocuments() {
  const [documents, setDocuments] = useState<any[]>([]);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function fetchDocuments() {
    const res = await fetch("/api/documents");
    if (res.ok) {
      setDocuments(await res.json());
    }
  }

  useEffect(() => { fetchDocuments(); }, []);

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

  return { documents, uploadStatus, fileInputRef, handleUpload };
}
