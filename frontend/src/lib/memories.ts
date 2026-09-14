import { apiJson } from "./api";
import type { MemoryItem } from "./types";

export function listMemories(): Promise<MemoryItem[]> {
  return apiJson<MemoryItem[]>("/api/v1/memories");
}

export function createMemory(content: string): Promise<MemoryItem> {
  return apiJson<MemoryItem>("/api/v1/memories", { method: "POST", body: JSON.stringify({ content }) });
}

export async function deleteMemory(id: string): Promise<void> {
  await apiJson(`/api/v1/memories/${id}`, { method: "DELETE" });
}
