"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Sparkles, X } from "lucide-react";
import QuickCreatePanel from "@/components/QuickCreatePanel";
import { isLoggedIn } from "@/lib/auth";

const HIDDEN_ON = new Set(["/login", "/register"]);

/** Mounted once in the root layout, so image/video/motion/vector/document generation is
 * reachable from every page — not just the homepage's Quick Create Studio — without navigating
 * away from whatever the user is doing. A floating trigger (bottom-right, matches the app's
 * solid-indigo-600 button language) opens the same QuickCreatePanel used on the homepage inside
 * a modal, chromeless so it doesn't double up on its own card/title inside this one. */
export default function GlobalQuickCreate() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  // Checked client-side only, after mount: isLoggedIn() reads localStorage, which isn't
  // available during SSR — calling it directly in render would render `null` on the server
  // and (for a logged-in user) the real button on the client's first paint, a hydration
  // mismatch. Starting at false and flipping in an effect keeps server and client in sync.
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    setLoggedIn(isLoggedIn());
  }, [pathname]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open]);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (HIDDEN_ON.has(pathname) || !loggedIn) return null;

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        title="Create — image, video, motion, vector or document"
        aria-label="Open Quick Create"
        className="fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-indigo-600 text-white shadow-lg transition hover:scale-105 hover:bg-indigo-500 active:scale-95"
      >
        <Sparkles className="h-6 w-6" strokeWidth={2.25} />
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-4 pt-10 pb-10 backdrop-blur-sm sm:pt-16"
          onClick={() => setOpen(false)}
        >
          <div
            className="thin-scroll flex max-h-full w-full max-w-2xl flex-col overflow-y-auto rounded-3xl bg-white p-4 shadow-2xl sm:p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-500">
                  <Sparkles className="h-4 w-4 text-white" strokeWidth={2.5} />
                </span>
                <div>
                  <h2 className="text-sm font-semibold text-gray-900">Quick Create Studio</h2>
                  <p className="text-xs text-gray-500">Generate from anywhere — no need to leave this page.</p>
                </div>
              </div>
              <button
                onClick={() => setOpen(false)}
                aria-label="Close"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
              >
                <X className="h-4 w-4" strokeWidth={2.5} />
              </button>
            </div>

            <QuickCreatePanel chromeless />
          </div>
        </div>
      )}
    </>
  );
}
