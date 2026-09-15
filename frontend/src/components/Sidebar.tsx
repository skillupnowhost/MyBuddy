import Link from "next/link";
import { useState } from "react";
import {
  Sparkles,
  Plus,
  Home,
  Compass,
  Code2,
  Image as ImageIcon,
  PenTool,
  Film,
  Clapperboard,
  Target,
  Wand2,
  FileText,
  Brain,
  FolderOpen,
  SlidersHorizontal,
  Settings,
  Search,
  X,
  LogOut,
  type LucideIcon,
} from "lucide-react";
import type { Conversation } from "@/lib/types";
import AnimatedIcon from "@/components/AnimatedIcon";

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  userEmail: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onHome: () => void;
  onDelete: (id: string) => void;
  onLogout: () => void;
  onOpenDocuments: () => void;
  onOpenMemory: () => void;
  isAdmin: boolean;
}

const TOOL_LINKS: { href: string; label: string; icon: LucideIcon }[] = [
  { href: "/code", label: "Code", icon: Code2 },
  { href: "/image", label: "Image", icon: ImageIcon },
  { href: "/vector", label: "Vector", icon: PenTool },
  { href: "/animation", label: "Animator", icon: Film },
  { href: "/motion", label: "Motion", icon: Clapperboard },
  { href: "/creative", label: "Creative Director", icon: Target },
  { href: "/image-edit", label: "Image Edit", icon: Wand2 },
];

function NavButton({
  onClick,
  icon: Icon,
  label,
  active,
}: {
  onClick: () => void;
  icon: LucideIcon;
  label: string;
  active?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      className={`group flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition ${
        active ? "bg-white/10 text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
      }`}
    >
      <AnimatedIcon icon={Icon} />
      {label}
    </button>
  );
}

function NavLink({ href, icon: Icon, label }: { href: string; icon: LucideIcon; label: string }) {
  return (
    <Link
      href={href}
      className="group flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-white/70 transition hover:bg-white/5 hover:text-white"
    >
      <AnimatedIcon icon={Icon} />
      {label}
    </Link>
  );
}

export default function Sidebar({
  conversations,
  activeId,
  userEmail,
  onSelect,
  onNew,
  onHome,
  onDelete,
  onLogout,
  onOpenDocuments,
  onOpenMemory,
  isAdmin,
}: SidebarProps) {
  const initial = (userEmail ?? "?").trim().charAt(0).toUpperCase();
  const [historyFilter, setHistoryFilter] = useState("");
  const filteredConversations = historyFilter.trim()
    ? conversations.filter((c) => c.title.toLowerCase().includes(historyFilter.trim().toLowerCase()))
    : conversations;

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col bg-[#12142a]">
      <div className="flex items-center gap-2 px-5 pb-4 pt-5">
        <span className="animate-brand-glow flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-400 to-purple-500">
          <AnimatedIcon icon={Sparkles} className="h-4 w-4 text-white" strokeWidth={2.5} />
        </span>
        <div>
          <h1 className="text-base font-semibold leading-tight text-white">MyBuddy</h1>
          <p className="text-[11px] leading-tight text-white/40">Your AI. Always with you.</p>
        </div>
      </div>

      <div className="px-3">
        <button
          onClick={onNew}
          className="group mb-3 flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-indigo-500 to-violet-500 px-3 py-2.5 text-sm font-medium text-white shadow-sm transition hover:opacity-90"
        >
          <AnimatedIcon icon={Plus} className="h-4 w-4" strokeWidth={2.5} />
          New Chat
        </button>
      </div>

      <nav className="thin-scroll flex-1 space-y-4 overflow-y-auto px-3 pb-3">
        <div className="space-y-1">
          <NavButton onClick={onHome} icon={Home} label="Home" active={!activeId} />
          <NavButton onClick={onHome} icon={Compass} label="Explore Agents" />
        </div>

        <div>
          <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-white/30">Tools</p>
          <div className="space-y-1">
            {TOOL_LINKS.map((tool) => (
              <NavLink key={tool.href} {...tool} />
            ))}
          </div>
        </div>

        <div>
          <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-white/30">Library</p>
          <div className="space-y-1">
            <NavButton onClick={onOpenDocuments} icon={FileText} label="Knowledge base" />
            <NavButton onClick={onOpenMemory} icon={Brain} label="Memory" />
            <NavLink href="/code" icon={FolderOpen} label="Projects" />
          </div>
        </div>

        {isAdmin && (
          <div className="space-y-1">
            <NavLink href="/finetune" icon={SlidersHorizontal} label="Fine-tuning" />
            <NavLink href="/admin" icon={Settings} label="Admin" />
          </div>
        )}

        <div>
          <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-white/30">History</p>
          {conversations.length > 0 && (
            <div className="relative mb-1 px-1">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-white/30" />
              <input
                value={historyFilter}
                onChange={(e) => setHistoryFilter(e.target.value)}
                placeholder="Filter conversations..."
                className="w-full rounded-lg border border-white/10 bg-white/5 py-1.5 pl-8 pr-2 text-xs text-white/80 outline-none placeholder:text-white/30 focus:border-indigo-400"
              />
            </div>
          )}
          <div className="space-y-1">
            {conversations.length === 0 && (
              <p className="px-3 py-1 text-xs text-white/30">No conversations yet.</p>
            )}
            {conversations.length > 0 && filteredConversations.length === 0 && (
              <p className="px-3 py-1 text-xs text-white/30">No matches.</p>
            )}
            {filteredConversations.map((c) => (
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
                  className="ml-2 shrink-0 opacity-0 transition group-hover:opacity-100 hover:text-red-400"
                  aria-label="Delete conversation"
                >
                  <X className="h-3.5 w-3.5" strokeWidth={2.5} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </nav>

      <div className="flex items-center gap-2.5 border-t border-white/10 p-3">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-white/10 text-sm font-medium text-white">
          {initial}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm text-white/90">{userEmail ?? "Signed out"}</p>
        </div>
        <button
          onClick={onLogout}
          title="Log out"
          className="rounded-md p-1.5 text-white/50 transition hover:bg-white/10 hover:text-white"
        >
          <LogOut className="h-4 w-4" strokeWidth={2} />
        </button>
      </div>
    </aside>
  );
}
