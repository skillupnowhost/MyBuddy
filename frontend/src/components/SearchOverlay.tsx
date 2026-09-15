"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { MessageSquare, Search, X } from "lucide-react";
import { TOOL_LINKS, PROJECT_LINKS } from "@/lib/navigation";
import type { Conversation } from "@/lib/types";

interface SearchOverlayProps {
  open: boolean;
  onClose: () => void;
  conversations: Conversation[];
  onSelectConversation: (id: string) => void;
}

export default function SearchOverlay({ open, onClose, conversations, onSelectConversation }: SearchOverlayProps) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  const q = query.trim().toLowerCase();

  const matchedConversations = useMemo(
    () => (q ? conversations.filter((c) => c.title.toLowerCase().includes(q)) : conversations.slice(0, 6)),
    [conversations, q],
  );

  const matchedLinks = useMemo(() => {
    const seen = new Set<string>();
    const deduped = [...PROJECT_LINKS, ...TOOL_LINKS].filter((t) => {
      if (seen.has(t.href)) return false;
      seen.add(t.href);
      return true;
    });
    return deduped.filter((t) => !q || t.label.toLowerCase().includes(q));
  }, [q]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-4 pt-20 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex max-h-[70vh] w-full max-w-xl flex-col overflow-hidden rounded-3xl bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 border-b border-gray-100 px-4 py-3">
          <Search className="h-4 w-4 shrink-0 text-gray-400" strokeWidth={2} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search conversations, tools & projects..."
            className="flex-1 bg-transparent text-sm text-gray-900 outline-none placeholder:text-gray-400"
          />
          <button
            onClick={onClose}
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
            aria-label="Close search"
          >
            <X className="h-4 w-4" strokeWidth={2.5} />
          </button>
        </div>

        <div className="thin-scroll flex-1 overflow-y-auto p-2">
          {matchedConversations.length > 0 && (
            <div className="mb-2">
              <p className="px-2 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                Conversations
              </p>
              {matchedConversations.map((c) => (
                <button
                  key={c.id}
                  onClick={() => {
                    onSelectConversation(c.id);
                    onClose();
                  }}
                  className="flex w-full items-center gap-2.5 rounded-2xl px-3 py-2 text-left text-sm text-gray-700 transition hover:bg-indigo-50"
                >
                  <MessageSquare className="h-4 w-4 shrink-0 text-gray-400" strokeWidth={2} />
                  <span className="truncate">{c.title}</span>
                </button>
              ))}
            </div>
          )}

          {matchedLinks.length > 0 && (
            <div>
              <p className="px-2 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">
                Tools &amp; Projects
              </p>
              {matchedLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={onClose}
                  className="flex w-full items-center gap-2.5 rounded-2xl px-3 py-2 text-left text-sm text-gray-700 transition hover:bg-indigo-50"
                >
                  <link.icon className="h-4 w-4 shrink-0 text-gray-400" strokeWidth={2} />
                  {link.label}
                </Link>
              ))}
            </div>
          )}

          {matchedConversations.length === 0 && matchedLinks.length === 0 && (
            <p className="px-3 py-6 text-center text-sm text-gray-400">No matches for &ldquo;{query}&rdquo;</p>
          )}
        </div>
      </div>
    </div>
  );
}
