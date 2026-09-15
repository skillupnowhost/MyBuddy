import { apiFetch } from "./api";
import type { Source } from "./types";

const CHAT_REQUEST_TIMEOUT_MS = 45_000;

export async function streamChatMessage(
  conversationId: string,
  content: string,
  onDelta: (delta: string) => void,
  signal?: AbortSignal,
  onSources?: (sources: Source[]) => void,
  onToolCall?: (toolName: string) => void,
  imageIds?: string[],
): Promise<void> {
  const timeoutController = new AbortController();
  let timedOut = false;
  const timeoutId = window.setTimeout(() => {
    timedOut = true;
    timeoutController.abort();
  }, CHAT_REQUEST_TIMEOUT_MS);
  const abortFromCaller = () => timeoutController.abort();
  signal?.addEventListener("abort", abortFromCaller, { once: true });

  try {
    const resp = await apiFetch(`/api/v1/conversations/${conversationId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content, stream: true, image_ids: imageIds ?? [] }),
      signal: timeoutController.signal,
    });

    if (!resp.ok || !resp.body) {
      throw new Error(`Chat request failed: ${resp.status}`);
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let completed = false;

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
        if (payload.error) throw new Error(payload.error);
        if (payload.sources) onSources?.(payload.sources);
        if (payload.tool_call) onToolCall?.(payload.tool_call);
        if (payload.delta) onDelta(payload.delta);
        if (payload.done) {
          completed = true;
          return;
        }
      }
    }
    if (!completed) throw new Error("The chat stream ended before MyBuddy finished responding.");
  } catch (error) {
    if (timedOut) throw new Error("MyBuddy did not respond within 45 seconds. Check that Ollama is running and try again.");
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
    signal?.removeEventListener("abort", abortFromCaller);
  }
}
