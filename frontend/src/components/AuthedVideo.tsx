"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { getVideoBlobUrl } from "@/lib/videoGeneration";

export default function AuthedVideo({
  videoId,
  className,
  downloadFilename,
  onOpen,
}: {
  videoId: string;
  className?: string;
  downloadFilename?: string;
  /** When provided, the video becomes clickable (cursor-zoom-in) and is passed the already-
   * loaded blob src — the caller owns opening a MediaLightbox with it (no re-fetch needed). */
  onOpen?: (src: string) => void;
}) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    getVideoBlobUrl(videoId)
      .then(({ url }) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setSrc(url);
      })
      .catch(() => {});

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [videoId]);

  if (!src) {
    return <div className={`animate-pulse rounded-lg bg-gray-200 ${className ?? "h-32 w-full"}`} />;
  }

  return (
    <div className="group/vid relative inline-block w-full">
      <video
        src={src}
        className={`${className ?? "h-32 w-full rounded-lg object-cover"} ${onOpen ? "cursor-zoom-in" : ""}`}
        loop
        muted
        autoPlay
        playsInline
        onClick={onOpen ? () => onOpen(src) : undefined}
      />
      <button
        onClick={(e) => {
          e.stopPropagation();
          const link = document.createElement("a");
          link.href = src;
          link.download = downloadFilename ?? `${videoId}.mp4`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        }}
        aria-label="Download video"
        title="Download"
        className="absolute bottom-1.5 right-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-black/60 text-white opacity-80 transition hover:bg-black/80 hover:opacity-100 group-hover/vid:opacity-100"
      >
        <Download className="h-3.5 w-3.5" strokeWidth={2.25} />
      </button>
    </div>
  );
}
