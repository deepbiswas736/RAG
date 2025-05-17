"use client";

import { useState } from "react";

export function useQuery() {
  const [query, setQuery] = useState("");
  const [syncResult, setSyncResult] = useState("");
  const [asyncResult, setAsyncResult] = useState("");
  const [, setAsyncId] = useState(""); // Changed this line

  async function handleSyncQuery(e: React.FormEvent) {
    e.preventDefault();
    setSyncResult("Loading...");
    const res = await fetch("/api/query/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    setSyncResult(await res.text());
  }

  async function handleAsyncQuery(e: React.FormEvent) {
    e.preventDefault();
    setAsyncResult("Submitting...");
    const res = await fetch("/api/query/async", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    setAsyncId(data.query_id);
    setAsyncResult("Processing...");
    pollAsyncResult(data.query_id);
  }

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

  return {
    query,
    setQuery,
    syncResult,
    asyncResult,
    handleSyncQuery,
    handleAsyncQuery,
  };
}
