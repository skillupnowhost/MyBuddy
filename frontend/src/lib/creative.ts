import { apiJson } from "./api";
import type { BrandKitItem, CreativeAssetItem, CreativeAssetType, CreativeProjectItem, VectorDocumentPurpose } from "./types";

export interface BrandKitParams {
  name: string;
  primary_color?: string;
  secondary_color?: string;
  accent_color?: string;
  font_family?: string;
}

export function createBrandKit(params: BrandKitParams): Promise<BrandKitItem> {
  return apiJson<BrandKitItem>("/api/v1/creative/brand-kits", {
    method: "POST",
    body: JSON.stringify(params),
  });
}

export function listBrandKits(): Promise<BrandKitItem[]> {
  return apiJson<BrandKitItem[]>("/api/v1/creative/brand-kits");
}

export async function deleteBrandKit(id: string): Promise<void> {
  await apiJson(`/api/v1/creative/brand-kits/${id}`, { method: "DELETE" });
}

export function createCreativeProject(title: string, brandKitId?: string): Promise<CreativeProjectItem> {
  return apiJson<CreativeProjectItem>("/api/v1/creative/projects", {
    method: "POST",
    body: JSON.stringify({ title, brand_kit_id: brandKitId }),
  });
}

export function listCreativeProjects(): Promise<CreativeProjectItem[]> {
  return apiJson<CreativeProjectItem[]>("/api/v1/creative/projects");
}

export function getCreativeProject(id: string): Promise<CreativeProjectItem> {
  return apiJson<CreativeProjectItem>(`/api/v1/creative/projects/${id}`);
}

export async function deleteCreativeProject(id: string): Promise<void> {
  await apiJson(`/api/v1/creative/projects/${id}`, { method: "DELETE" });
}

export function attachAsset(
  projectId: string,
  assetType: CreativeAssetType,
  assetId: string,
  label?: string,
): Promise<CreativeAssetItem> {
  return apiJson<CreativeAssetItem>(`/api/v1/creative/projects/${projectId}/assets`, {
    method: "POST",
    body: JSON.stringify({ asset_type: assetType, asset_id: assetId, label }),
  });
}

export async function detachAsset(projectId: string, assetId: string): Promise<void> {
  await apiJson(`/api/v1/creative/projects/${projectId}/assets/${assetId}`, { method: "DELETE" });
}

export interface GenerateAssetParams {
  prompt: string;
  purpose?: VectorDocumentPurpose;
  label?: string;
}

export function generateAsset(projectId: string, params: GenerateAssetParams) {
  return apiJson(`/api/v1/creative/projects/${projectId}/assets/generate`, {
    method: "POST",
    body: JSON.stringify(params),
  });
}
