import { apiFetch, apiJson } from "./api";
import type { AnimationDocumentItem, AnimationEasing, AnimationKeyframeItem } from "./types";

export function createAnimationDocument(
  vectorDocumentId: string,
  prompt: string,
  durationMs?: number,
  frameRate?: number,
  loop = true,
): Promise<AnimationDocumentItem> {
  return apiJson<AnimationDocumentItem>("/api/v1/animation/documents", {
    method: "POST",
    body: JSON.stringify({
      vector_document_id: vectorDocumentId,
      prompt,
      duration_ms: durationMs,
      frame_rate: frameRate,
      loop,
    }),
  });
}

export function listAnimationDocuments(): Promise<AnimationDocumentItem[]> {
  return apiJson<AnimationDocumentItem[]>("/api/v1/animation/documents");
}

export function getAnimationDocument(id: string): Promise<AnimationDocumentItem> {
  return apiJson<AnimationDocumentItem>(`/api/v1/animation/documents/${id}`);
}

export async function deleteAnimationDocument(id: string): Promise<void> {
  await apiJson(`/api/v1/animation/documents/${id}`, { method: "DELETE" });
}

export function addKeyframe(
  animationId: string,
  objectId: string,
  timeMs: number,
  prop: string,
  value: number | string,
  easing: AnimationEasing = "LINEAR",
): Promise<AnimationKeyframeItem> {
  return apiJson<AnimationKeyframeItem>(`/api/v1/animation/documents/${animationId}/keyframes`, {
    method: "POST",
    body: JSON.stringify({ object_id: objectId, time_ms: timeMs, prop, value, easing }),
  });
}

export function updateKeyframe(
  animationId: string,
  keyframeId: string,
  patch: Partial<{ time_ms: number; prop: string; value: number | string; easing: AnimationEasing }>,
): Promise<AnimationKeyframeItem> {
  return apiJson<AnimationKeyframeItem>(`/api/v1/animation/documents/${animationId}/keyframes/${keyframeId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function deleteKeyframe(animationId: string, keyframeId: string): Promise<void> {
  await apiJson(`/api/v1/animation/documents/${animationId}/keyframes/${keyframeId}`, { method: "DELETE" });
}

/** Same authenticated-blob pattern as images.ts::getImageBlobUrl and vector.ts's export —
 * the exported SVG contains real CSS @keyframes and plays natively once set as an <img src>. */
export async function getAnimationBlobUrl(id: string): Promise<string> {
  const resp = await apiFetch(`/api/v1/animation/documents/${id}/export`);
  if (!resp.ok) throw new Error(`Could not load animation: ${resp.status}`);
  const blob = await resp.blob();
  return URL.createObjectURL(blob);
}

export async function downloadAnimationDocument(id: string, filename: string): Promise<void> {
  const resp = await apiFetch(`/api/v1/animation/documents/${id}/export`);
  if (!resp.ok) throw new Error(`Could not export animation: ${resp.status}`);
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
