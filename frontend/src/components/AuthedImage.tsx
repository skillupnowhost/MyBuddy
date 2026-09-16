"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { getImageBlobUrl } from "@/lib/images";

export default function AuthedImage({
  imageId,
  className,
  alt = "attached image",
  downloadable = false,
  downloadFilename,
  onOpen,
}: {
  imageId: string;
  className?: string;
  alt?: string;
  /** Shows a hover download button that saves the already-loaded image bytes — no re-fetch. */
  downloadable?: boolean;
  downloadFilename?: string;
  /** When provided, the image becomes clickable (cursor-zoom-in) and is passed the already-
   * loaded blob src — the caller owns opening a MediaLightbox with it (no re-fetch needed). */
  onOpen?: (src: string) => void;
}) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    getImageBlobUrl(imageId)
      .then((url) => {
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
  }, [imageId]);

  if (!src) {
    return <div className={`animate-pulse rounded-lg bg-gray-200 ${className ?? "h-24 w-24"}`} />;
  }

  const imgClassName = `${className ?? "h-24 w-24 rounded-lg object-cover"} ${onOpen ? "cursor-zoom-in" : ""}`;
  // eslint-disable-next-line @next/next/no-img-element -- a blob: URL can't go through next/image's loader
  const img = <img src={src} alt={alt} className={imgClassName} onClick={onOpen ? () => onOpen(src) : undefined} />;

  if (!downloadable) return img;

  return (
    <div className="group/img relative inline-block">
      {img}
      <button
        onClick={(e) => {
          e.stopPropagation();
          const link = document.createElement("a");
          link.href = src;
          link.download = downloadFilename ?? `${imageId}.png`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        }}
        aria-label="Download image"
        title="Download"
        className="absolute bottom-1.5 right-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-black/60 text-white opacity-80 transition hover:bg-black/80 hover:opacity-100 group-hover/img:opacity-100"
      >
        <Download className="h-3.5 w-3.5" strokeWidth={2.25} />
      </button>
    </div>
  );
}
