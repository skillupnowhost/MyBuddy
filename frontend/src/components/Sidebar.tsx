"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  Plus,
  Home,
  Search,
  X,
  LogOut,
  Settings,
  SlidersHorizontal,
  CreditCard,
  Clock,
  BookOpen,
  FolderOpen,
  Wrench,
  ChevronDown,
  PanelLeftClose,
  PanelLeftOpen,
  type LucideIcon,
} from "lucide-react";
import type { Conversation } from "@/lib/types";
import AnimatedIcon from "@/components/AnimatedIcon";
import { TOOL_LINKS, LIBRARY_ACTIONS, PROJECT_LINKS, type LibraryActionKey } from "@/lib/navigation";
import { firstNameFromEmail } from "@/lib/displayName";

interface SidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  userEmail: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onHome: () => void;
  onDelete: (id: string) => void;
  onLogout: () => void;
  onLibraryAction: (key: LibraryActionKey) => void;
  onOpenSearch: () => void;
  isAdmin: boolean;
}

const COLLAPSE_STORAGE_KEY = "mybuddy:sidebar-collapsed";

type SectionKey = "library" | "projects" | "tools" | "admin" | "history";

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
      className={`group flex w-full items-center gap-2.5 rounded-full px-3 py-2 text-left text-sm transition ${
        active ? "bg-indigo-50 text-indigo-700" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
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
      className="group flex w-full items-center gap-2.5 rounded-full px-3 py-2 text-left text-sm text-gray-600 transition hover:bg-gray-100 hover:text-gray-900"
    >
      <AnimatedIcon icon={Icon} />
      {label}
    </Link>
  );
}

/** Single icon button for the collapsed (icon-only) rail. Shows a dark tooltip with the label
 * on hover/focus, since there's no room left for text. The tooltip is portaled to <body> and
 * positioned from the trigger's bounding rect so it isn't clipped by the nav's scroll container
 * (which forces overflow-x: auto as soon as overflow-y is anything but visible). */
function RailIcon({
  icon: Icon,
  label,
  onClick,
  href,
  active,
}: {
  icon: LucideIcon;
  label: string;
  onClick?: () => void;
  href?: string;
  active?: boolean;
}) {
  const [tooltipPos, setTooltipPos] = useState<{ top: number; left: number } | null>(null);
  const triggerRef = useRef<HTMLSpanElement>(null);

  function showTooltip() {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (rect) setTooltipPos({ top: rect.top + rect.height / 2, left: rect.right + 8 });
  }
  function hideTooltip() {
    setTooltipPos(null);
  }

  const inner = (
    <span
      ref={triggerRef}
      onMouseEnter={showTooltip}
      onMouseLeave={hideTooltip}
      onFocus={showTooltip}
      onBlur={hideTooltip}
      className={`flex h-10 w-10 items-center justify-center rounded-full transition ${
        active ? "bg-indigo-50 text-indigo-700" : "text-gray-500 hover:bg-gray-100 hover:text-gray-900"
      }`}
    >
      <AnimatedIcon icon={Icon} />
    </span>
  );

  const tooltip =
    tooltipPos && typeof document !== "undefined"
      ? createPortal(
          <span
            className="pointer-events-none fixed z-[100] -translate-y-1/2 whitespace-nowrap rounded-md bg-gray-900 px-2 py-1 text-xs text-white shadow-lg"
            style={{ top: tooltipPos.top, left: tooltipPos.left }}
          >
            {label}
          </span>,
          document.body
        )
      : null;

  if (href) {
    return (
      <Link href={href} onClick={onClick} aria-label={label} className="flex justify-center">
        {inner}
        {tooltip}
      </Link>
    );
  }
  return (
    <button onClick={onClick} aria-label={label} className="flex justify-center">
      {inner}
      {tooltip}
    </button>
  );
}

/** A section with an uppercase header that toggles its content open/closed via the trailing
 * chevron — the "Files" accordion pattern. In the collapsed rail there's no room for headers, so
 * it just stacks the icon-only children. */
function Section({
  title,
  icon: Icon,
  open,
  onToggle,
  collapsed,
  children,
}: {
  title: string;
  icon: LucideIcon;
  open: boolean;
  onToggle: () => void;
  collapsed: boolean;
  children: React.ReactNode;
}) {
  if (collapsed) {
    return <div className="space-y-1">{children}</div>;
  }
  return (
    <div>
      <button
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400 transition hover:text-gray-600"
      >
        <span className="flex items-center gap-1.5">
          <Icon className="h-3.5 w-3.5" strokeWidth={2.5} />
          {title}
        </span>
        <ChevronDown
          className={`h-3.5 w-3.5 shrink-0 transition-transform duration-200 ${open ? "" : "-rotate-90"}`}
          strokeWidth={2.5}
        />
      </button>
      <div
        className={`grid transition-all duration-200 ease-in-out ${
          open ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"
        }`}
      >
        <div className="min-h-0 space-y-1 overflow-hidden pt-1">{children}</div>
      </div>
    </div>
  );
}

function AccountMenu({
  userEmail,
  isAdmin,
  collapsed,
  onLogout,
}: {
  userEmail: string | null;
  isAdmin: boolean;
  collapsed: boolean;
  onLogout: () => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const firstName = firstNameFromEmail(userEmail);
  const initial = userEmail ? firstName.charAt(0).toUpperCase() : "?";

  useEffect(() => {
    if (!open) return;
    function handlePointer(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative border-t border-gray-200 p-3">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="Account menu"
        className={`flex w-full items-center gap-2.5 rounded-full py-1 text-left transition hover:bg-gray-100 ${
          collapsed ? "justify-center" : "px-1"
        }`}
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-sm font-medium text-white">
          {initial}
        </span>
        {!collapsed && (
          <>
            <span className="min-w-0 flex-1 truncate text-sm text-gray-900">{firstName}</span>
            <ChevronDown
              className={`h-3.5 w-3.5 shrink-0 text-gray-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
              strokeWidth={2.5}
            />
          </>
        )}
      </button>

      {open && (
        <div
          className={`absolute bottom-full z-50 mb-2 w-64 overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl ${
            collapsed ? "left-3" : "left-3 right-3 w-auto"
          }`}
        >
          <div className="flex items-center gap-3 border-b border-gray-100 p-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-sm font-medium text-white">
              {initial}
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-gray-900">{firstName}</p>
              {userEmail && <p className="truncate text-xs text-gray-400">{userEmail}</p>}
            </div>
          </div>
          <div className="p-1.5">
            {isAdmin && (
              <Link
                href="/admin"
                onClick={() => setOpen(false)}
                className="flex items-center gap-3 rounded-xl px-3 py-2 text-sm text-gray-700 transition hover:bg-gray-100"
              >
                <Settings className="h-4 w-4 text-gray-500" strokeWidth={2} />
                Admin settings
              </Link>
            )}
            <button className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-gray-700 transition hover:bg-gray-100">
              <CreditCard className="h-4 w-4 text-gray-500" strokeWidth={2} />
              Subscription
            </button>
            <button
              onClick={() => {
                setOpen(false);
                onLogout();
              }}
              className="flex w-full items-center gap-3 rounded-xl px-3 py-2 text-left text-sm text-red-600 transition hover:bg-red-50"
            >
              <LogOut className="h-4 w-4" strokeWidth={2} />
              Log out
            </button>
          </div>
        </div>
      )}
    </div>
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
  onLibraryAction,
  onOpenSearch,
  isAdmin,
}: SidebarProps) {
  const [historyFilter, setHistoryFilter] = useState("");
  const [collapsed, setCollapsed] = useState(false);
  // Collapsed by default so the rail reads as a short list of categories rather than every
  // item at once — History is the exception, since jumping back into a past conversation is
  // the single most common thing this panel is opened for.
  const [openSections, setOpenSections] = useState<Record<SectionKey, boolean>>({
    library: false,
    projects: false,
    tools: false,
    admin: false,
    history: true,
  });

  useEffect(() => {
    if (window.localStorage.getItem(COLLAPSE_STORAGE_KEY) === "1") setCollapsed(true);
  }, []);

  useEffect(() => {
    window.localStorage.setItem(COLLAPSE_STORAGE_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  function toggleSection(key: SectionKey) {
    setOpenSections((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function expandHistory() {
    setCollapsed(false);
    setOpenSections((prev) => ({ ...prev, history: true }));
  }

  const filteredConversations = historyFilter.trim()
    ? conversations.filter((c) => c.title.toLowerCase().includes(historyFilter.trim().toLowerCase()))
    : conversations;

  return (
    <aside
      className={`hidden h-full shrink-0 flex-col border-r border-gray-200 bg-white transition-[width] duration-200 lg:flex ${
        collapsed ? "w-[76px]" : "w-72"
      }`}
    >
      {collapsed ? (
        <div className="flex flex-col items-center gap-2 px-3 pb-4 pt-5">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 text-sm font-semibold text-white">
            M
          </div>
          <button
            onClick={onOpenSearch}
            title="Search"
            aria-label="Search"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100 hover:text-gray-900"
          >
            <Search className="h-4 w-4" strokeWidth={2} />
          </button>
          <button
            onClick={() => setCollapsed(false)}
            title="Expand sidebar"
            aria-label="Expand sidebar"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100 hover:text-gray-900"
          >
            <PanelLeftOpen className="h-4 w-4" strokeWidth={2} />
          </button>
        </div>
      ) : (
        <div className="flex items-center gap-1 px-5 pb-4 pt-5">
          <div className="min-w-0 flex-1">
            <h1 className="text-base font-semibold leading-tight text-gray-900">MyBuddy</h1>
            <p className="text-[11px] leading-tight text-gray-400">Your AI. Always with you.</p>
          </div>
          <button
            onClick={onOpenSearch}
            title="Search"
            aria-label="Search"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100 hover:text-gray-900"
          >
            <Search className="h-4 w-4" strokeWidth={2} />
          </button>
          <button
            onClick={() => setCollapsed(true)}
            title="Collapse sidebar"
            aria-label="Collapse sidebar"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100 hover:text-gray-900"
          >
            <PanelLeftClose className="h-4 w-4" strokeWidth={2} />
          </button>
        </div>
      )}

      <div className="px-3">
        {collapsed ? (
          <div className="mb-3 flex justify-center">
            <button
              onClick={onNew}
              title="New Chat"
              aria-label="New Chat"
              className="flex h-10 w-10 items-center justify-center rounded-full bg-indigo-600 text-white shadow-sm transition hover:bg-indigo-500"
            >
              <AnimatedIcon icon={Plus} className="h-4 w-4" strokeWidth={2.5} />
            </button>
          </div>
        ) : (
          <button
            onClick={onNew}
            className="group mb-3 flex w-full items-center justify-center gap-2 rounded-full bg-indigo-600 px-3 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-500"
          >
            <AnimatedIcon icon={Plus} className="h-4 w-4" strokeWidth={2.5} />
            New Chat
          </button>
        )}
      </div>

      <nav className="thin-scroll flex-1 space-y-4 overflow-y-auto px-3 pb-3">
        <div className={collapsed ? "flex justify-center" : "space-y-1"}>
          {collapsed ? (
            <RailIcon icon={Home} label="Home" onClick={onHome} active={!activeId} />
          ) : (
            <NavButton onClick={onHome} icon={Home} label="Home" active={!activeId} />
          )}
        </div>

        <Section
          title="Library"
          icon={BookOpen}
          open={openSections.library}
          onToggle={() => toggleSection("library")}
          collapsed={collapsed}
        >
          {LIBRARY_ACTIONS.map((action) =>
            collapsed ? (
              <RailIcon key={action.key} icon={action.icon} label={action.label} onClick={() => onLibraryAction(action.key)} />
            ) : (
              <NavButton
                key={action.key}
                onClick={() => onLibraryAction(action.key)}
                icon={action.icon}
                label={action.label}
              />
            )
          )}
        </Section>

        <Section
          title="Projects"
          icon={FolderOpen}
          open={openSections.projects}
          onToggle={() => toggleSection("projects")}
          collapsed={collapsed}
        >
          {PROJECT_LINKS.map((link) =>
            collapsed ? (
              <RailIcon key={link.href} icon={link.icon} label={link.label} href={link.href} />
            ) : (
              <NavLink key={link.href} {...link} />
            )
          )}
        </Section>

        <Section
          title="Tools"
          icon={Wrench}
          open={openSections.tools}
          onToggle={() => toggleSection("tools")}
          collapsed={collapsed}
        >
          {TOOL_LINKS.map((tool) =>
            collapsed ? (
              <RailIcon key={tool.href} icon={tool.icon} label={tool.label} href={tool.href} />
            ) : (
              <NavLink key={tool.href} {...tool} />
            )
          )}
        </Section>

        {isAdmin && (
          <Section
            title="Admin"
            icon={Settings}
            open={openSections.admin}
            onToggle={() => toggleSection("admin")}
            collapsed={collapsed}
          >
            {collapsed ? (
              <>
                <RailIcon icon={SlidersHorizontal} label="Fine-tuning" href="/finetune" />
                <RailIcon icon={Settings} label="Admin" href="/admin" />
              </>
            ) : (
              <>
                <NavLink href="/finetune" icon={SlidersHorizontal} label="Fine-tuning" />
                <NavLink href="/admin" icon={Settings} label="Admin" />
              </>
            )}
          </Section>
        )}

        {collapsed ? (
          <div className="flex justify-center">
            <RailIcon icon={Clock} label="History" onClick={expandHistory} />
          </div>
        ) : (
          <Section
            title="History"
            icon={Clock}
            open={openSections.history}
            onToggle={() => toggleSection("history")}
            collapsed={collapsed}
          >
            {conversations.length > 0 && (
              <div className="relative mb-1 px-1">
                <Search className="pointer-events-none absolute left-3.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-gray-400" />
                <input
                  value={historyFilter}
                  onChange={(e) => setHistoryFilter(e.target.value)}
                  placeholder="Filter conversations..."
                  className="w-full rounded-full border border-gray-200 bg-gray-50 py-1.5 pl-8 pr-2 text-xs text-gray-700 outline-none placeholder:text-gray-400 focus:border-indigo-400"
                />
              </div>
            )}
            {conversations.length === 0 && (
              <p className="px-3 py-1 text-xs text-gray-400">No conversations yet.</p>
            )}
            {conversations.length > 0 && filteredConversations.length === 0 && (
              <p className="px-3 py-1 text-xs text-gray-400">No matches.</p>
            )}
            {filteredConversations.map((c) => (
              <div
                key={c.id}
                className={`group flex items-center justify-between rounded-full px-3 py-2 text-sm transition ${
                  c.id === activeId ? "bg-indigo-50 text-indigo-700" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }`}
              >
                <button onClick={() => onSelect(c.id)} className="flex-1 truncate text-left">
                  {c.title}
                </button>
                <button
                  onClick={() => onDelete(c.id)}
                  className="ml-2 shrink-0 opacity-0 transition group-hover:opacity-100 hover:text-red-500"
                  aria-label="Delete conversation"
                >
                  <X className="h-3.5 w-3.5" strokeWidth={2.5} />
                </button>
              </div>
            ))}
          </Section>
        )}
      </nav>

      <AccountMenu userEmail={userEmail} isAdmin={isAdmin} collapsed={collapsed} onLogout={onLogout} />
    </aside>
  );
}
