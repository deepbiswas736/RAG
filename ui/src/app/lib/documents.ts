import { useState, useRef, useEffect } from "react";

export interface Document {
  id: string;
  title: string;
  file?: string;
  metadata?: Record<string, unknown>;
}

export function useDocuments() {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function fetchDocuments() {
    setIsLoading(true);
    try {
      const res = await fetch("/api/documents");
      if (res.ok) {
        setDocuments(await res.json());
      } else {
        console.error("Failed to fetch documents");
      }
    } catch (error) {
      console.error("Error fetching documents:", error);
    } finally {
      setIsLoading(false);
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
    try {
      const res = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        setUploadStatus("Upload successful!");
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
        fetchDocuments();
      } else {
        setUploadStatus("Upload failed.");
      }
    } catch (error) {
      console.error("Error uploading document:", error);
      setUploadStatus("Upload failed due to an error.");
    }
  }

  async function deleteDocument(id: string) {
    if (!confirm("Are you sure you want to delete this document?")) {
      return;
    }
    
    setIsLoading(true);
    try {
      const res = await fetch(`/api/documents/${id}`, {
        method: "DELETE",
      });
      
      if (res.ok) {
        // Update documents list after successful deletion
        fetchDocuments();
      } else {
        console.error("Failed to delete document");
        alert("Failed to delete document. Please try again.");
      }
    } catch (error) {
      console.error("Error deleting document:", error);
      alert("An error occurred while deleting the document.");
    } finally {
      setIsLoading(false);
    }
  }

  async function downloadDocument(id: string, title: string) {
    setIsLoading(true);
    try {
      const res = await fetch(`/api/documents/${id}/download`);
      
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = title || `document-${id}.pdf`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } else {
        console.error("Failed to download document");
        alert("Failed to download document. Please try again.");
      }
    } catch (error) {
      console.error("Error downloading document:", error);
      alert("An error occurred while downloading the document.");
    } finally {
      setIsLoading(false);
    }
  }

  return { 
    documents, 
    uploadStatus, 
    fileInputRef, 
    handleUpload, 
    deleteDocument, 
    downloadDocument,
    isLoading,
    fetchDocuments
  };
}
