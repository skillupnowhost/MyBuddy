import { apiFetch, apiJson } from "./api";
import type { DatasetItem, RegisteredModelItem, TrainingJobItem } from "./types";

export function listDatasets(): Promise<DatasetItem[]> {
  return apiJson<DatasetItem[]>("/api/v1/datasets");
}

export async function uploadDataset(file: File): Promise<DatasetItem> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await apiFetch("/api/v1/datasets", { method: "POST", body: formData });
  if (!resp.ok) throw new Error((await resp.text()) || `Upload failed: ${resp.status}`);
  return resp.json();
}

export async function deleteDataset(id: string): Promise<void> {
  await apiJson(`/api/v1/datasets/${id}`, { method: "DELETE" });
}

export function listTrainingJobs(): Promise<TrainingJobItem[]> {
  return apiJson<TrainingJobItem[]>("/api/v1/training-jobs");
}

export function createTrainingJob(
  datasetId: string,
  baseModel: string,
  options?: { epochs?: number; learning_rate?: number; lora_r?: number },
): Promise<TrainingJobItem> {
  return apiJson<TrainingJobItem>("/api/v1/training-jobs", {
    method: "POST",
    body: JSON.stringify({ dataset_id: datasetId, base_model: baseModel, ...options }),
  });
}

export function cancelTrainingJob(id: string): Promise<TrainingJobItem> {
  return apiJson<TrainingJobItem>(`/api/v1/training-jobs/${id}/cancel`, { method: "POST" });
}

export function listRegisteredModels(): Promise<RegisteredModelItem[]> {
  return apiJson<RegisteredModelItem[]>("/api/v1/models/registry");
}

export function promoteModel(id: string, status: string): Promise<RegisteredModelItem> {
  return apiJson<RegisteredModelItem>(`/api/v1/models/registry/${id}/promote`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
