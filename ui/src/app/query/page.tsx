'use client';
import { useQuery } from "../lib/query";

export default function QueryPage() {
  const { query, setQuery, syncResult, asyncResult, handleSyncQuery, handleAsyncQuery } = useQuery();

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Query</h1>
      <form onSubmit={handleSyncQuery} className="mb-4 flex flex-col gap-2">
        <label className="font-semibold">Sync Query</label>
        <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Enter query" className="border px-2 py-1" />
        <button type="submit" className="px-4 py-2 bg-green-600 text-white rounded">Sync Query</button>
        {syncResult && <div className="mt-2 text-base font-medium text-gray-800">Sync Answer: {syncResult}</div>}
      </form>
      <form onSubmit={handleAsyncQuery} className="mb-4 flex flex-col gap-2">
        <label className="font-semibold">Async Query</label>
        <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Enter query" className="border px-2 py-1" />
        <button type="submit" className="px-4 py-2 bg-purple-600 text-white rounded">Async Query</button>
        {asyncResult && <div className="mt-2 text-base font-medium text-gray-800">Async Answer: {asyncResult}</div>}
      </form>
    </div>
  );
}
