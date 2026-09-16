"use client";

import { useEffect } from "react";
import { Download, RotateCw, Wand2, X } from "lucide-react";
import CopyButton from "@/components/CopyButton";

const ACTION_BTN =
  "flex h-9 w-9 items-center justify-center rounded-full bg-white/10 text-white/80 transition hover:bg-white/20 hover:text-white";

interface MediaLightboxProps {
  open: boolean;
  onClose: () => void;
  mediaType: "image" | "video" | "svg";
  src: string;
  alt?: string;
  prompt?: string | null;
  onDownload?: () => void;
  onRegenerate?: () => void;
  onEditImage?: () => void;
}

/** Premium fullscreen viewer for a generated image/video/SVG — click a thumbnail to open,
 * Escape or backdrop click to close. Same overlay shape as SearchOverlay.tsx (fixed inset-0,
 * backdrop-blur, stopPropagation on the content) but centers media instead of a list. */
export default function MediaLightbox({
  open,
  onClose,
  mediaType,
  src,
  alt = "Generated result",
  prompt,
  onDownload,
  onRegenerate,
  onEditImage,
}: MediaLightboxProps) {
  useEffect(() => {
    if (!open) return;
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex flex-col items-center justify-center gap-4 bg-black/85 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[85vh] max-w-[90vw] flex-col items-center gap-3"
        onClick={(e) => e.stopPropagation()}
      >
        {mediaType === "video" ? (
          // eslint-disable-next-line jsx-a11y/media-has-caption -- generated preview, no captions available
          <video
            src={src}
            controls
            autoPlay
            loop
            className="max-h-[75vh] max-w-[90vw] rounded-2xl object-contain shadow-2xl"
          />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element -- a blob: URL can't go through next/image's loader
          <img
            src={src}
            alt={alt}
            className={`max-h-[75vh] max-w-[90vw] rounded-2xl object-contain shadow-2xl ${mediaType === "svg" ? "bg-white p-4" : ""}`}
          />
        )}

        {prompt && (
          <p className="thin-scroll max-h-20 max-w-xl overflow-y-auto text-center text-sm text-white/70">{prompt}</p>
        )}

        <div className="flex items-center gap-2">
          {onDownload && (
            <button onClick={onDownload} title="Download" aria-label="Download" className={ACTION_BTN}>
              <Download className="h-4 w-4" strokeWidth={2.25} />
            </button>
          )}
          {prompt && (
            <CopyButton
              text={prompt}
              className={`${ACTION_BTN} [&_svg]:text-inherit`}
            />
          )}
          {onRegenerate && (
            <button onClick={onRegenerate} title="Regenerate" aria-label="Regenerate" className={ACTION_BTN}>
              <RotateCw className="h-4 w-4" strokeWidth={2.25} />
            </button>
          )}
          {onEditImage && (
            <button onClick={onEditImage} title="Edit image" aria-label="Edit image" className={ACTION_BTN}>
              <Wand2 className="h-4 w-4" strokeWidth={2.25} />
            </button>
          )}
          <button onClick={onClose} title="Close" aria-label="Close" className={ACTION_BTN}>
            <X className="h-4 w-4" strokeWidth={2.5} />
          </button>
        </div>
      </div>
    </div>
  );
}
