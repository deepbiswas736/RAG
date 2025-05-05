"use client";

import Link from "next/link";
import Image from "next/image";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-8 text-center">
      <h1 className="text-4xl font-bold mb-6">Welcome to RAG Document System</h1>
      
      <div className="max-w-3xl mx-auto bg-white p-8 rounded-lg shadow-md">
        <div className="mb-8 flex justify-center">
          <div className="grid grid-cols-3 gap-6">
            <Image src="/file.svg" alt="Document" width={80} height={80} />
            <Image src="/globe.svg" alt="Global Access" width={80} height={80} />
            <Image src="/window.svg" alt="Interface" width={80} height={80} />
          </div>
        </div>
        
        <p className="text-lg mb-6">
          Our Retrieval-Augmented Generation (RAG) system combines the power of large language models with 
          a specialized document retrieval system to deliver precise, contextual answers based on your uploaded documents.
        </p>
        
        <div className="mb-8">
          <h2 className="text-2xl font-semibold mb-3">Key Features</h2>
          <ul className="text-left list-disc pl-8 space-y-2">
            <li>Document upload and management with automatic processing</li>
            <li>Advanced chunking and embedding for optimal retrieval</li>
            <li>Synchronous queries for immediate responses</li>
            <li>Asynchronous queries for complex document processing</li>
            <li>Support for various document formats</li>
            <li>Secure document storage and handling</li>
          </ul>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
          <Link href="/documents" className="bg-blue-600 text-white py-3 px-6 rounded-lg hover:bg-blue-700 transition-colors">
            Manage Documents
          </Link>
          <Link href="/query" className="bg-green-600 text-white py-3 px-6 rounded-lg hover:bg-green-700 transition-colors">
            Query Documents
          </Link>
          <Link href="/api/documents" className="bg-purple-600 text-white py-3 px-6 rounded-lg hover:bg-purple-700 transition-colors">
            API Documentation
          </Link>
        </div>
      </div>
    </div>
  );
}
