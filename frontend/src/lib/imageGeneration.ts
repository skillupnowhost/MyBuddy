import { apiJson } from "./api";
import type { ImageGenerationJobItem } from "./types";

export interface GenerationParams {
  prompt: string;
  negative_prompt?: string;
  width?: number;
  height?: number;
  steps?: number;
  seed?: number;
}

export function createGenerationJob(params: GenerationParams): Promise<ImageGenerationJobItem> {
  return apiJson<ImageGenerationJobItem>("/api/v1/image-generation", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export function listGenerationJobs(): Promise<ImageGenerationJobItem[]> {
  return apiJson<ImageGenerationJobItem[]>("/api/v1/image-generation");
}

export function getGenerationJob(id: string): Promise<ImageGenerationJobItem> {
  return apiJson<ImageGenerationJobItem>(`/api/v1/image-generation/${id}`);
}

export function cancelGenerationJob(id: string): Promise<ImageGenerationJobItem> {
  return apiJson<ImageGenerationJobItem>(`/api/v1/image-generation/${id}/cancel`, { method: "POST" });
}

const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

/** Same self-scheduling poll-until-terminal-status shape as code.ts::pollExecution. */
export function pollGenerationJob(
  id: string,
  onUpdate: (job: ImageGenerationJobItem) => void,
  intervalMs = 2000,
): () => void {
  let stopped = false;

  async function tick() {
    if (stopped) return;
    try {
      const job = await getGenerationJob(id);
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
