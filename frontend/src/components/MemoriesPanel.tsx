"use client";

import { useEffect, useState } from "react";
import { X, Plus } from "lucide-react";
import { createMemory, deleteMemory, listMemories } from "@/lib/memories";
import type { MemoryItem } from "@/lib/types";

export default function MemoriesPanel({ onClose }: { onClose: () => void }) {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setMemories(await listMemories());
    } catch {
      setError("Could not load memories.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleAdd() {
    const content = input.trim();
    if (!content) return;
    setError(null);
    try {
      const memory = await createMemory(content);
      setMemories((prev) => [memory, ...prev]);
      setInput("");
    } catch {
      setError("Could not save memory.");
    }
  }

  async function handleDelete(id: string) {
    await deleteMemory(id);
    setMemories((prev) => prev.filter((m) => m.id !== id));
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-lg rounded-2xl border border-gray-200 bg-white p-6 shadow-xl">
        <div className="mb-1 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Memory</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-900">
            <X className="h-4 w-4" strokeWidth={2} />
          </button>
        </div>
        <p className="mb-4 text-xs text-gray-400">
          Facts MyBuddy remembers about you across conversations. Some are added automatically after a chat; you can
          also add or remove any of them yourself.
        </p>

        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="e.g. I prefer concise answers"
            className="flex-1 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-400 focus:bg-white"
          />
          <button
            onClick={handleAdd}
            disabled={!input.trim()}
            className="flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-2 text-sm text-white hover:bg-indigo-500 disabled:opacity-40"
          >
            <Plus className="h-4 w-4" strokeWidth={2.5} />
            Add
          </button>
        </div>

        {error && <p className="mt-2 text-sm text-red-500">{error}</p>}

        <div className="mt-4 max-h-80 space-y-2 overflow-y-auto">
          {memories.length === 0 ? (
            <p className="py-6 text-center text-sm text-gray-400">No memories yet.</p>
          ) : (
            memories.map((memory) => (
              <div
                key={memory.id}
                className="flex items-center justify-between rounded-lg border border-gray-200 px-3 py-2 text-sm"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-gray-800">{memory.content}</p>
                  <p className="text-xs text-gray-400">{memory.source === "auto" ? "learned automatically" : "added by you"}</p>
                </div>
                <button
                  onClick={() => handleDelete(memory.id)}
                  className="ml-2 shrink-0 text-gray-400 hover:text-red-500"
                  aria-label="Delete memory"
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
