"use client";

import { useEffect, useRef, useState } from "react";
import CodeMirror from "@uiw/react-codemirror";
import { javascript } from "@codemirror/lang-javascript";
import { python } from "@codemirror/lang-python";
import Link from "next/link";
import { useRouter } from "next/navigation";
import CodeFileTree from "@/components/CodeFileTree";
import MessageBubble from "@/components/MessageBubble";
import { apiJson } from "@/lib/api";
import { getCurrentUser } from "@/lib/admin";
import { isLoggedIn } from "@/lib/auth";
import {
  deleteCodeProject,
  getCodeFileContent,
  getCodeProjectTree,
  listCodeProjects,
  pollExecution,
  submitExecution,
  uploadCodeProject,
} from "@/lib/code";
import { streamChatMessage } from "@/lib/stream";
import type {
  CodeExecutionItem,
  CodeFileItem,
  CodeProjectItem,
  Conversation,
  Message,
  ModelsResponse,
} from "@/lib/types";

const CODE_SYSTEM_PROMPT =
  "You are MyBuddy Code, a coding assistant with access to the currently open project via " +
  "retrieved snippets. Prefer citing file paths and line numbers. Give complete, runnable code.";

const IN_PROGRESS_STATUSES = new Set(["UPLOADING", "EXTRACTING", "EMBEDDING"]);

function languageExtension(language: string | null) {
  if (language === "javascript" || language === "typescript") return [javascript({ jsx: true, typescript: true })];
  return [python()];
}

export default function CodePage() {
  const router = useRouter();
  const [projects, setProjects] = useState<CodeProjectItem[]>([]);
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null);
  const [tree, setTree] = useState<CodeFileItem[]>([]);
  const [selectedFile, setSelectedFile] = useState<CodeFileItem | null>(null);
  const [editorContent, setEditorContent] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [codeModel, setCodeModel] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [execution, setExecution] = useState<CodeExecutionItem | null>(null);
  const [running, setRunning] = useState(false);
  const stopPollingRef = useRef<(() => void) | null>(null);

  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeProject = projects.find((p) => p.id === activeProjectId) ?? null;

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    refreshProjects();
    getCurrentUser()
      .then((user) => setIsAdmin(user.role === "ADMIN"))
      .catch(() => {});
    apiJson<ModelsResponse>("/api/v1/models")
      .then((res) => setCodeModel(res.code_model))
      .catch(() => {});
  }, [router]);

  useEffect(() => {
    const interval = setInterval(() => {
      setProjects((prev) => {
        if (prev.some((p) => IN_PROGRESS_STATUSES.has(p.status))) refreshProjects();
        return prev;
      });
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    return () => stopPollingRef.current?.();
  }, []);

  async function refreshProjects() {
    try {
      setProjects(await listCodeProjects());
    } catch {
      setError("Could not load code projects.");
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const project = await uploadCodeProject(file);
      setProjects((prev) => [project, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleSelectProject(id: string) {
    setActiveProjectId(id);
    setSelectedFile(null);
    setEditorContent("");
    setConversationId(null);
    setMessages([]);
    try {
      setTree(await getCodeProjectTree(id));
    } catch {
      setError("Could not load the project's file tree.");
    }
  }

  async function handleDeleteProject(id: string) {
    await deleteCodeProject(id);
    setProjects((prev) => prev.filter((p) => p.id !== id));
    if (activeProjectId === id) {
      setActiveProjectId(null);
      setTree([]);
      setSelectedFile(null);
    }
  }

  async function handleSelectFile(file: CodeFileItem) {
    if (!activeProjectId) return;
    setSelectedFile(file);
    try {
      const content = await getCodeFileContent(activeProjectId, file.id);
      setEditorContent(content.content);
    } catch {
      setError("Could not load file content.");
    }
  }

  async function handleRun() {
    if (!isAdmin || running) return;
    setError(null);
    setRunning(true);
    setExecution(null);
    try {
      const language = selectedFile?.language === "javascript" ? "javascript" : "python";
      const job = await submitExecution(language, editorContent);
      setExecution(job);
      stopPollingRef.current?.();
      stopPollingRef.current = pollExecution(job.id, (updated) => {
        setExecution(updated);
        if (updated.status !== "PENDING" && updated.status !== "RUNNING") setRunning(false);
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit code for execution.");
      setRunning(false);
    }
  }

  async function ensureConversation(): Promise<string> {
    if (conversationId) return conversationId;
    const conversation = await apiJson<Conversation>("/api/v1/conversations", {
      method: "POST",
      body: JSON.stringify({
        title: activeProject ? `Code: ${activeProject.name}` : "Code chat",
        model: codeModel,
        system_prompt: CODE_SYSTEM_PROMPT,
        code_project_id: activeProjectId,
      }),
    });
    setConversationId(conversation.id);
    return conversation.id;
  }

  async function handleSendChat() {
    const content = chatInput.trim();
    if (!content || isStreaming) return;
    setChatInput("");
    setError(null);

    let id: string;
    try {
      id = await ensureConversation();
    } catch {
      setError("Could not start a code chat conversation.");
      return;
    }

    setMessages((prev) => [
      ...prev,
      { id: `local-${Date.now()}`, role: "user", content, created_at: new Date().toISOString() },
      { id: "streaming", role: "assistant", content: "", created_at: new Date().toISOString() },
    ]);
    setIsStreaming(true);

    try {
      let assembled = "";
      await streamChatMessage(
        id,
        content,
        (delta) => {
          assembled += delta;
          setMessages((prev) => prev.map((m) => (m.id === "streaming" ? { ...m, content: assembled } : m)));
        },
        undefined,
        (sources) => setMessages((prev) => prev.map((m) => (m.id === "streaming" ? { ...m, sources } : m))),
      );
    } catch {
      setError("The message could not be sent. Is the backend running?");
    } finally {
      setIsStreaming(false);
      setMessages((prev) => prev.map((m) => (m.id === "streaming" ? { ...m, id: `assistant-${Date.now()}` } : m)));
    }
  }

  return (
    <div className="flex h-screen flex-col bg-[#f4f5f9] text-gray-900">
      <div className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3">
        <h1 className="text-lg font-semibold">MyBuddy Code</h1>
        <Link href="/chat" className="text-sm text-indigo-600 hover:underline">
          &larr; Back to chat
        </Link>
      </div>

      {error && <p className="border-b border-gray-200 bg-red-50 px-4 py-2 text-sm text-red-500">{error}</p>}

      <div className="flex flex-1 overflow-hidden">
        {/* Left: projects + file tree */}
        <aside className="flex w-64 shrink-0 flex-col border-r border-gray-200 bg-white">
          <div className="p-3">
            <input ref={fileInputRef} type="file" accept=".zip" onChange={handleUpload} className="hidden" />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="w-full rounded-lg border border-dashed border-gray-300 py-2 text-xs text-gray-500 hover:border-indigo-400 hover:text-gray-900 disabled:opacity-50"
            >
              {uploading ? "Uploading..." : "+ Upload project (.zip)"}
            </button>
          </div>
          <div className="flex-1 overflow-y-auto px-2">
            {projects.map((p) => (
              <div key={p.id} className="mb-1">
                <div
                  className={`group flex items-center justify-between rounded-lg px-2 py-2 text-sm ${
                    p.id === activeProjectId ? "bg-gray-100 text-gray-900" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                  }`}
                >
                  <button onClick={() => handleSelectProject(p.id)} className="flex-1 truncate text-left">
                    {p.name}
                    <span className="ml-1 text-xs text-gray-400">
                      {p.status !== "READY" ? ` (${p.status.toLowerCase()})` : ""}
                    </span>
                  </button>
                  <button
                    onClick={() => handleDeleteProject(p.id)}
                    className="ml-1 opacity-0 transition group-hover:opacity-100 hover:text-red-500"
                    aria-label="Delete project"
                  >
                    &times;
                  </button>
                </div>
                {p.id === activeProjectId && p.status === "READY" && (
                  <CodeFileTree files={tree} selectedId={selectedFile?.id ?? null} onSelect={handleSelectFile} />
                )}
                {p.id === activeProjectId && p.error_message && (
                  <p className="px-3 py-1 text-xs text-red-500">{p.error_message}</p>
                )}
              </div>
            ))}
            {projects.length === 0 && <p className="py-6 text-center text-xs text-gray-400">No code projects yet.</p>}
          </div>
        </aside>

        {/* Center: editor + run + output */}
        <main className="flex flex-1 flex-col overflow-hidden border-r border-gray-200">
          <div className="flex items-center justify-between border-b border-gray-200 bg-white px-3 py-2">
            <span className="truncate text-xs text-gray-500">
              {selectedFile ? selectedFile.relative_path : "No file selected — running executes whatever is typed here"}
            </span>
            {isAdmin ? (
              <button
                onClick={handleRun}
                disabled={running || !editorContent}
                className="rounded-lg bg-emerald-600 px-3 py-1 text-xs font-medium text-white hover:bg-emerald-500 disabled:opacity-40"
              >
                {running ? "Running..." : "▶ Run"}
              </button>
            ) : (
              <span className="text-xs text-gray-400" title="Code execution is restricted to admin accounts">
                Run (admin only)
              </span>
            )}
          </div>
          {/* CodeMirror keeps its dark editor theme intentionally — a dark code surface inside a light app
              shell is the standard VS Code / GitHub pattern and preserves syntax-highlighting contrast. */}
          <div className="flex-1 overflow-auto">
            <CodeMirror
              value={editorContent}
              onChange={setEditorContent}
              theme="dark"
              height="100%"
              extensions={languageExtension(selectedFile?.language ?? "python")}
            />
          </div>
          {execution && (
            <div className="max-h-48 overflow-y-auto border-t border-gray-200 bg-black/90 p-3 text-xs">
              <p className="mb-1 text-white/50">
                status: <span className="text-white/80">{execution.status}</span>
                {execution.duration_ms !== null ? ` · ${execution.duration_ms}ms` : ""}
                {execution.exit_code !== null ? ` · exit ${execution.exit_code}` : ""}
              </p>
              {execution.stdout && (
                <pre className="whitespace-pre-wrap text-emerald-300">
                  {execution.stdout}
                  {execution.stdout_truncated ? "\n[truncated]" : ""}
                </pre>
              )}
              {execution.stderr && (
                <pre className="whitespace-pre-wrap text-red-300">
                  {execution.stderr}
                  {execution.stderr_truncated ? "\n[truncated]" : ""}
                </pre>
              )}
              {execution.error_message && <p className="text-red-400">{execution.error_message}</p>}
            </div>
          )}
        </main>

        {/* Right: code chat */}
        <aside className="flex w-96 shrink-0 flex-col bg-white">
          <div className="border-b border-gray-200 px-3 py-2 text-xs text-gray-500">
            {activeProject ? `Chatting about: ${activeProject.name}` : "Open a project for code-aware chat"}
          </div>
          <div className="flex-1 overflow-y-auto p-3">
            <div className="flex flex-col gap-3">
              {messages.map((m) => (
                <MessageBubble key={m.id} message={m} />
              ))}
              <div ref={bottomRef} />
            </div>
          </div>
          <div className="border-t border-gray-200 p-3">
            <div className="flex items-end gap-2">
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSendChat();
                  }
                }}
                placeholder="Ask about this project..."
                rows={2}
                className="max-h-32 flex-1 resize-none rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-400 focus:bg-white"
              />
              <button
                onClick={handleSendChat}
                disabled={!chatInput.trim() || isStreaming}
                className="rounded-xl bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
              >
                Send
              </button>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
