"use client";

import { useEffect, useState } from "react";
import { getImageBlobUrl } from "@/lib/images";

export default function AuthedImage({
  imageId,
  className,
  alt = "attached image",
}: {
  imageId: string;
  className?: string;
  alt?: string;
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
    return <div className={`animate-pulse rounded-lg bg-white/10 ${className ?? "h-24 w-24"}`} />;
  }

  // eslint-disable-next-line @next/next/no-img-element -- a blob: URL can't go through next/image's loader
  return <img src={src} alt={alt} className={className ?? "h-24 w-24 rounded-lg object-cover"} />;
}
