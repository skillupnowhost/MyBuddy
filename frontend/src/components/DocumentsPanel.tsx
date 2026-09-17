"use client";

import { useEffect, useRef, useState } from "react";
import { LoaderCircle, RotateCcw, X, Upload } from "lucide-react";
import { deleteDocument, listDocuments, retryDocument, uploadDocument } from "@/lib/documents";
import type { DocumentItem, DocumentStatus } from "@/lib/types";

const STATUS_STYLES: Record<DocumentStatus, string> = {
  UPLOADING: "text-gray-400",
  PROCESSING: "text-amber-500",
  EMBEDDING: "text-amber-500",
  READY: "text-emerald-600",
  FAILED: "text-red-500",
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function DocumentsPanel({ onClose }: { onClose: () => void }) {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    try {
      setDocuments(await listDocuments());
    } catch {
      setError("Could not load documents.");
    }
  }

  useEffect(() => {
    refresh();
    const interval = setInterval(() => {
      setDocuments((prev) => {
        if (prev.some((d) => d.status === "UPLOADING" || d.status === "PROCESSING" || d.status === "EMBEDDING")) {
          refresh();
        }
        return prev;
      });
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  async function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const doc = await uploadDocument(file);
      setDocuments((prev) => [doc, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDelete(id: string) {
    await deleteDocument(id);
    setDocuments((prev) => prev.filter((d) => d.id !== id));
  }

  async function handleRetry(id: string) {
    setRetryingId(id);
    setError(null);
    try {
      const retried = await retryDocument(id);
      setDocuments((prev) => prev.map((doc) => (doc.id === id ? retried : doc)));
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not retry document.");
    } finally {
      setRetryingId(null);
    }
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-lg rounded-2xl border border-gray-200 bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Knowledge base</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-900">
            <X className="h-4 w-4" strokeWidth={2} />
          </button>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt,.md,.docx"
          onChange={handleFileSelected}
          className="hidden"
        />
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="group flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-gray-300 py-3 text-sm text-gray-500 transition hover:border-indigo-400 hover:text-gray-900 disabled:opacity-50"
        >
          <Upload className="h-4 w-4 transition-transform duration-200 group-hover:-translate-y-0.5" strokeWidth={2} />
          {uploading ? "Uploading..." : "Upload a document (PDF, TXT, MD, DOCX)"}
        </button>

        {error && <p className="mt-2 text-sm text-red-500">{error}</p>}

        <div className="mt-4 max-h-80 space-y-2 overflow-y-auto">
          {documents.length === 0 ? (
            <p className="py-6 text-center text-sm text-gray-400">No documents yet.</p>
          ) : (
            documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2 text-sm"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-gray-800">{doc.filename}</p>
                  <p className="text-xs text-gray-400" title={doc.error_message || undefined}>
                    {formatSize(doc.size_bytes)} ·{" "}
                    <span className={STATUS_STYLES[doc.status]}>{doc.status.toLowerCase()}</span>
                    {doc.error_message ? `: ${doc.error_message}` : ""}
                  </p>
                </div>
                {doc.status === "FAILED" && (
                  <button
                    onClick={() => handleRetry(doc.id)}
                    disabled={retryingId === doc.id}
                    className="ml-2 shrink-0 text-gray-400 hover:text-indigo-600 disabled:opacity-50"
                    aria-label="Retry document processing"
                    title="Retry document processing"
                  >
                    {retryingId === doc.id ? (
                      <LoaderCircle className="h-4 w-4 animate-spin" strokeWidth={2} />
                    ) : (
                      <RotateCcw className="h-4 w-4" strokeWidth={2} />
                    )}
                  </button>
                )}
                <button
                  onClick={() => handleDelete(doc.id)}
                  className="ml-2 shrink-0 text-gray-400 hover:text-red-500"
                  aria-label="Delete document"
                >
                  <X className="h-4 w-4" strokeWidth={2} />
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
