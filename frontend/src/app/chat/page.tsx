"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Paperclip, Send, Square, X, Mic, Headphones, Image as ImageIcon, Video, FileText, Music } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import { MobileTopBar } from "@/components/MobileNav";
import AnimatedIcon from "@/components/AnimatedIcon";
import { LoadingDots } from "@/components/LoadingIcons";
import HomeDashboard from "@/components/HomeDashboard";
import MessageBubble from "@/components/MessageBubble";
import DocumentsPanel from "@/components/DocumentsPanel";
import MemoriesPanel from "@/components/MemoriesPanel";
import AuthedImage from "@/components/AuthedImage";
import SearchOverlay from "@/components/SearchOverlay";
import VoiceAssistant from "@/components/VoiceAssistant";
import { apiJson } from "@/lib/api";
import { getCurrentUser } from "@/lib/admin";
import { clearTokens, isLoggedIn } from "@/lib/auth";
import { uploadDocument } from "@/lib/documents";
import { deleteImage, uploadImage } from "@/lib/images";
import { streamChatMessage } from "@/lib/stream";
import { isSpeechRecognitionSupported, useSpeechRecognition } from "@/lib/useSpeechRecognition";
import type { LibraryActionKey } from "@/lib/navigation";
import type { Conversation, CurrentUser, ImageItem, Message } from "@/lib/types";

const TRANSIENT_RETRY_DELAY_MS = 900;
const COMPOSER_MAX_HEIGHT_PX = 240;

const ATTACH_OPTIONS = [
  { key: "image", label: "Image", icon: ImageIcon, enabled: true },
  { key: "video", label: "Video", icon: Video, enabled: false },
  { key: "files", label: "Files", icon: FileText, enabled: true },
  { key: "audio", label: "Audio", icon: Music, enabled: false },
] as const;

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
  const [searchOpen, setSearchOpen] = useState(false);
  const [voiceOpen, setVoiceOpen] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [pendingImages, setPendingImages] = useState<ImageItem[]>([]);
  const [imageUploading, setImageUploading] = useState(false);
  const [attachMenuOpen, setAttachMenuOpen] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [thinkingSeconds, setThinkingSeconds] = useState(0);
  const abortRef = useRef<AbortController | null>(null);
  // Synchronous guard against a double-send: two rapid Enter presses (or a click that lands
  // right as a keydown handler fires) can both read isStreaming as false before either
  // send's setIsStreaming(true) has actually committed — a plain state check races, a ref
  // set the instant a send starts does not.
  const sendingRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const attachMenuRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const dictationBaseRef = useRef("");

  const activeConversation = conversations.find((c) => c.id === activeId) ?? null;
  const isAdmin = currentUser?.role === "ADMIN";
  const showHome = !activeId && messages.length === 0;
  const lastAssistantMessage = [...messages].reverse().find((m) => m.role === "assistant") ?? null;
  const streamingMessage = messages.find((m) => m.id === "streaming");
  // Shown centered above the composer while the assistant's reply is still empty — once real
  // content, a tool result, sources, or an image arrives, the bubble itself takes over.
  const showThinkingIndicator =
    isStreaming &&
    !!streamingMessage &&
    !streamingMessage.content &&
    !streamingMessage.toolCall &&
    !(streamingMessage.sources && streamingMessage.sources.length > 0) &&
    !(streamingMessage.images && streamingMessage.images.length > 0);

  const {
    listening: dictationListening,
    start: startDictation,
    stop: stopDictation,
  } = useSpeechRecognition({
    onResult: (transcript, isFinal) => {
      setInput(`${dictationBaseRef.current}${dictationBaseRef.current && transcript ? " " : ""}${transcript}`);
      if (isFinal) stopDictation();
    },
  });

  useEffect(() => {
    setSpeechSupported(isSpeechRecognitionSupported());
  }, []);

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

  useEffect(() => {
    if (!attachMenuOpen) return;
    function handleClickOutside(e: MouseEvent) {
      if (attachMenuRef.current && !attachMenuRef.current.contains(e.target as Node)) setAttachMenuOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [attachMenuOpen]);

  useEffect(() => {
    if (!notice) return;
    const t = window.setTimeout(() => setNotice(null), 5000);
    return () => window.clearTimeout(t);
  }, [notice]);

  // Local CPU-only inference can genuinely take a minute or more to produce a first token on
  // a long or complex prompt (measured directly: ~57s for a moderately complex one on this
  // hardware) — with nothing but three static dots, that reads as broken well before it
  // actually times out. Ticking a visible counter and stepping through progressively more
  // reassuring copy is the fix: same wait, but it now looks like it's working.
  useEffect(() => {
    if (!showThinkingIndicator) {
      setThinkingSeconds(0);
      return;
    }
    const id = window.setInterval(() => setThinkingSeconds((s) => s + 1), 1000);
    return () => window.clearInterval(id);
  }, [showThinkingIndicator]);

  // Auto-grow the composer: resetting to "auto" before reading scrollHeight is what makes it
  // shrink back down too, not just grow — without the reset, scrollHeight only ever reports
  // the tallest the box has already been. Capped at COMPOSER_MAX_HEIGHT_PX so a very long
  // paste scrolls inside the box instead of pushing the send button off-screen.
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, COMPOSER_MAX_HEIGHT_PX)}px`;
  }, [input]);

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

  function handleLibraryAction(key: LibraryActionKey) {
    if (key === "documents") setShowDocuments(true);
    else if (key === "memory") setShowMemory(true);
  }

  function toggleDictation() {
    if (dictationListening) {
      stopDictation();
    } else {
      dictationBaseRef.current = input.trim();
      startDictation();
    }
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

  async function handleAttachFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setImageUploading(true);
    try {
      await uploadDocument(file);
      setNotice(`Added "${file.name}" to your documents. Turn on "Use my documents" below to ask about it.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "File upload failed.");
    } finally {
      setImageUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
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

  // Sends a message end-to-end, resilient to transient failures: a new conversation is
  // created if needed, one silent retry is attempted on a dropped stream, and — only if that
  // also fails — the user's own message is marked "failed" in place with a retry affordance,
  // instead of surfacing a raw error banner.
  async function sendMessage(content: string, imagesForThisMessage: ImageItem[], retryMessageId?: string) {
    let conversationId = activeId;
    if (!conversationId) {
      try {
        const conversation = await apiJson<Conversation>("/api/v1/conversations", {
          method: "POST",
          body: JSON.stringify({}),
        });
        setConversations((prev) => [conversation, ...prev]);
        conversationId = conversation.id;
        setActiveId(conversationId);
      } catch {
        if (retryMessageId) {
          setMessages((prev) => prev.map((m) => (m.id === retryMessageId ? { ...m, status: "failed" } : m)));
        } else {
          setMessages((prev) => [
            ...prev,
            {
              id: `local-${Date.now()}`,
              role: "user",
              content,
              created_at: new Date().toISOString(),
              images: imagesForThisMessage,
              status: "failed",
            },
          ]);
        }
        return;
      }
    }

    let userMessageId = retryMessageId ?? `local-${Date.now()}`;
    // Once the server confirms it actually persisted the user's message, a "transient
    // failure" retry must NOT resend — the backend creates a brand-new user message on every
    // POST unconditionally, so retrying after the message already landed doesn't recover
    // from the failure, it duplicates the turn and starts a second, competing generation on
    // top of whatever's still running from the first (which on slow CPU-only inference makes
    // both attempts more likely to time out — exactly "sends multiple times, no reply ever
    // comes back"). Only retry when the request failed before that point, e.g. the network
    // request itself never reached the server.
    let userMessagePersisted = false;
    setError(null);
    setMessages((prev) => {
      const withoutStreaming = prev.filter((m) => m.id !== "streaming");
      const withUserMessage = retryMessageId
        ? withoutStreaming.map((m) => (m.id === retryMessageId ? { ...m, status: undefined } : m))
        : [
            ...withoutStreaming,
            {
              id: userMessageId,
              role: "user" as const,
              content,
              created_at: new Date().toISOString(),
              images: imagesForThisMessage,
            },
          ];
      return [...withUserMessage, { id: "streaming", role: "assistant" as const, content: "", created_at: new Date().toISOString() }];
    });

    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);

    const attempt = async (isRetry: boolean): Promise<boolean> => {
      try {
        let assembled = "";
        await streamChatMessage(
          conversationId as string,
          content,
          (delta) => {
            assembled += delta;
            setMessages((prev) => prev.map((m) => (m.id === "streaming" ? { ...m, content: assembled } : m)));
          },
          controller.signal,
          (sources) => setMessages((prev) => prev.map((m) => (m.id === "streaming" ? { ...m, sources } : m))),
          (toolName) => setMessages((prev) => prev.map((m) => (m.id === "streaming" ? { ...m, toolCall: toolName } : m))),
          imagesForThisMessage.map((img) => img.id),
          (imageId) =>
            setMessages((prev) =>
              prev.map((m) =>
                m.id === "streaming"
                  ? {
                      ...m,
                      images: [
                        ...(m.images ?? []),
                        { id: imageId, content_type: "image/png", size_bytes: 0, created_at: new Date().toISOString() },
                      ],
                    }
                  : m,
              ),
            ),
          (realId) => {
            const localId = userMessageId;
            userMessageId = realId;
            userMessagePersisted = true;
            setMessages((prev) => prev.map((m) => (m.id === localId ? { ...m, id: realId } : m)));
          },
        );
        return true;
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return true;
        if (!isRetry && !userMessagePersisted) {
          await new Promise((resolve) => setTimeout(resolve, TRANSIENT_RETRY_DELAY_MS));
          return attempt(true);
        }
        return false;
      }
    };

    const ok = await attempt(false);
    setIsStreaming(false);
    abortRef.current = null;

    if (ok) {
      setMessages((prev) => prev.map((m) => (m.id === "streaming" ? { ...m, id: `assistant-${Date.now()}` } : m)));
    } else {
      setMessages((prev) =>
        prev.filter((m) => m.id !== "streaming").map((m) => (m.id === userMessageId ? { ...m, status: "failed" } : m)),
      );
    }
    loadConversations();
  }

  async function handleSend(overrideText?: string) {
    const content = (overrideText ?? input).trim();
    if (!content || isStreaming || sendingRef.current) return;
    sendingRef.current = true;
    const imagesForThisMessage = pendingImages;
    if (!overrideText) setInput("");
    setPendingImages([]);
    try {
      await sendMessage(content, imagesForThisMessage);
    } finally {
      sendingRef.current = false;
    }
  }

  function handleRetry(message: Message) {
    if (isStreaming || sendingRef.current) return;
    sendingRef.current = true;
    sendMessage(message.content, message.images ?? [], message.id).finally(() => {
      sendingRef.current = false;
    });
  }

  // "Edit and resend": discards the edited message and everything after it (locally, and on
  // the server via the delete-onward endpoint, since the old reply no longer corresponds to
  // what's being asked), then sends the new wording as a fresh message. A message that never
  // made it to the server (a failed send, still carrying a client-generated "local-…" id) has
  // nothing to delete server-side — editing it just replaces it locally before resending.
  async function handleEditMessage(message: Message, newContent: string) {
    const trimmed = newContent.trim();
    if (!trimmed || isStreaming || sendingRef.current) return;
    sendingRef.current = true;
    try {
      const isPersisted = !message.id.startsWith("local-") && message.id !== "streaming";
      if (isPersisted && activeId) {
        try {
          await apiJson(`/api/v1/conversations/${activeId}/messages/${message.id}/onward`, { method: "DELETE" });
        } catch {
          setError("Could not update that message. Please try again.");
          return;
        }
      }
      setMessages((prev) => {
        const index = prev.findIndex((m) => m.id === message.id);
        return index === -1 ? prev : prev.slice(0, index);
      });
      await sendMessage(trimmed, message.images ?? []);
    } finally {
      sendingRef.current = false;
    }
  }

  // Regenerating an assistant reply is the same operation as editing the user turn right
  // before it with unchanged wording: discard that turn onward, resend the same content, get
  // a fresh reply. Reusing handleEditMessage keeps there being exactly one place that knows
  // how to safely discard-and-resend.
  function handleRegenerate(assistantMessage: Message) {
    if (isStreaming || sendingRef.current) return;
    const index = messages.findIndex((m) => m.id === assistantMessage.id);
    if (index === -1) return;
    const precedingUser = [...messages.slice(0, index)].reverse().find((m) => m.role === "user");
    if (!precedingUser) return;
    handleEditMessage(precedingUser, precedingUser.content);
  }

  async function handleFeedback(message: Message, feedback: "up" | "down" | null) {
    if (!activeId || message.id.startsWith("local-") || message.id === "streaming") return;
    const previous = message.feedback;
    setMessages((prev) => prev.map((m) => (m.id === message.id ? { ...m, feedback } : m)));
    try {
      await apiJson(`/api/v1/conversations/${activeId}/messages/${message.id}`, {
        method: "PATCH",
        body: JSON.stringify({ feedback }),
      });
    } catch {
      setMessages((prev) => prev.map((m) => (m.id === message.id ? { ...m, feedback: previous } : m)));
      setError("Could not save feedback.");
    }
  }

  function handleStop() {
    abortRef.current?.abort();
  }

  const displayName = currentUser?.email ? currentUser.email.split("@")[0].replace(/[._-]/g, " ") : "there";

  return (
    <div className="flex h-screen bg-white">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        userEmail={currentUser?.email ?? null}
        onSelect={selectConversation}
        onNew={handleNewConversation}
        onHome={handleHome}
        onDelete={handleDeleteConversation}
        onLogout={handleLogout}
        onLibraryAction={handleLibraryAction}
        onOpenSearch={() => setSearchOpen(true)}
        isAdmin={isAdmin}
      />

      {showDocuments && <DocumentsPanel onClose={() => setShowDocuments(false)} />}
      {showMemory && <MemoriesPanel onClose={() => setShowMemory(false)} />}
      <SearchOverlay
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        conversations={conversations}
        onSelectConversation={selectConversation}
      />
      <VoiceAssistant
        open={voiceOpen}
        onClose={() => setVoiceOpen(false)}
        onSubmit={(text) => handleSend(text)}
        isStreaming={isStreaming}
        latestAssistantMessage={lastAssistantMessage}
      />

      <main className="flex flex-1 flex-col overflow-hidden">
        <MobileTopBar
          conversations={conversations}
          activeId={activeId}
          userEmail={currentUser?.email ?? null}
          onSelect={selectConversation}
          onNew={handleNewConversation}
          onHome={handleHome}
          onDelete={handleDeleteConversation}
          onLogout={handleLogout}
          onLibraryAction={handleLibraryAction}
          onOpenSearch={() => setSearchOpen(true)}
          isAdmin={isAdmin}
        />

        <div className="thin-scroll flex-1 overflow-y-auto">
          {showHome ? (
            <HomeDashboard
              displayName={displayName}
              onPromptSelect={handlePromptSelect}
              onOpenDocuments={() => setShowDocuments(true)}
            />
          ) : (
            <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
              {messages.map((m) => (
                <MessageBubble
                  key={m.id}
                  message={m}
                  onRetry={() => handleRetry(m)}
                  onEdit={(newContent) => handleEditMessage(m, newContent)}
                  onRegenerate={() => handleRegenerate(m)}
                  onFeedback={(feedback) => handleFeedback(m, feedback)}
                />
              ))}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        {error && <p className="mx-auto mb-2 max-w-3xl text-sm text-red-500">{error}</p>}
        {notice && <p className="mx-auto mb-2 max-w-3xl text-sm text-emerald-600">{notice}</p>}

        {showThinkingIndicator && (
          <div className="flex flex-col items-center justify-center gap-1 py-2">
            <LoadingDots className="h-8 w-8" />
            {thinkingSeconds >= 8 && (
              <p className="max-w-sm text-center text-xs text-gray-400">
                {thinkingSeconds < 25
                  ? "Still thinking…"
                  : thinkingSeconds < 60
                    ? "This is taking a bit longer than usual…"
                    : "Still working — long or complex prompts can take a minute or more without a GPU. You can keep waiting, or tap Stop and try a shorter prompt."}
              </p>
            )}
          </div>
        )}

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
                    <AuthedImage imageId={img.id} className="h-16 w-16 rounded-xl object-cover" />
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
            <div className="flex items-end gap-1 rounded-3xl border border-gray-200 bg-gray-50 py-1.5 pl-1.5 pr-2 transition focus-within:border-indigo-400 focus-within:bg-white">
              <input
                ref={imageInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                multiple
                onChange={handleAttachImages}
                className="hidden"
              />
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,text/plain,text/markdown,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                onChange={handleAttachFile}
                className="hidden"
              />
              <div className="relative shrink-0" ref={attachMenuRef}>
                <button
                  onClick={() => setAttachMenuOpen((open) => !open)}
                  disabled={imageUploading}
                  title="Attach"
                  className="group shrink-0 rounded-full p-2.5 text-gray-500 transition hover:bg-gray-200/70 hover:text-gray-900 disabled:opacity-40"
                >
                  <AnimatedIcon icon={Paperclip} className="h-4 w-4" strokeWidth={2} />
                </button>

                {attachMenuOpen && (
                  <div className="absolute bottom-full left-0 mb-2 flex flex-col gap-0.5 rounded-2xl border border-gray-200 bg-white p-1.5 shadow-lg">
                    {ATTACH_OPTIONS.map((opt) => (
                      <button
                        key={opt.key}
                        onClick={() => {
                          if (!opt.enabled) return;
                          setAttachMenuOpen(false);
                          if (opt.key === "image") imageInputRef.current?.click();
                          else if (opt.key === "files") fileInputRef.current?.click();
                        }}
                        disabled={!opt.enabled}
                        title={opt.enabled ? `Attach ${opt.label.toLowerCase()}` : "Coming soon"}
                        className={`flex items-center gap-2.5 whitespace-nowrap rounded-xl px-3 py-2 text-left text-sm font-medium transition ${
                          opt.enabled ? "text-gray-700 hover:bg-gray-100" : "cursor-not-allowed text-gray-300"
                        }`}
                      >
                        <AnimatedIcon icon={opt.icon} className="h-4 w-4" />
                        {opt.label}
                        {!opt.enabled && <span className="ml-auto text-[10px] uppercase tracking-wide text-gray-300">Soon</span>}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  // Enter (with or without Shift) inserts a newline like a normal textarea —
                  // Ctrl/Cmd+Enter sends, so composing a multi-line prompt doesn't fight the
                  // keyboard.
                  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Message MyBuddy... (Ctrl+Enter to send)"
                rows={1}
                className="max-h-60 flex-1 resize-none overflow-y-auto bg-transparent py-2.5 text-sm text-gray-900 outline-none"
              />
              {speechSupported && (
                <>
                  <button
                    onClick={toggleDictation}
                    title={dictationListening ? "Stop dictation" : "Dictate with microphone"}
                    className={`shrink-0 rounded-full p-2.5 transition ${
                      dictationListening ? "bg-red-50 text-red-600" : "text-gray-500 hover:bg-gray-200/70 hover:text-gray-900"
                    }`}
                  >
                    <Mic className="h-4 w-4" strokeWidth={2} />
                  </button>
                  <button
                    onClick={() => setVoiceOpen(true)}
                    title="Talk to MyBuddy (voice assistant)"
                    className="shrink-0 rounded-full p-2.5 text-gray-500 transition hover:bg-gray-200/70 hover:text-gray-900"
                  >
                    <Headphones className="h-4 w-4" strokeWidth={2} />
                  </button>
                </>
              )}
              {isStreaming ? (
                <button
                  onClick={handleStop}
                  title="Stop"
                  className="flex shrink-0 items-center justify-center rounded-full bg-red-600 p-2.5 text-white transition hover:bg-red-500"
                >
                  <Square className="h-4 w-4" fill="currentColor" strokeWidth={0} />
                </button>
              ) : (
                <button
                  onClick={() => handleSend()}
                  disabled={!input.trim()}
                  title="Send"
                  className="group flex shrink-0 items-center justify-center rounded-full bg-indigo-600 p-2.5 text-white transition hover:bg-indigo-500 disabled:opacity-40"
                >
                  <Send className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" strokeWidth={2} />
                </button>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
