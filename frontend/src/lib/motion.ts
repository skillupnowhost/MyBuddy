import { apiFetch, apiJson } from "./api";
import type { MotionClipItem, MotionProjectItem } from "./types";

export function createMotionProject(
  title: string,
  canvasWidth: number,
  canvasHeight: number,
  totalDurationMs: number,
  loop = false,
): Promise<MotionProjectItem> {
  return apiJson<MotionProjectItem>("/api/v1/motion/projects", {
    method: "POST",
    body: JSON.stringify({
      title,
      canvas_width: canvasWidth,
      canvas_height: canvasHeight,
      total_duration_ms: totalDurationMs,
      loop,
    }),
  });
}

export function listMotionProjects(): Promise<MotionProjectItem[]> {
  return apiJson<MotionProjectItem[]>("/api/v1/motion/projects");
}

export function getMotionProject(id: string): Promise<MotionProjectItem> {
  return apiJson<MotionProjectItem>(`/api/v1/motion/projects/${id}`);
}

export async function deleteMotionProject(id: string): Promise<void> {
  await apiJson(`/api/v1/motion/projects/${id}`, { method: "DELETE" });
}

export function addClip(
  projectId: string,
  animationDocumentId: string,
  startOffsetMs = 0,
  xOffset = 0,
  yOffset = 0,
  zIndex = 0,
): Promise<MotionClipItem> {
  return apiJson<MotionClipItem>(`/api/v1/motion/projects/${projectId}/clips`, {
    method: "POST",
    body: JSON.stringify({
      animation_document_id: animationDocumentId,
      start_offset_ms: startOffsetMs,
      x_offset: xOffset,
      y_offset: yOffset,
      z_index: zIndex,
    }),
  });
}

export function updateClip(
  projectId: string,
  clipId: string,
  patch: Partial<{ start_offset_ms: number; x_offset: number; y_offset: number; z_index: number }>,
): Promise<MotionClipItem> {
  return apiJson<MotionClipItem>(`/api/v1/motion/projects/${projectId}/clips/${clipId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function deleteClip(projectId: string, clipId: string): Promise<void> {
  await apiJson(`/api/v1/motion/projects/${projectId}/clips/${clipId}`, { method: "DELETE" });
}

/** Same authenticated-blob pattern as animation.ts::getAnimationBlobUrl. */
export async function getMotionBlobUrl(id: string): Promise<string> {
  const resp = await apiFetch(`/api/v1/motion/projects/${id}/export`);
  if (!resp.ok) throw new Error(`Could not load motion project: ${resp.status}`);
  const blob = await resp.blob();
  return URL.createObjectURL(blob);
}

export async function downloadMotionProject(id: string, filename: string): Promise<void> {
  const resp = await apiFetch(`/api/v1/motion/projects/${id}/export`);
  if (!resp.ok) throw new Error(`Could not export motion project: ${resp.status}`);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.endsWith(".svg") ? filename : `${filename}.svg`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
