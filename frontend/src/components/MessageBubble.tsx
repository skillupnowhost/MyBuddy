"use client";

import { useEffect, useRef, useState } from "react";
import {
  Wrench,
  FileText,
  RefreshCw,
  AlertCircle,
  Pencil,
  Check,
  Download,
  ThumbsUp,
  ThumbsDown,
  RotateCw,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import AuthedImage from "@/components/AuthedImage";
import CopyButton from "@/components/CopyButton";
import MediaLightbox from "@/components/MediaLightbox";
import type { ImageItem, Message } from "@/lib/types";

const ICON_BTN = "flex h-7 w-7 items-center justify-center rounded-full text-gray-400 transition hover:bg-gray-100 hover:text-gray-700";

// Common languages a fenced code block is likely to be tagged with, mapped to a sensible file
// extension for the download button — anything else just falls back to .txt.
const LANGUAGE_EXTENSIONS: Record<string, string> = {
  python: "py",
  javascript: "js",
  jsx: "jsx",
  typescript: "ts",
  tsx: "tsx",
  java: "java",
  c: "c",
  cpp: "cpp",
  "c++": "cpp",
  csharp: "cs",
  "c#": "cs",
  go: "go",
  golang: "go",
  rust: "rs",
  ruby: "rb",
  php: "php",
  html: "html",
  css: "css",
  json: "json",
  sql: "sql",
  bash: "sh",
  sh: "sh",
  shell: "sh",
  yaml: "yml",
  yml: "yml",
  markdown: "md",
  swift: "swift",
  kotlin: "kt",
};

function downloadSnippet(language: string | undefined, content: string) {
  const ext = LANGUAGE_EXTENSIONS[(language ?? "").toLowerCase()] ?? "txt";
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `snippet.${ext}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function CopyableCode({ language, children }: { language?: string; children: string }) {
  // A header row (language name + download + copy), not a floating overlay — an
  // absolutely-positioned button collided with long lines that wrap edge-to-edge, and stayed
  // invisible until hovered. A header row can't overlap content and needs no hover to see.
  return (
    <div className="my-3 overflow-hidden rounded-lg border border-gray-700 bg-gray-900 shadow-md">
      <div className="flex items-center justify-between border-b border-white/10 bg-black/20 py-1 pl-3 pr-1">
        <span className="text-xs font-medium text-white/50">{language || "code"}</span>
        <div className="flex items-center gap-0.5">
          <button
            onClick={() => downloadSnippet(language, children)}
            title="Download"
            aria-label="Download code"
            className="flex h-9 w-9 items-center justify-center rounded-full text-white/70 transition hover:bg-white/10 hover:text-white"
          >
            <Download className="h-4 w-4" strokeWidth={2} />
          </button>
          <CopyButton
            text={children}
            className="flex h-9 w-9 items-center justify-center rounded-full text-white/70 transition hover:bg-white/10 hover:text-white"
          />
        </div>
      </div>
      <SyntaxHighlighter
        language={(language || "text").toLowerCase()}
        style={vscDarkPlus}
        customStyle={{ margin: 0, background: "transparent", padding: "0.75rem", fontSize: "0.875rem" }}
        wrapLongLines
      >
        {children}
      </SyntaxHighlighter>
    </div>
  );
}

export default function MessageBubble({
  message,
  onRetry,
  onEdit,
  onRegenerate,
  onFeedback,
}: {
  message: Message;
  onRetry?: () => void;
  onEdit?: (newContent: string) => void;
  onRegenerate?: () => void;
  onFeedback?: (feedback: "up" | "down" | null) => void;
}) {
  const isUser = message.role === "user";
  // While the assistant's reply is still empty (no text, tool result, sources, or generated
  // image yet), render nothing here — the shared "thinking" indicator lives centered above
  // the composer instead (see chat/page.tsx), not as a bubble in the message flow.
  const isEmptyStreamingReply =
    !isUser &&
    !message.content &&
    !message.toolCall &&
    !(message.sources && message.sources.length > 0) &&
    !(message.images && message.images.length > 0);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState(message.content);
  const editTextareaRef = useRef<HTMLTextAreaElement>(null);
  const [lightboxImage, setLightboxImage] = useState<{ src: string; image: ImageItem } | null>(null);

  // Grows the edit box to fit the whole message (no internal scrollbar, ever) — the message
  // list itself already scrolls, so there's no fixed-height constraint to cap this against
  // the way the bottom composer needs one. Must run unconditionally (before the early return
  // below) since isEmptyStreamingReply can flip for this same mounted instance mid-stream —
  // an early return above a hook would violate the Rules of Hooks.
  useEffect(() => {
    const el = editTextareaRef.current;
    if (!el || !isEditing) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [isEditing, editValue]);

  if (isEmptyStreamingReply) return null;

  const failed = isUser && message.status === "failed";
  const canEdit = isUser && !!onEdit && message.id !== "streaming";
  const isPersisted = !message.id.startsWith("local-") && message.id !== "streaming";

  function startEdit() {
    setEditValue(message.content);
    setIsEditing(true);
  }

  function saveEdit() {
    const trimmed = editValue.trim();
    setIsEditing(false);
    if (trimmed && trimmed !== message.content) onEdit?.(trimmed);
  }

  const markdown = (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ className, children, ...props }) {
          const isBlock = className?.includes("language-");
          if (isBlock) {
            const language = className?.match(/language-(\S+)/)?.[1];
            return <CopyableCode language={language}>{String(children).replace(/\n$/, "")}</CopyableCode>;
          }
          return (
            <code className={`rounded px-1 py-0.5 text-[0.85em] ${isUser ? "bg-black/20" : "bg-gray-100"}`} {...props}>
              {children}
            </code>
          );
        },
        a({ children, ...props }) {
          return (
            <a
              className={isUser ? "text-white underline" : "text-indigo-600 underline"}
              target="_blank"
              rel="noreferrer"
              {...props}
            >
              {children}
            </a>
          );
        },
      }}
    >
      {message.content}
    </ReactMarkdown>
  );

  if (isEditing) {
    return (
      <div className="flex flex-col items-end">
        <div className="w-full max-w-[80%] rounded-2xl bg-indigo-600 p-2">
          <textarea
            ref={editTextareaRef}
            autoFocus
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                saveEdit();
              }
              if (e.key === "Escape") setIsEditing(false);
            }}
            rows={2}
            className="w-full resize-none overflow-hidden rounded-xl bg-indigo-700/50 px-3 py-2 text-sm text-white outline-none"
          />
          <div className="mt-1.5 flex justify-end gap-1.5">
            <button
              onClick={() => setIsEditing(false)}
              className="rounded-full px-2.5 py-1 text-xs font-medium text-white/80 transition hover:bg-white/10"
            >
              Cancel
            </button>
            <button
              onClick={saveEdit}
              disabled={!editValue.trim() || editValue.trim() === message.content}
              title={editValue.trim() === message.content ? "Change the text to resend it" : undefined}
              className="flex items-center gap-1 rounded-full bg-white px-2.5 py-1 text-xs font-medium text-indigo-600 transition hover:bg-white/90 disabled:opacity-40"
            >
              <Check className="h-3 w-3" strokeWidth={2.5} />
              Save &amp; resend
            </button>
          </div>
        </div>
      </div>
    );
  }

  // User turns stay a pill bubble (matches how every reference chat UI sets a sent message
  // apart); assistant turns run as plain text on the page — no card — with a persistent
  // action row underneath, same layout the references use for a reply.
  if (isUser) {
    return (
      <div className="group flex flex-col items-end">
        <div
          className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed text-white ${
            failed ? "bg-indigo-600/50" : "bg-indigo-600"
          }`}
        >
          {message.images && message.images.length > 0 && (
            <div className="mb-2 flex flex-wrap gap-2">
              {message.images.map((img) => (
                <AuthedImage key={img.id} imageId={img.id} className="h-32 w-32 rounded-lg object-cover" downloadable />
              ))}
            </div>
          )}
          {markdown}
        </div>

        <div className="mt-1 flex items-center gap-0.5 opacity-60 transition group-hover:opacity-100">
          <CopyButton text={message.content} className={ICON_BTN} />
          {canEdit && (
            <button onClick={startEdit} title="Edit & resend" aria-label="Edit message" className={ICON_BTN}>
              <Pencil className="h-3.5 w-3.5" strokeWidth={2} />
            </button>
          )}
        </div>

        {failed && (
          <button
            onClick={onRetry}
            className="mt-1 flex items-center gap-1.5 rounded-full bg-red-50 px-3 py-1 text-xs font-medium text-red-600 transition hover:bg-red-100"
          >
            <AlertCircle className="h-3 w-3" strokeWidth={2.5} />
            Not sent &mdash; tap to retry
            <RefreshCw className="h-3 w-3" strokeWidth={2.5} />
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-start">
      <div className="max-w-[80%] text-sm leading-relaxed text-gray-800">
        {markdown}

        {message.images && message.images.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {message.images.map((img) => (
              <AuthedImage
                key={img.id}
                imageId={img.id}
                className="h-40 w-40 rounded-xl object-cover"
                onOpen={(src) => setLightboxImage({ src, image: img })}
              />
            ))}
          </div>
        )}

        {message.toolCall && (
          <div className="mt-2 border-t border-gray-200 pt-2">
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
              <Wrench className="h-3 w-3 animate-icon-pop" strokeWidth={2.5} /> used tool: {message.toolCall}
            </span>
          </div>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5 border-t border-gray-200 pt-2">
            {message.sources.map((source, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600"
                title={source.filename}
              >
                <FileText className="h-3 w-3" strokeWidth={2} /> {source.filename}
                {source.page_number ? ` p.${source.page_number}` : ""}
                {source.lines ? ` L${source.lines}` : ""}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="mt-1.5 flex items-center gap-0.5">
        <button
          onClick={() => onFeedback?.(message.feedback === "up" ? null : "up")}
          disabled={!isPersisted}
          title="Good response"
          aria-label="Good response"
          aria-pressed={message.feedback === "up"}
          className={`${ICON_BTN} disabled:opacity-30 ${message.feedback === "up" ? "text-indigo-600" : ""}`}
        >
          <ThumbsUp className="h-3.5 w-3.5" strokeWidth={2} fill={message.feedback === "up" ? "currentColor" : "none"} />
        </button>
        <button
          onClick={() => onFeedback?.(message.feedback === "down" ? null : "down")}
          disabled={!isPersisted}
          title="Bad response"
          aria-label="Bad response"
          aria-pressed={message.feedback === "down"}
          className={`${ICON_BTN} disabled:opacity-30 ${message.feedback === "down" ? "text-red-500" : ""}`}
        >
          <ThumbsDown className="h-3.5 w-3.5" strokeWidth={2} fill={message.feedback === "down" ? "currentColor" : "none"} />
        </button>
        {onRegenerate && (
          <button onClick={onRegenerate} title="Regenerate response" aria-label="Regenerate response" className={ICON_BTN}>
            <RotateCw className="h-3.5 w-3.5" strokeWidth={2} />
          </button>
        )}
        <CopyButton text={message.content} className={ICON_BTN} />
      </div>

      {lightboxImage && (
        <MediaLightbox
          open
          onClose={() => setLightboxImage(null)}
          mediaType="image"
          src={lightboxImage.src}
          prompt={lightboxImage.image.prompt}
          onDownload={() => {
            const link = document.createElement("a");
            link.href = lightboxImage.src;
            link.download = `${lightboxImage.image.id}.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
          }}
        />
      )}
    </div>
  );
}
