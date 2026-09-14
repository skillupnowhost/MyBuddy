import { apiFetch, apiJson } from "./api";
import type { CodeExecutionItem, CodeFileContentItem, CodeFileItem, CodeProjectItem } from "./types";

export function listCodeProjects(): Promise<CodeProjectItem[]> {
  return apiJson<CodeProjectItem[]>("/api/v1/code/projects");
}

export function getCodeProject(id: string): Promise<CodeProjectItem> {
  return apiJson<CodeProjectItem>(`/api/v1/code/projects/${id}`);
}

export async function uploadCodeProject(file: File): Promise<CodeProjectItem> {
  const formData = new FormData();
  formData.append("file", file);
  const resp = await apiFetch("/api/v1/code/projects", { method: "POST", body: formData });
  if (!resp.ok) throw new Error((await resp.text()) || `Upload failed: ${resp.status}`);
  return resp.json();
}

export function getCodeProjectTree(id: string): Promise<CodeFileItem[]> {
  return apiJson<CodeFileItem[]>(`/api/v1/code/projects/${id}/tree`);
}

export function getCodeFileContent(projectId: string, fileId: string): Promise<CodeFileContentItem> {
  return apiJson<CodeFileContentItem>(`/api/v1/code/projects/${projectId}/files/${fileId}`);
}

export async function deleteCodeProject(id: string): Promise<void> {
  await apiJson(`/api/v1/code/projects/${id}`, { method: "DELETE" });
}

export function submitExecution(language: string, source: string): Promise<CodeExecutionItem> {
  return apiJson<CodeExecutionItem>("/api/v1/code/execute", {
    method: "POST",
    body: JSON.stringify({ language, source }),
  });
}

export function getExecution(id: string): Promise<CodeExecutionItem> {
  return apiJson<CodeExecutionItem>(`/api/v1/code/execute/${id}`);
}

export function listExecutions(): Promise<CodeExecutionItem[]> {
  return apiJson<CodeExecutionItem[]>("/api/v1/code/execute");
}

const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED", "TIMEOUT", "CANCELLED"]);

/** Polls a sandbox job until it reaches a terminal status. Sandbox jobs finish in low
 * single-digit seconds, so this polls much tighter than finetune's 4s job polling. Returns
 * an unsubscribe function so callers can stop early (e.g. component unmount). */
export function pollExecution(
  id: string,
  onUpdate: (job: CodeExecutionItem) => void,
  intervalMs = 1000,
): () => void {
  let stopped = false;

  async function tick() {
    if (stopped) return;
    try {
      const job = await getExecution(id);
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
