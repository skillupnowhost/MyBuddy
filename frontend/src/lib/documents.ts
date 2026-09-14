import { apiFetch, apiJson } from "./api";
import type { DocumentItem } from "./types";

export function listDocuments(): Promise<DocumentItem[]> {
  return apiJson<DocumentItem[]>("/api/v1/documents");
}

export async function uploadDocument(file: File): Promise<DocumentItem> {
  const formData = new FormData();
  formData.append("file", file);

  const resp = await apiFetch("/api/v1/documents", { method: "POST", body: formData });
  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(detail || `Upload failed: ${resp.status}`);
  }
  return resp.json();
}

export async function deleteDocument(id: string): Promise<void> {
  await apiJson(`/api/v1/documents/${id}`, { method: "DELETE" });
}
