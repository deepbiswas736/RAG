"use client";

import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";

interface SourceMetadata {
  page_number?: number;
  content_type?: string;
  [key: string]: unknown;
}

interface Source {
  content: string;
  source: string;
  metadata: SourceMetadata;
}

interface QueryResult {
  status: string;
  answer: string;
  sources: Source[];
}

interface CompletedQuery {
  query_id: string;
  status: string;
  preview: string;
  timestamp?: string;
  source_count: number;
}

export default function AsyncQueryPage() {
  const [query, setQuery] = useState("");
  const [queryId, setQueryId] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const [completedQueries, setCompletedQueries] = useState<CompletedQuery[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);

  // Fetch completed queries on page load
  useEffect(() => {
    fetchCompletedQueries();
  }, []);

  async function fetchCompletedQueries() {
    setIsLoadingHistory(true);
    try {
      const res = await fetch("/api/query/completed");
      if (res.ok) {
        const data = await res.json();
        setCompletedQueries(data);
      } else {
        console.error("Failed to load completed queries");
      }
    } catch (error) {
      console.error("Error fetching completed queries:", error);
    } finally {
      setIsLoadingHistory(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    
    setIsLoading(true);
    setResult(null);
    setQueryId(null);
    
    try {
      const res = await fetch("/api/query/async", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      
      const data = await res.json();
      setQueryId(data.query_id);
    } catch (error) {
      console.error("Error submitting async query:", error);
      setIsLoading(false);
    }
  }

  async function loadQueryResult(queryId: string) {
    if (!queryId) return;
    
    setQueryId(queryId);
    setIsLoading(true);
    setResult(null);
    
    try {
      const res = await fetch(`/api/query/async/${queryId}`);
      const data = await res.json();
      
      if (data.status === "completed" || data.status === "error") {
        setResult(data);
        setIsLoading(false);
      } else {
        // If still processing, start polling
        startPolling(queryId);
      }
    } catch (error) {
      console.error("Error loading query result:", error);
      setIsLoading(false);
    }
  }

  function startPolling(queryId: string) {
    // Start polling for this query ID
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/query/async/${queryId}`);
        const data = await res.json();
        
        if (data.status === "completed" || data.status === "error") {
          setResult(data);
          setIsLoading(false);
          clearInterval(interval);
          
          // Refresh completed queries list
          fetchCompletedQueries();
        }
      } catch (error) {
        console.error("Error polling for results:", error);
        setIsLoading(false);
        clearInterval(interval);
      }
    }, 2000);
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }

  useEffect(() => {
    let interval: NodeJS.Timeout;
    
    if (queryId) {
      interval = setInterval(async () => {
        try {
          const res = await fetch(`/api/query/async/${queryId}`);
          const data = await res.json();
          
          if (data.status === "completed" || data.status === "error") {
            setResult(data);
            setIsLoading(false);
            clearInterval(interval);
            
            // Refresh completed queries list after a new query is completed
            fetchCompletedQueries();
          }
        } catch (error) {
          console.error("Error polling for results:", error);
          setIsLoading(false);
          clearInterval(interval);
        }
      }, 2000);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [queryId]);

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Asynchronous Query</h1>
      <p className="mb-4 text-gray-600">
        Submit your query for background processing. Results will be available once processing is complete.
      </p>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="md:col-span-2">
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
                  : "bg-purple-600 hover:bg-purple-700 text-white"
              }`}
            >
              {isLoading ? "Processing..." : "Submit Query"}
            </button>
          </form>
        </div>
        
        <div className="border rounded-md p-4 bg-gray-50">
          <h2 className="text-lg font-semibold mb-3">Previous Queries</h2>
          {isLoadingHistory ? (
            <div className="animate-pulse text-gray-500">Loading...</div>
          ) : completedQueries.length > 0 ? (
            <ul className="divide-y">
              {completedQueries.map((item) => (
                <li key={item.query_id} className="py-2">
                  <button
                    onClick={() => loadQueryResult(item.query_id)}
                    className="w-full text-left hover:bg-gray-100 p-1 rounded transition-colors"
                  >
                    <p className="text-sm line-clamp-2 text-gray-800">{item.preview}</p>
                    <div className="flex justify-between text-xs text-gray-500 mt-1">
                      <span>{item.status === "completed" ? "✓" : "⚠️"} {item.source_count} sources</span>
                      <span>{item.timestamp || "Recently completed"}</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-gray-500 text-sm">No completed queries yet.</p>
          )}
        </div>
      </div>

      {queryId && isLoading && (
        <div className="mt-6 p-4 bg-yellow-50 border border-yellow-200 rounded-md">
          <div className="flex items-center space-x-2">
            <svg className="animate-spin h-5 w-5 text-yellow-500" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              ></circle>
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              ></path>
            </svg>
            <span>Processing your query... (ID: {queryId})</span>
          </div>
        </div>
      )}

      {result && (
        <div className="mt-8">
          <div className="mb-6">
            <h2 className="text-xl font-semibold mb-2">Answer:</h2>
            <div className="border rounded-md p-4 bg-white shadow-inner min-h-[150px] text-base text-gray-800">
              <div className="prose prose-slate max-w-none">
                <ReactMarkdown>{result.answer}</ReactMarkdown>
              </div>
            </div>
          </div>
          
          {result.sources && result.sources.length > 0 && (
            <div>
              <div className="flex items-center justify-between">
                <h2 className="text-xl font-semibold mb-2">Sources:</h2>
                <button
                  onClick={() => setShowSources(!showSources)}
                  className="text-blue-600 hover:text-blue-800 text-sm"
                >
                  {showSources ? "Hide Sources" : "Show Sources"}
                </button>
              </div>
              
              {showSources && (
                <div className="mt-2 border rounded-md divide-y">
                  {result.sources.map((source, index) => (
                    <div key={index} className="p-3">
                      <div className="font-medium mb-1 text-gray-700">
                        {source.source}
                      </div>
                      <div className="text-sm text-gray-600 mb-2">
                        {source.metadata?.page_number && (
                          <span className="mr-2">Page: {source.metadata.page_number}</span>
                        )}
                        {source.metadata?.content_type && (
                          <span>Type: {source.metadata.content_type}</span>
                        )}
                      </div>
                      <div className="text-sm border-l-2 border-gray-300 pl-3 mt-1 line-clamp-3 hover:line-clamp-none">
                        {source.content}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}