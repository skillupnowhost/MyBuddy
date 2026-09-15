import { apiFetch, apiJson } from "./api";
import type { VideoGenerationJobItem } from "./types";

export interface VideoGenerationParams {
  prompt: string;
  negative_prompt?: string;
  width?: number;
  height?: number;
  num_frames?: number;
  steps?: number;
  seed?: number;
}

export function createVideoGenerationJob(params: VideoGenerationParams): Promise<VideoGenerationJobItem> {
  return apiJson<VideoGenerationJobItem>("/api/v1/video-generation", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export function getVideoGenerationJob(id: string): Promise<VideoGenerationJobItem> {
  return apiJson<VideoGenerationJobItem>(`/api/v1/video-generation/${id}`);
}

export function cancelVideoGenerationJob(id: string): Promise<VideoGenerationJobItem> {
  return apiJson<VideoGenerationJobItem>(`/api/v1/video-generation/${id}/cancel`, { method: "POST" });
}

const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

/** Same self-scheduling poll-until-terminal-status shape as imageGeneration.ts::pollGenerationJob. */
export function pollVideoGenerationJob(
  id: string,
  onUpdate: (job: VideoGenerationJobItem) => void,
  intervalMs = 2500,
): () => void {
  let stopped = false;

  async function tick() {
    if (stopped) return;
    try {
      const job = await getVideoGenerationJob(id);
      onUpdate(job);
      if (TERMINAL_STATUSES.has(job.status)) return;
    } catch {
      return;
    }
    if (!stopped) setTimeout(tick, intervalMs);
  }

  tick();
  return () => {
    stopped = true;
  };
}

/** Videos are served from an authenticated endpoint (a bearer token, not a cookie), so a plain
 * <video src> can't load them directly — fetch the bytes ourselves (apiFetch attaches the
 * token) and hand back a blob: URL, same pattern as images.ts::getImageBlobUrl. */
export async function getVideoBlobUrl(id: string): Promise<{ url: string; contentType: string }> {
  const resp = await apiFetch(`/api/v1/videos/${id}`);
  if (!resp.ok) throw new Error(`Could not load video: ${resp.status}`);
  const blob = await resp.blob();
  return { url: URL.createObjectURL(blob), contentType: blob.type || "video/mp4" };
}

export async function downloadVideo(id: string, filename: string): Promise<void> {
  const resp = await apiFetch(`/api/v1/videos/${id}`);
  if (!resp.ok) throw new Error(`Could not download video: ${resp.status}`);
  const blob = await resp.blob();
  const extension = blob.type === "image/gif" ? ".gif" : ".mp4";
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.endsWith(extension) ? filename : `${filename}${extension}`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
