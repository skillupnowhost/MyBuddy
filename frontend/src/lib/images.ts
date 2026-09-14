import { apiFetch, apiJson } from "./api";
import type { ImageItem } from "./types";

export async function uploadImage(file: File): Promise<ImageItem> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await apiFetch("/api/v1/images", { method: "POST", body: formData });
  if (!resp.ok) throw new Error((await resp.text()) || `Upload failed: ${resp.status}`);
  return resp.json();
}

export async function deleteImage(id: string): Promise<void> {
  await apiJson(`/api/v1/images/${id}`, { method: "DELETE" });
}

/** Images are served from an authenticated endpoint (a bearer token, not a cookie), so a
 * plain <img src="/api/v1/images/id"> can't load them directly — fetch the bytes ourselves
 * (apiFetch attaches the token) and hand back a blob: URL the caller must revoke later. */
export async function getImageBlobUrl(id: string): Promise<string> {
  const resp = await apiFetch(`/api/v1/images/${id}`);
  if (!resp.ok) throw new Error(`Could not load image: ${resp.status}`);
  const blob = await resp.blob();
  return URL.createObjectURL(blob);
}
