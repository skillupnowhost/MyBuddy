"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import MessageBubble from "@/components/MessageBubble";
import { apiJson } from "@/lib/api";
import { clearTokens, isLoggedIn } from "@/lib/auth";
import { streamChatMessage } from "@/lib/stream";
import type { Conversation, Message } from "@/lib/types";

export default function ChatPage() {
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    loadConversations();
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function loadConversations() {
    try {
      const convos = await apiJson<Conversation[]>("/api/v1/conversations");
      setConversations(convos);
      if (convos.length > 0 && !activeId) {
        selectConversation(convos[0].id);
      }
    } catch {
      setError("Could not load conversations.");
    }
  }

  async function selectConversation(id: string) {
    setActiveId(id);
    try {
      const detail = await apiJson<Conversation & { messages: Message[] }>(`/api/v1/conversations/${id}`);
      setMessages(detail.messages);
    } catch {
      setError("Could not load conversation.");
    }
  }

  async function handleNewConversation() {
    const conversation = await apiJson<Conversation>("/api/v1/conversations", {
      method: "POST",
      body: JSON.stringify({}),
    });
    setConversations((prev) => [conversation, ...prev]);
    setActiveId(conversation.id);
    setMessages([]);
  }

  async function handleDeleteConversation(id: string) {
    await apiJson(`/api/v1/conversations/${id}`, { method: "DELETE" });
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeId === id) {
      setActiveId(null);
      setMessages([]);
    }
  }

  function handleLogout() {
    clearTokens();
    router.replace("/login");
  }

  async function handleSend() {
    const content = input.trim();
    if (!content || isStreaming) return;

    let conversationId = activeId;
    if (!conversationId) {
      const conversation = await apiJson<Conversation>("/api/v1/conversations", {
        method: "POST",
        body: JSON.stringify({}),
      });
      setConversations((prev) => [conversation, ...prev]);
      conversationId = conversation.id;
      setActiveId(conversationId);
    }

    setInput("");
    setError(null);
    setMessages((prev) => [
      ...prev,
      { id: `local-${Date.now()}`, role: "user", content, created_at: new Date().toISOString() },
      { id: "streaming", role: "assistant", content: "", created_at: new Date().toISOString() },
    ]);

    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);

    try {
      let assembled = "";
      await streamChatMessage(
        conversationId,
        content,
        (delta) => {
          assembled += delta;
          setMessages((prev) => prev.map((m) => (m.id === "streaming" ? { ...m, content: assembled } : m)));
        },
        controller.signal,
      );
    } catch (err) {
      if (!(err instanceof DOMException && err.name === "AbortError")) {
        setError("The message could not be sent. Is the backend running?");
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
      setMessages((prev) => prev.map((m) => (m.id === "streaming" ? { ...m, id: `assistant-${Date.now()}` } : m)));
      loadConversations();
    }
  }

  function handleStop() {
    abortRef.current?.abort();
  }

  return (
    <div className="flex h-screen bg-[#0f1115]">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={selectConversation}
        onNew={handleNewConversation}
        onDelete={handleDeleteConversation}
        onLogout={handleLogout}
      />

      <main className="flex flex-1 flex-col">
        <div className="flex-1 overflow-y-auto px-4 py-6">
          {messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center text-white/40">
              <h2 className="mb-2 text-xl font-medium text-white/70">Meet MyBuddy</h2>
              <p className="text-sm">Your private, self-hosted AI companion. Ask me anything.</p>
            </div>
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {error && <p className="mx-auto mb-2 max-w-3xl text-sm text-red-400">{error}</p>}

        <div className="border-t border-white/10 p-4">
          <div className="mx-auto flex max-w-3xl items-end gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="Message MyBuddy..."
              rows={1}
              className="max-h-40 flex-1 resize-none rounded-xl border border-white/10 bg-[#161922] px-4 py-3 text-sm text-white outline-none focus:border-blue-500"
            />
            {isStreaming ? (
              <button
                onClick={handleStop}
                className="rounded-xl bg-red-600 px-4 py-3 text-sm font-medium text-white hover:bg-red-500"
              >
                Stop
              </button>
            ) : (
              <button
                onClick={handleSend}
                disabled={!input.trim()}
                className="rounded-xl bg-blue-600 px-4 py-3 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
              >
                Send
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
