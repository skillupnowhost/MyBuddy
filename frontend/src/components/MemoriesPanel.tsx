"use client";

import { useEffect, useState } from "react";
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
    <div className="fixed inset-0 z-20 flex items-center justify-center bg-black/50 px-4">
      <div className="w-full max-w-lg rounded-xl border border-white/10 bg-[#161922] p-6 shadow-xl">
        <div className="mb-1 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Memory</h2>
          <button onClick={onClose} className="text-white/50 hover:text-white">
            &times;
          </button>
        </div>
        <p className="mb-4 text-xs text-white/40">
          Facts MyBuddy remembers about you across conversations. Some are added automatically after a chat; you can
          also add or remove any of them yourself.
        </p>

        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder="e.g. I prefer concise answers"
            className="flex-1 rounded-lg border border-white/10 bg-[#0f1115] px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
          />
          <button
            onClick={handleAdd}
            disabled={!input.trim()}
            className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-500 disabled:opacity-40"
          >
            Add
          </button>
        </div>

        {error && <p className="mt-2 text-sm text-red-400">{error}</p>}

        <div className="mt-4 max-h-80 space-y-2 overflow-y-auto">
          {memories.length === 0 ? (
            <p className="py-6 text-center text-sm text-white/40">No memories yet.</p>
          ) : (
            memories.map((memory) => (
              <div
                key={memory.id}
                className="flex items-center justify-between rounded-lg border border-white/10 px-3 py-2 text-sm"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-white/90">{memory.content}</p>
                  <p className="text-xs text-white/40">{memory.source === "auto" ? "learned automatically" : "added by you"}</p>
                </div>
                <button
                  onClick={() => handleDelete(memory.id)}
                  className="ml-2 text-white/40 hover:text-red-400"
                  aria-label="Delete memory"
                >
                  &times;
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
