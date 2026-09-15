"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Image as ImageIcon, Send, Square, X } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import HomeDashboard from "@/components/HomeDashboard";
import MessageBubble from "@/components/MessageBubble";
import DocumentsPanel from "@/components/DocumentsPanel";
import MemoriesPanel from "@/components/MemoriesPanel";
import AuthedImage from "@/components/AuthedImage";
import { apiJson } from "@/lib/api";
import { getCurrentUser } from "@/lib/admin";
import { clearTokens, isLoggedIn } from "@/lib/auth";
import { deleteImage, uploadImage } from "@/lib/images";
import { streamChatMessage } from "@/lib/stream";
import type { Conversation, CurrentUser, ImageItem, Message } from "@/lib/types";

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
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [pendingImages, setPendingImages] = useState<ImageItem[]>([]);
  const [imageUploading, setImageUploading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const activeConversation = conversations.find((c) => c.id === activeId) ?? null;
  const isAdmin = currentUser?.role === "ADMIN";
  const showHome = !activeId && messages.length === 0;

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    loadConversations();
    getCurrentUser()
      .then(setCurrentUser)
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

  function handleHome() {
    setActiveId(null);
    setMessages([]);
  }

  function handlePromptSelect(text: string) {
    setInput(text);
    textareaRef.current?.focus();
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

  const displayName = currentUser?.email ? currentUser.email.split("@")[0].replace(/[._-]/g, " ") : "there";

  return (
    <div className="flex h-screen bg-[#f4f5f9]">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        userEmail={currentUser?.email ?? null}
        onSelect={selectConversation}
        onNew={handleNewConversation}
        onHome={handleHome}
        onDelete={handleDeleteConversation}
        onLogout={handleLogout}
        onOpenDocuments={() => setShowDocuments(true)}
        onOpenMemory={() => setShowMemory(true)}
        isAdmin={isAdmin}
      />

      {showDocuments && <DocumentsPanel onClose={() => setShowDocuments(false)} />}
      {showMemory && <MemoriesPanel onClose={() => setShowMemory(false)} />}

      <main className="flex flex-1 flex-col overflow-hidden">
        <Header userEmail={currentUser?.email ?? null} onLogout={handleLogout} />

        <div className="thin-scroll flex-1 overflow-y-auto">
          {showHome ? (
            <HomeDashboard
              displayName={displayName}
              isAdmin={isAdmin}
              onPromptSelect={handlePromptSelect}
              onOpenDocuments={() => setShowDocuments(true)}
            />
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {error && <p className="mx-auto mb-2 max-w-3xl text-sm text-red-500">{error}</p>}

        <div className="border-t border-gray-200 bg-white p-4">
          <div className="mx-auto flex max-w-3xl flex-col gap-2">
            {activeConversation && (
              <div className="flex flex-wrap gap-4">
                <label className="flex w-fit items-center gap-2 text-xs text-gray-500">
                  <input
                    type="checkbox"
                    checked={activeConversation.rag_enabled}
                    onChange={() => handleToggleFlag("rag_enabled")}
                    className="accent-indigo-600"
                  />
                  Use my documents (RAG)
                </label>
                <label className="flex w-fit items-center gap-2 text-xs text-gray-500">
                  <input
                    type="checkbox"
                    checked={activeConversation.tools_enabled}
                    onChange={() => handleToggleFlag("tools_enabled")}
                    className="accent-indigo-600"
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
                      className="absolute -right-1.5 -top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-black/80 text-white/80 hover:bg-red-600"
                      aria-label="Remove image"
                    >
                      <X className="h-3 w-3" strokeWidth={2.5} />
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
                className="group rounded-xl border border-gray-200 px-3 py-3 text-gray-500 transition hover:bg-gray-100 hover:text-gray-900 disabled:opacity-40"
              >
                <ImageIcon className="h-4 w-4 transition-transform duration-200 group-hover:scale-110" strokeWidth={2} />
              </button>
              <textarea
                ref={textareaRef}
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
                className="max-h-40 flex-1 resize-none rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 outline-none focus:border-indigo-400 focus:bg-white"
              />
              {isStreaming ? (
                <button
                  onClick={handleStop}
                  className="flex items-center gap-1.5 rounded-xl bg-red-600 px-4 py-3 text-sm font-medium text-white hover:bg-red-500"
                >
                  <Square className="h-3.5 w-3.5" fill="currentColor" strokeWidth={0} />
                  Stop
                </button>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="group flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
                >
                  Send
                  <Send className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" strokeWidth={2} />
                </button>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
