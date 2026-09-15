"use client";

import { useState } from "react";
import { Search, Sun, Bell } from "lucide-react";

export default function Header({ userEmail, onLogout }: { userEmail: string | null; onLogout: () => void }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const initial = (userEmail ?? "?").trim().charAt(0).toUpperCase();

  return (
    <header className="flex items-center gap-3 border-b border-gray-200 bg-white/80 px-6 py-3 backdrop-blur">
      <div className="relative flex-1 max-w-xl">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        <input
          type="text"
          placeholder="Search anything..."
          className="w-full rounded-lg border border-gray-200 bg-gray-50 py-2 pl-9 pr-3 text-sm text-gray-700 outline-none transition focus:border-indigo-400 focus:bg-white"
        />
      </div>

      <div className="flex items-center gap-1.5">
        <button
          title="Toggle theme"
          className="group flex h-9 w-9 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100"
        >
          <Sun className="h-[18px] w-[18px] transition-transform duration-500 group-hover:rotate-90" strokeWidth={2} />
        </button>
        <button
          title="Notifications"
          className="group flex h-9 w-9 items-center justify-center rounded-full text-gray-500 transition hover:bg-gray-100"
        >
          <Bell className="h-[18px] w-[18px] transition-transform duration-200 group-hover:rotate-12" strokeWidth={2} />
        </button>

        <div className="relative ml-1">
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-500 text-sm font-medium text-white"
          >
            {initial}
          </button>
          {menuOpen && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(false)} />
              <div className="absolute right-0 z-20 mt-2 w-48 rounded-lg border border-gray-200 bg-white py-1 shadow-lg">
                <p className="truncate border-b border-gray-100 px-3 py-2 text-xs text-gray-500">{userEmail}</p>
                <button
                  onClick={onLogout}
                  className="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
                >
                  Log out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
