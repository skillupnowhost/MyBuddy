import { apiJson } from "./api";
import type { ImageEditJobItem, ImageEditOperation } from "./types";

export interface EditParams {
  operation: ImageEditOperation;
  source_image_id: string;
  mask_image_id?: string;
  prompt?: string;
  negative_prompt?: string;
  steps?: number;
  outpaint_top?: number;
  outpaint_bottom?: number;
  outpaint_left?: number;
  outpaint_right?: number;
}

export function createEditJob(params: EditParams): Promise<ImageEditJobItem> {
  return apiJson<ImageEditJobItem>("/api/v1/image-edit", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export function listEditJobs(): Promise<ImageEditJobItem[]> {
  return apiJson<ImageEditJobItem[]>("/api/v1/image-edit");
}

export function getEditJob(id: string): Promise<ImageEditJobItem> {
  return apiJson<ImageEditJobItem>(`/api/v1/image-edit/${id}`);
}

export function cancelEditJob(id: string): Promise<ImageEditJobItem> {
  return apiJson<ImageEditJobItem>(`/api/v1/image-edit/${id}/cancel`, { method: "POST" });
}

/** Removes a finished job's row server-side — used to auto-clean a FAILED job so it doesn't
 * sit around forever, same pattern as imageGeneration.ts::deleteGenerationJob. */
export function deleteEditJob(id: string): Promise<void> {
  return apiJson<void>(`/api/v1/image-edit/${id}`, { method: "DELETE" });
}

const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

/** Same self-scheduling poll-until-terminal-status shape as imageGeneration.ts::pollGenerationJob. */
export function pollEditJob(id: string, onUpdate: (job: ImageEditJobItem) => void, intervalMs = 2000): () => void {
  let stopped = false;

  async function tick() {
    if (stopped) return;
    try {
      const job = await getEditJob(id);
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
