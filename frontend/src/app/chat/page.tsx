"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import MessageBubble from "@/components/MessageBubble";
import DocumentsPanel from "@/components/DocumentsPanel";
import MemoriesPanel from "@/components/MemoriesPanel";
import AuthedImage from "@/components/AuthedImage";
import { apiJson } from "@/lib/api";
import { getCurrentUser } from "@/lib/admin";
import { clearTokens, isLoggedIn } from "@/lib/auth";
import { deleteImage, uploadImage } from "@/lib/images";
import { streamChatMessage } from "@/lib/stream";
import type { Conversation, ImageItem, Message } from "@/lib/types";

export default function ChatPage() {
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showDocuments, setShowDocuments] = useState(false);
  const [showMemory, setShowMemory] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [pendingImages, setPendingImages] = useState<ImageItem[]>([]);
  const [imageUploading, setImageUploading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);

  const activeConversation = conversations.find((c) => c.id === activeId) ?? null;

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    loadConversations();
    getCurrentUser()
      .then((user) => setIsAdmin(user.role === "ADMIN"))
      .catch(() => {});
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

  async function handleToggleFlag(flag: "rag_enabled" | "tools_enabled") {
    if (!activeConversation) return;
    const updated = await apiJson<Conversation>(`/api/v1/conversations/${activeConversation.id}`, {
      method: "PATCH",
      body: JSON.stringify({ [flag]: !activeConversation[flag] }),
    });
    setConversations((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
  }

  function handleLogout() {
    clearTokens();
    router.replace("/login");
  }

  async function handleAttachImages(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    setError(null);
    setImageUploading(true);
    try {
      const uploaded = await Promise.all(files.map(uploadImage));
      setPendingImages((prev) => [...prev, ...uploaded]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Image upload failed.");
    } finally {
      setImageUploading(false);
      if (imageInputRef.current) imageInputRef.current.value = "";
    }
  }

  async function handleRemovePendingImage(id: string) {
    setPendingImages((prev) => prev.filter((img) => img.id !== id));
    try {
      await deleteImage(id);
    } catch {
      // Already attached elsewhere or already gone — nothing more to do client-side.
    }
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

    const imagesForThisMessage = pendingImages;
    setInput("");
    setPendingImages([]);
    setError(null);
    setMessages((prev) => [
      ...prev,
      {
        id: `local-${Date.now()}`,
        role: "user",
        content,
        created_at: new Date().toISOString(),
        images: imagesForThisMessage,
      },
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
        (sources) => {
          setMessages((prev) => prev.map((m) => (m.id === "streaming" ? { ...m, sources } : m)));
        },
        (toolName) => {
          setMessages((prev) => prev.map((m) => (m.id === "streaming" ? { ...m, toolCall: toolName } : m)));
        },
        imagesForThisMessage.map((img) => img.id),
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
        onOpenDocuments={() => setShowDocuments(true)}
        onOpenMemory={() => setShowMemory(true)}
        isAdmin={isAdmin}
      />

      {showDocuments && <DocumentsPanel onClose={() => setShowDocuments(false)} />}
      {showMemory && <MemoriesPanel onClose={() => setShowMemory(false)} />}

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
          <div className="mx-auto flex max-w-3xl flex-col gap-2">
            {activeConversation && (
              <div className="flex flex-wrap gap-4">
                <label className="flex w-fit items-center gap-2 text-xs text-white/50">
                  <input
                    type="checkbox"
                    checked={activeConversation.rag_enabled}
                    onChange={() => handleToggleFlag("rag_enabled")}
                    className="accent-blue-600"
                  />
                  Use my documents (RAG)
                </label>
                <label className="flex w-fit items-center gap-2 text-xs text-white/50">
                  <input
                    type="checkbox"
                    checked={activeConversation.tools_enabled}
                    onChange={() => handleToggleFlag("tools_enabled")}
                    className="accent-blue-600"
                  />
                  Allow tools (calculator, date/time)
                </label>
              </div>
            )}
            {pendingImages.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {pendingImages.map((img) => (
                  <div key={img.id} className="group relative">
                    <AuthedImage imageId={img.id} className="h-16 w-16 rounded-lg object-cover" />
                    <button
                      onClick={() => handleRemovePendingImage(img.id)}
                      className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-black/80 text-xs text-white/80 hover:bg-red-600"
                      aria-label="Remove image"
                    >
                      &times;
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex items-end gap-2">
              <input
                ref={imageInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                multiple
                onChange={handleAttachImages}
                className="hidden"
              />
              <button
                onClick={() => imageInputRef.current?.click()}
                disabled={imageUploading}
                title="Attach image(s) for MyBuddy Vision"
                className="rounded-xl border border-white/10 px-3 py-3 text-sm text-white/60 hover:bg-white/10 hover:text-white disabled:opacity-40"
              >
                🖼️
              </button>
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
        </div>
      </main>
    </div>
  );
}
