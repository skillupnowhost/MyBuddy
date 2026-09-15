import { Wrench, FileText } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import AuthedImage from "@/components/AuthedImage";
import TypingIndicator from "@/components/TypingIndicator";
import type { Message } from "@/lib/types";

function CopyableCode({ children }: { children: string }) {
  return (
    <div className="group relative">
      <pre className="overflow-x-auto rounded-lg bg-gray-900 p-3 text-sm text-gray-100">
        <code>{children}</code>
      </pre>
      <button
        onClick={() => navigator.clipboard.writeText(children)}
        className="absolute right-2 top-2 rounded bg-white/10 px-2 py-1 text-xs text-white/70 opacity-0 transition group-hover:opacity-100 hover:bg-white/20"
      >
        Copy
      </button>
    </div>
  );
}

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const isEmptyStreamingReply =
    !isUser && !message.content && !message.toolCall && !(message.sources && message.sources.length > 0);

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser ? "bg-indigo-600 text-white" : "bg-white text-gray-800 shadow-sm ring-1 ring-gray-200"
        }`}
      >
        {message.images && message.images.length > 0 && (
          <div className="mb-2 flex flex-wrap gap-2">
            {message.images.map((img) => (
              <AuthedImage key={img.id} imageId={img.id} className="h-32 w-32 rounded-lg object-cover" />
            ))}
          </div>
        )}
        {isEmptyStreamingReply ? (
          <TypingIndicator />
        ) : (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ className, children, ...props }) {
                const isBlock = className?.includes("language-");
                if (isBlock) {
                  return <CopyableCode>{String(children).replace(/\n$/, "")}</CopyableCode>;
                }
                return (
                  <code
                    className={`rounded px-1 py-0.5 text-[0.85em] ${isUser ? "bg-black/20" : "bg-gray-100"}`}
                    {...props}
                  >
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
        )}

        {message.toolCall && (
          <div className={`mt-2 border-t pt-2 ${isUser ? "border-white/20" : "border-gray-200"}`}>
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-700">
              <Wrench className="h-3 w-3 animate-icon-pop" strokeWidth={2.5} /> used tool: {message.toolCall}
            </span>
          </div>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className={`mt-2 flex flex-wrap gap-1.5 border-t pt-2 ${isUser ? "border-white/20" : "border-gray-200"}`}>
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
    </div>
  );
}
