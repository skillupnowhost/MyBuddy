"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";

export default function CopyButton({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(text);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  }

  const Icon = copied ? Check : Copy;

  return (
    <button
      onClick={handleCopy}
      title={copied ? "Copied!" : "Copy"}
      aria-label="Copy code"
      className={
        className ??
        "flex h-7 w-7 items-center justify-center rounded-full bg-white/10 text-white/80 opacity-0 transition group-hover:opacity-100 hover:bg-white/20"
      }
    >
      {/* Keying on `copied` remounts the icon on each toggle, retriggering the pop-in
          keyframe (see .animate-icon-pop in globals.css) instead of only playing once. Color
          is deliberately not set here — it inherits from whatever text color the caller's
          className puts on the button, since this renders on both dark (code block header)
          and light (message action row) backgrounds. */}
      <Icon key={copied ? "check" : "copy"} className="h-3.5 w-3.5 animate-icon-pop" strokeWidth={2.25} />
    </button>
  );
}
