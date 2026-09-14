import { apiFetch, apiJson } from "./api";
import type { VectorDocumentItem, VectorDocumentPurpose, VectorObjectItem, VectorObjectType } from "./types";

export function createVectorDocument(
  prompt: string,
  purpose: VectorDocumentPurpose = "GENERAL",
  canvasWidth?: number,
  canvasHeight?: number,
): Promise<VectorDocumentItem> {
  return apiJson<VectorDocumentItem>("/api/v1/vector/documents", {
    method: "POST",
    body: JSON.stringify({ prompt, purpose, canvas_width: canvasWidth, canvas_height: canvasHeight }),
  });
}

export function listVectorDocuments(): Promise<VectorDocumentItem[]> {
  return apiJson<VectorDocumentItem[]>("/api/v1/vector/documents");
}

export function getVectorDocument(id: string): Promise<VectorDocumentItem> {
  return apiJson<VectorDocumentItem>(`/api/v1/vector/documents/${id}`);
}

export async function deleteVectorDocument(id: string): Promise<void> {
  await apiJson(`/api/v1/vector/documents/${id}`, { method: "DELETE" });
}

export function editVectorDocument(id: string, instruction: string): Promise<VectorDocumentItem> {
  return apiJson<VectorDocumentItem>(`/api/v1/vector/documents/${id}/edit`, {
    method: "POST",
    body: JSON.stringify({ instruction }),
  });
}

export interface NewObjectProps {
  object_type: VectorObjectType;
  [key: string]: unknown;
}

export function addVectorObject(
  documentId: string,
  props: NewObjectProps,
  zIndex = 0,
  layerName = "default",
): Promise<VectorObjectItem> {
  return apiJson<VectorObjectItem>(`/api/v1/vector/documents/${documentId}/objects`, {
    method: "POST",
    body: JSON.stringify({ props, z_index: zIndex, layer_name: layerName }),
  });
}

export function updateVectorObject(
  documentId: string,
  objectId: string,
  prop: string,
  value: number | string,
): Promise<VectorObjectItem> {
  return apiJson<VectorObjectItem>(`/api/v1/vector/documents/${documentId}/objects/${objectId}`, {
    method: "PATCH",
    body: JSON.stringify({ prop, value }),
  });
}

export async function deleteVectorObject(documentId: string, objectId: string): Promise<void> {
  await apiJson(`/api/v1/vector/documents/${documentId}/objects/${objectId}`, { method: "DELETE" });
}

/** The export endpoint is authenticated (bearer token, not a cookie), so a plain <a href>
 * can't download it directly — fetch it ourselves (apiFetch attaches the token) and trigger
 * the save via a throwaway object URL, same auth-workaround shape as images.ts::getImageBlobUrl. */
export async function downloadVectorDocument(id: string, filename: string): Promise<void> {
  const resp = await apiFetch(`/api/v1/vector/documents/${id}/export`);
  if (!resp.ok) throw new Error(`Could not export document: ${resp.status}`);
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
