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
}: {
  imageId: string;
  className?: string;
  alt?: string;
  /** Shows a hover download button that saves the already-loaded image bytes — no re-fetch. */
  downloadable?: boolean;
  downloadFilename?: string;
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

  if (!downloadable) {
    // eslint-disable-next-line @next/next/no-img-element -- a blob: URL can't go through next/image's loader
    return <img src={src} alt={alt} className={className ?? "h-24 w-24 rounded-lg object-cover"} />;
  }

  return (
    <div className="group/img relative inline-block">
      {/* eslint-disable-next-line @next/next/no-img-element -- a blob: URL can't go through next/image's loader */}
      <img src={src} alt={alt} className={className ?? "h-24 w-24 rounded-lg object-cover"} />
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
