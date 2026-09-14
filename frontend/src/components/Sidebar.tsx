import Link from "next/link";
import type { Conversation } from "@/lib/types";

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  onLogout: () => void;
  onOpenDocuments: () => void;
  onOpenMemory: () => void;
  isAdmin: boolean;
}

export default function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  onLogout,
  onOpenDocuments,
  onOpenMemory,
  isAdmin,
}: SidebarProps) {
  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-white/10 bg-[#12141c]">
      <div className="p-4">
        <h1 className="text-lg font-semibold text-white">MyBuddy</h1>
      </div>

      <div className="space-y-2 px-3">
        <button
          onClick={onNew}
          className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-left text-sm text-white/90 transition hover:bg-white/10"
        >
          + New chat
        </button>
        <button
          onClick={onOpenDocuments}
          className="w-full rounded-lg border border-white/10 px-3 py-2 text-left text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
        >
          📄 Knowledge base
        </button>
        <button
          onClick={onOpenMemory}
          className="w-full rounded-lg border border-white/10 px-3 py-2 text-left text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
        >
          🧠 Memory
        </button>
        <Link
          href="/code"
          className="block w-full rounded-lg border border-white/10 px-3 py-2 text-left text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
        >
          💻 Code
        </Link>
        <Link
          href="/image"
          className="block w-full rounded-lg border border-white/10 px-3 py-2 text-left text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
        >
          🎨 Image
        </Link>
        <Link
          href="/vector"
          className="block w-full rounded-lg border border-white/10 px-3 py-2 text-left text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
        >
          ✒️ Vector
        </Link>
        <Link
          href="/animation"
          className="block w-full rounded-lg border border-white/10 px-3 py-2 text-left text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
        >
          🎞️ Animator
        </Link>
        <Link
          href="/motion"
          className="block w-full rounded-lg border border-white/10 px-3 py-2 text-left text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
        >
          🎬 Motion
        </Link>
        <Link
          href="/creative"
          className="block w-full rounded-lg border border-white/10 px-3 py-2 text-left text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
        >
          🎯 Creative Director
        </Link>
        <Link
          href="/image-edit"
          className="block w-full rounded-lg border border-white/10 px-3 py-2 text-left text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
        >
          🩹 Image Edit
        </Link>
        <Link
          href="/finetune"
          className="block w-full rounded-lg border border-white/10 px-3 py-2 text-left text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
        >
          🛠️ Fine-tuning
        </Link>
        {isAdmin && (
          <Link
            href="/admin"
            className="block w-full rounded-lg border border-white/10 px-3 py-2 text-left text-sm text-white/70 transition hover:bg-white/10 hover:text-white"
          >
            ⚙️ Admin
          </Link>
        )}
      </div>

      <div className="mt-3 flex-1 space-y-1 overflow-y-auto px-3">
        {conversations.map((c) => (
          <div
            key={c.id}
            className={`group flex items-center justify-between rounded-lg px-3 py-2 text-sm transition ${
              c.id === activeId ? "bg-white/10 text-white" : "text-white/60 hover:bg-white/5 hover:text-white"
            }`}
          >
            <button onClick={() => onSelect(c.id)} className="flex-1 truncate text-left">
              {c.title}
            </button>
            <button
              onClick={() => onDelete(c.id)}
              className="ml-2 opacity-0 transition group-hover:opacity-100 hover:text-red-400"
              aria-label="Delete conversation"
            >
              &times;
            </button>
          </div>
        ))}
      </div>

      <div className="border-t border-white/10 p-3">
        <button onClick={onLogout} className="w-full rounded-lg px-3 py-2 text-left text-sm text-white/50 hover:bg-white/5 hover:text-white">
          Log out
        </button>
      </div>
    </aside>
  );
}
