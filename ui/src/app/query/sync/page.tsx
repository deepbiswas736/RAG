"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";

export default function SyncQueryPage() {
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState("");
  const resultRef = useRef<HTMLDivElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    
    setIsLoading(true);
    setResult("");
    
    try {
      const response = await fetch("/api/query/sync", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      
      // Create a reader for the stream
      const reader = response.body?.getReader();
      if (!reader) throw new Error("Failed to create stream reader");
      
      // Read the stream
      const decoder = new TextDecoder();
      let done = false;
      
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        
        if (value) {
          const chunk = decoder.decode(value, { stream: !done });
          setResult(prev => prev + chunk);
        }
      }
    } catch (error) {
      console.error("Error during sync query:", error);
      setResult("An error occurred while processing your query.");
    } finally {
      setIsLoading(false);
    }
  }

  // Scroll to bottom of results when they update
  useEffect(() => {
    if (resultRef.current) {
      resultRef.current.scrollTop = resultRef.current.scrollHeight;
    }
  }, [result]);

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Synchronous Query</h1>
      <p className="mb-4 text-gray-600">
        Get real-time streamed answers to your questions. Results are processed immediately and streamed back as they are generated.
      </p>
      
      <form onSubmit={handleSubmit} className="mb-6">
        <div className="flex flex-col space-y-2">
          <label htmlFor="query" className="font-medium">
            Your Question:
          </label>
          <textarea
            id="query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="border rounded-md p-2 min-h-[100px]"
            placeholder="Enter your question here..."
            disabled={isLoading}
          />
        </div>
        <button
          type="submit"
          disabled={isLoading}
          className={`mt-4 px-4 py-2 rounded-md ${
            isLoading
              ? "bg-gray-400 cursor-not-allowed"
              : "bg-blue-600 hover:bg-blue-700 text-white"
          }`}
        >
          {isLoading ? "Processing..." : "Submit Query"}
        </button>
      </form>

      {(result || isLoading) && (
        <div className="mt-6">
          <h2 className="text-xl font-semibold mb-2">Answer:</h2>
          <div
            ref={resultRef}
            className="border rounded-md p-4 bg-white shadow-inner min-h-[200px] max-h-[500px] overflow-y-auto whitespace-pre-wrap text-base text-gray-800"
          >
            {isLoading && !result && <div className="animate-pulse">Processing query...</div>}
            <div className="prose prose-slate max-w-none">
              <ReactMarkdown>{result}</ReactMarkdown>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}