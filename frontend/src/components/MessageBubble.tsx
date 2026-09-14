import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "@/lib/types";

function CopyableCode({ children }: { children: string }) {
  return (
    <div className="group relative">
      <pre className="overflow-x-auto rounded-lg bg-black/40 p-3 text-sm">
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

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isUser ? "bg-blue-600 text-white" : "bg-[#1c202b] text-white/90"
        }`}
      >
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            code({ className, children, ...props }) {
              const isBlock = className?.includes("language-");
              if (isBlock) {
                return <CopyableCode>{String(children).replace(/\n$/, "")}</CopyableCode>;
              }
              return (
                <code className="rounded bg-black/30 px-1 py-0.5 text-[0.85em]" {...props}>
                  {children}
                </code>
              );
            },
            a({ children, ...props }) {
              return (
                <a className="text-blue-400 underline" target="_blank" rel="noreferrer" {...props}>
                  {children}
                </a>
              );
            },
          }}
        >
          {message.content}
        </ReactMarkdown>

        {message.toolCall && (
          <div className="mt-2 border-t border-white/10 pt-2">
            <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-xs text-amber-300">
              🔧 used tool: {message.toolCall}
            </span>
          </div>
        )}

        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5 border-t border-white/10 pt-2">
            {message.sources.map((source, i) => (
              <span
                key={i}
                className="rounded-full bg-white/10 px-2 py-0.5 text-xs text-white/60"
                title={source.filename}
              >
                📄 {source.filename}
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
