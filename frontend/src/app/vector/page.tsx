"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import VectorCanvas from "@/components/VectorCanvas";
import VectorPropertyPanel from "@/components/VectorPropertyPanel";
import { isLoggedIn } from "@/lib/auth";
import {
  createVectorDocument,
  deleteVectorDocument,
  downloadVectorDocument,
  editVectorDocument,
  getVectorDocument,
  listVectorDocuments,
} from "@/lib/vector";
import type { VectorDocumentItem, VectorDocumentPurpose, VectorObjectItem } from "@/lib/types";

const PURPOSE_OPTIONS: { value: VectorDocumentPurpose; label: string }[] = [
  { value: "GENERAL", label: "General" },
  { value: "ILLUSTRATION", label: "Illustration" },
  { value: "LOGO", label: "Logo" },
  { value: "ICON", label: "Icon" },
];

export default function VectorPage() {
  const router = useRouter();
  const [documents, setDocuments] = useState<VectorDocumentItem[]>([]);
  const [activeDocument, setActiveDocument] = useState<VectorDocumentItem | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [prompt, setPrompt] = useState("");
  const [purpose, setPurpose] = useState<VectorDocumentPurpose>("GENERAL");
  const [instruction, setInstruction] = useState("");
  const [generating, setGenerating] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const promptRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    refreshList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function refreshList() {
    try {
      setDocuments(await listVectorDocuments());
    } catch {
      setError("Could not load vector documents.");
    }
  }

  async function handleGenerate() {
    const trimmed = prompt.trim();
    if (!trimmed || generating) return;
    setError(null);
    setGenerating(true);
    try {
      const doc = await createVectorDocument(trimmed, purpose);
      setDocuments((prev) => [doc, ...prev]);
      setActiveDocument(doc);
      setSelectedId(null);
      setPrompt("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate a vector document.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSelectDocument(id: string) {
    try {
      const doc = await getVectorDocument(id);
      setActiveDocument(doc);
      setSelectedId(null);
    } catch {
      setError("Could not load that document.");
    }
  }

  async function handleDeleteDocument(id: string) {
    await deleteVectorDocument(id);
    setDocuments((prev) => prev.filter((d) => d.id !== id));
    if (activeDocument?.id === id) {
      setActiveDocument(null);
      setSelectedId(null);
    }
  }

  async function handleEdit() {
    const trimmed = instruction.trim();
    if (!trimmed || !activeDocument || editing) return;
    setError(null);
    setEditing(true);
    try {
      const updated = await editVectorDocument(activeDocument.id, trimmed);
      setActiveDocument(updated);
      setInstruction("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not apply that edit.");
    } finally {
      setEditing(false);
    }
  }

  function handleObjectUpdated(updated: VectorObjectItem) {
    setActiveDocument((prev) =>
      prev ? { ...prev, objects: prev.objects.map((o) => (o.id === updated.id ? updated : o)) } : prev,
    );
  }

  async function handleExport() {
    if (!activeDocument) return;
    try {
      await downloadVectorDocument(activeDocument.id, activeDocument.title || "vector");
    } catch {
      setError("Could not export this document.");
    }
  }

  const selectedObject = activeDocument?.objects.find((o) => o.id === selectedId) ?? null;

  return (
    <div className="flex h-screen flex-col bg-[#0f1115] text-white">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
        <h1 className="text-lg font-semibold">MyBuddy Vector</h1>
        <Link href="/chat" className="text-sm text-blue-400 hover:underline">
          &larr; Back to chat
        </Link>
      </div>

      {error && <p className="border-b border-white/10 bg-red-950/30 px-4 py-2 text-sm text-red-400">{error}</p>}

      <div className="flex flex-1 overflow-hidden">
        {/* Left: documents */}
        <aside className="flex w-64 shrink-0 flex-col border-r border-white/10 bg-[#12141c]">
          <div className="space-y-2 p-3">
            <textarea
              ref={promptRef}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe an image: a red circle next to a blue square"
              rows={3}
              className="w-full resize-none rounded-lg border border-white/10 bg-[#0f1115] px-2 py-1.5 text-xs text-white outline-none focus:border-blue-500"
            />
            <select
              value={purpose}
              onChange={(e) => setPurpose(e.target.value as VectorDocumentPurpose)}
              className="w-full rounded-lg border border-white/10 bg-[#0f1115] px-2 py-1.5 text-xs text-white"
            >
              {PURPOSE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <button
              onClick={handleGenerate}
              disabled={!prompt.trim() || generating}
              className="w-full rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500 disabled:opacity-40"
            >
              {generating ? "Generating..." : "+ New document"}
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-2">
            {documents.map((d) => (
              <div
                key={d.id}
                className={`group flex items-center justify-between rounded-lg px-2 py-2 text-sm ${
                  d.id === activeDocument?.id ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5 hover:text-white"
                }`}
              >
                <button onClick={() => handleSelectDocument(d.id)} className="flex-1 truncate text-left text-xs">
                  {d.title}
                </button>
                <button
                  onClick={() => handleDeleteDocument(d.id)}
                  className="ml-1 opacity-0 transition group-hover:opacity-100 hover:text-red-400"
                  aria-label="Delete document"
                >
                  &times;
                </button>
              </div>
            ))}
            {documents.length === 0 && <p className="py-6 text-center text-xs text-white/40">No documents yet.</p>}
          </div>
        </aside>

        {/* Center: canvas + NL edit */}
        <main className="flex flex-1 flex-col items-center overflow-auto border-r border-white/10 p-6">
          {activeDocument ? (
            <>
              <VectorCanvas document={activeDocument} selectedId={selectedId} onSelect={setSelectedId} />
              <div className="mt-4 flex w-full max-w-xl items-center gap-2">
                <input
                  value={instruction}
                  onChange={(e) => setInstruction(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleEdit()}
                  placeholder='Natural-language edit, e.g. "make the circle red"'
                  className="flex-1 rounded-lg border border-white/10 bg-[#161922] px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
                />
                <button
                  onClick={handleEdit}
                  disabled={!instruction.trim() || editing}
                  className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
                >
                  {editing ? "Applying..." : "Apply"}
                </button>
                <button
                  onClick={handleExport}
                  className="rounded-lg border border-white/10 px-3 py-2 text-sm text-white/70 hover:bg-white/10 hover:text-white"
                >
                  Export SVG
                </button>
              </div>
            </>
          ) : (
            <p className="mt-20 text-sm text-white/40">Generate or select a document to start editing.</p>
          )}
        </main>

        {/* Right: property panel */}
        <aside className="w-72 shrink-0 bg-[#12141c]">
          {activeDocument && (
            <VectorPropertyPanel documentId={activeDocument.id} object={selectedObject} onUpdated={handleObjectUpdated} />
          )}
        </aside>
      </div>
    </div>
  );
}
