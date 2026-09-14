import { apiFetch } from "./api";
import type { Source } from "./types";

export async function streamChatMessage(
  conversationId: string,
  content: string,
  onDelta: (delta: string) => void,
  signal?: AbortSignal,
  onSources?: (sources: Source[]) => void,
  onToolCall?: (toolName: string) => void,
  imageIds?: string[],
): Promise<void> {
  const resp = await apiFetch(`/api/v1/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, stream: true, image_ids: imageIds ?? [] }),
    signal,
  });

  if (!resp.ok || !resp.body) {
    throw new Error(`Chat request failed: ${resp.status}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n\n");
    buffer = lines.pop() || "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue;
      const jsonStr = trimmed.slice("data:".length).trim();
      if (!jsonStr) continue;
      const payload = JSON.parse(jsonStr);
      if (payload.sources) onSources?.(payload.sources);
      if (payload.tool_call) onToolCall?.(payload.tool_call);
      if (payload.delta) onDelta(payload.delta);
      if (payload.done) return;
    }
  }
}
