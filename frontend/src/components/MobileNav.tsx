"use client";

import Link from "next/link";
import { useState } from "react";
import {
  Menu,
  Search,
  Plus,
  Home,
  X,
  LogOut,
  Settings,
  SlidersHorizontal,
  CreditCard,
  type LucideIcon,
} from "lucide-react";
import AnimatedIcon from "@/components/AnimatedIcon";
import { TOOL_LINKS, LIBRARY_ACTIONS, PROJECT_LINKS, type LibraryActionKey } from "@/lib/navigation";
import { firstNameFromEmail } from "@/lib/displayName";
import type { Conversation } from "@/lib/types";

interface MobileTopBarProps {
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

function DrawerLink({ href, icon: Icon, label, onClick }: { href: string; icon: LucideIcon; label: string; onClick: () => void }) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-full px-3 py-2.5 text-left text-sm text-gray-600 transition hover:bg-gray-100 hover:text-gray-900"
    >
      <AnimatedIcon icon={Icon} />
      {label}
    </Link>
  );
}

function DrawerButton({ onClick, icon: Icon, label, active }: { onClick: () => void; icon: LucideIcon; label: string; active?: boolean }) {
  return (
    <button
      onClick={onClick}
      className={`flex w-full items-center gap-3 rounded-full px-3 py-2.5 text-left text-sm transition ${
        active ? "bg-indigo-50 text-indigo-700" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
      }`}
    >
      <AnimatedIcon icon={Icon} />
      {label}
    </button>
  );
}

/** Fixed top bar: hamburger (opens the nav drawer), icon-only search, account avatar. Mobile only.
 * The avatar is the single profile access point on mobile — it opens the same Settings /
 * Subscriptions / Log out sheet that a bottom bar previously duplicated. */
export function MobileTopBar({
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
}: MobileTopBarProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const firstName = firstNameFromEmail(userEmail);
  const initial = userEmail ? firstName.charAt(0).toUpperCase() : "?";
  const closeDrawer = () => setDrawerOpen(false);

  return (
    <div className="lg:hidden">
      <header className="fixed inset-x-0 top-0 z-30 flex items-center gap-2 border-b border-gray-200 bg-white/90 px-3 py-2.5 backdrop-blur">
        <button
          onClick={() => setDrawerOpen(true)}
          aria-label="Open menu"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-gray-600 transition hover:bg-gray-100"
        >
          <Menu className="h-5 w-5" strokeWidth={2.2} />
        </button>

        <div className="flex-1" />

        <button
          onClick={onOpenSearch}
          aria-label="Search"
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-gray-600 transition hover:bg-gray-100"
        >
          <Search className="h-[18px] w-[18px]" strokeWidth={2} />
        </button>

        <button
          onClick={() => setProfileOpen(true)}
          aria-label="Profile, settings & subscriptions"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-sm font-medium text-white"
        >
          {initial}
        </button>
      </header>
      {/* Spacer so page content starts below the fixed top bar */}
      <div className="h-[57px]" />

      {drawerOpen && (
        <div className="fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/40" onClick={closeDrawer} />
          <div className="thin-scroll absolute inset-y-0 left-0 flex w-[82%] max-w-xs flex-col overflow-y-auto border-r border-gray-200 bg-white p-3 shadow-2xl">
            <div className="mb-3 flex items-center gap-2 px-2 pt-2">
              <h1 className="flex-1 text-base font-semibold text-gray-900">MyBuddy</h1>
              <button
                onClick={closeDrawer}
                aria-label="Close menu"
                className="flex h-8 w-8 items-center justify-center rounded-full text-gray-500 hover:bg-gray-100 hover:text-gray-900"
              >
                <X className="h-4 w-4" strokeWidth={2.5} />
              </button>
            </div>

            <button
              onClick={() => {
                onNew();
                closeDrawer();
              }}
              className="mb-3 flex w-full items-center justify-center gap-2 rounded-full bg-indigo-600 px-3 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-500"
            >
              <AnimatedIcon icon={Plus} className="h-4 w-4" strokeWidth={2.5} />
              New Chat
            </button>

            <div className="space-y-4">
              <DrawerButton
                onClick={() => {
                  onHome();
                  closeDrawer();
                }}
                icon={Home}
                label="Home"
                active={!activeId}
              />

              <div>
                <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">Library</p>
                <div className="space-y-1">
                  {LIBRARY_ACTIONS.map((action) => (
                    <DrawerButton
                      key={action.key}
                      onClick={() => {
                        onLibraryAction(action.key);
                        closeDrawer();
                      }}
                      icon={action.icon}
                      label={action.label}
                    />
                  ))}
                </div>
              </div>

              <div>
                <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">Projects</p>
                <div className="space-y-1">
                  {PROJECT_LINKS.map((link) => (
                    <DrawerLink key={link.href} {...link} onClick={closeDrawer} />
                  ))}
                </div>
              </div>

              <div>
                <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">Tools</p>
                <div className="space-y-1">
                  {TOOL_LINKS.map((tool) => (
                    <DrawerLink key={tool.href} {...tool} onClick={closeDrawer} />
                  ))}
                </div>
              </div>

              {isAdmin && (
                <div className="space-y-1">
                  <DrawerLink href="/finetune" icon={SlidersHorizontal} label="Fine-tuning" onClick={closeDrawer} />
                  <DrawerLink href="/admin" icon={Settings} label="Admin" onClick={closeDrawer} />
                </div>
              )}

              <div>
                <p className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wide text-gray-400">History</p>
                <div className="space-y-1">
                  {conversations.length === 0 && <p className="px-3 py-1 text-xs text-gray-400">No conversations yet.</p>}
                  {conversations.map((c) => (
                    <div
                      key={c.id}
                      className={`group flex items-center justify-between rounded-full px-3 py-2 text-sm transition ${
                        c.id === activeId ? "bg-indigo-50 text-indigo-700" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                      }`}
                    >
                      <button
                        onClick={() => {
                          onSelect(c.id);
                          closeDrawer();
                        }}
                        className="flex-1 truncate text-left"
                      >
                        {c.title}
                      </button>
                      <button
                        onClick={() => onDelete(c.id)}
                        className="ml-2 shrink-0 text-gray-400 hover:text-red-500"
                        aria-label="Delete conversation"
                      >
                        <X className="h-3.5 w-3.5" strokeWidth={2.5} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {profileOpen && (
        <div className="fixed inset-0 z-40">
          <div className="absolute inset-0 bg-black/40" onClick={() => setProfileOpen(false)} />
          <div className="absolute inset-x-0 bottom-0 rounded-t-3xl bg-white p-4 pb-[calc(env(safe-area-inset-bottom)+1rem)] shadow-2xl">
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-gray-200" />
            <div className="mb-3 flex items-center gap-3 px-1">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-sm font-medium text-white">
                {initial}
              </span>
              <p className="truncate text-sm font-medium text-gray-900">{firstName}</p>
            </div>
            <div className="space-y-1">
              <button className="flex w-full items-center gap-3 rounded-full px-3 py-2.5 text-left text-sm text-gray-700 transition hover:bg-gray-100">
                <Settings className="h-4 w-4 text-gray-500" strokeWidth={2} />
                Settings
              </button>
              <button className="flex w-full items-center gap-3 rounded-full px-3 py-2.5 text-left text-sm text-gray-700 transition hover:bg-gray-100">
                <CreditCard className="h-4 w-4 text-gray-500" strokeWidth={2} />
                Subscriptions
              </button>
              <button
                onClick={() => {
                  setProfileOpen(false);
                  onLogout();
                }}
                className="flex w-full items-center gap-3 rounded-full px-3 py-2.5 text-left text-sm text-red-600 transition hover:bg-red-50"
              >
                <LogOut className="h-4 w-4" strokeWidth={2} />
                Log out
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
