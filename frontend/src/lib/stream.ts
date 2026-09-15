import { apiFetch } from "./api";
import type { Source } from "./types";

// An IDLE timeout (resets on every chunk received), not a total-request timeout — a short
// chat reply and a long generated document both stream for very different total durations,
// but both should only be killed if the connection actually goes quiet, not because the
// whole thing took longer than some fixed wall-clock budget. Generous on purpose: on
// CPU-only local inference, first-token latency for a long or complex prompt can genuinely
// run past a minute — a tight timeout here doesn't recover anything, it just fires the retry
// in sendMessage while the original request may still be working, which is how a slow model
// turns into "sent multiple times, no reply ever arrives" (see chat/page.tsx's
// userMessagePersisted guard for the other half of that fix).
const IDLE_TIMEOUT_MS = 120_000;

export async function streamChatMessage(
  conversationId: string,
  content: string,
  onDelta: (delta: string) => void,
  signal?: AbortSignal,
  onSources?: (sources: Source[]) => void,
  onToolCall?: (toolName: string) => void,
  imageIds?: string[],
  onImage?: (imageId: string) => void,
  onUserMessageId?: (id: string) => void,
): Promise<void> {
  const timeoutController = new AbortController();
  let timedOut = false;
  let idleTimeoutId = 0;
  const resetIdleTimer = () => {
    window.clearTimeout(idleTimeoutId);
    idleTimeoutId = window.setTimeout(() => {
      timedOut = true;
      timeoutController.abort();
    }, IDLE_TIMEOUT_MS);
  };
  resetIdleTimer();
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
      resetIdleTimer();
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
        if (payload.image_id) onImage?.(payload.image_id);
        if (payload.user_message_id) onUserMessageId?.(payload.user_message_id);
        if (payload.delta) onDelta(payload.delta);
        if (payload.done) {
          completed = true;
          return;
        }
      }
    }
    if (!completed) throw new Error("The chat stream ended before MyBuddy finished responding.");
  } catch (error) {
    if (timedOut) throw new Error("MyBuddy stopped responding. Check that Ollama is running and try again.");
    throw error;
  } finally {
    window.clearTimeout(idleTimeoutId);
    signal?.removeEventListener("abort", abortFromCaller);
  }
}
