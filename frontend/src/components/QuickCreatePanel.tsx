"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Clapperboard,
  Download,
  FileText,
  Image as ImageIcon,
  PenTool,
  Sparkles,
  Video,
  X,
  type LucideIcon,
} from "lucide-react";
import AnimatedIcon from "@/components/AnimatedIcon";
import { LoadingDots, LoadingGrid, LoadingRings } from "@/components/LoadingIcons";
import MediaLightbox from "@/components/MediaLightbox";
import { apiFetch, apiJson } from "@/lib/api";
import { createAnimationDocument, getAnimationBlobUrl, downloadAnimationDocument } from "@/lib/animation";
import { getImageBlobUrl } from "@/lib/images";
import { cancelGenerationJob, createGenerationJob, deleteGenerationJob, pollGenerationJob } from "@/lib/imageGeneration";
import { createVectorDocument, downloadVectorDocument } from "@/lib/vector";
import {
  cancelVideoGenerationJob,
  createVideoGenerationJob,
  downloadVideo,
  getVideoBlobUrl,
  pollVideoGenerationJob,
} from "@/lib/videoGeneration";
import { streamChatMessage } from "@/lib/stream";
import type { Conversation, VectorDocumentPurpose } from "@/lib/types";

type TabId = "image" | "video" | "motion" | "vector" | "document";

interface TabResult {
  status: "idle" | "generating" | "done" | "error";
  stageLabel?: string;
  error?: string;
  previewUrl?: string;
  previewType?: "video" | "image" | "svg" | "text";
  textContent?: string;
  downloadId?: string;
  jobId?: string;
}

const IDLE: TabResult = { status: "idle" };

const TABS: { id: TabId; label: string; icon: LucideIcon; placeholder: string; loadingIcon: "media" | "document" }[] = [
  {
    id: "image",
    label: "Image",
    icon: ImageIcon,
    placeholder: "A watercolor fox sitting in a snowy forest clearing...",
    loadingIcon: "media",
  },
  {
    id: "video",
    label: "Video",
    icon: Video,
    placeholder: "A drone shot flying over a misty mountain forest at sunrise...",
    loadingIcon: "media",
  },
  {
    id: "motion",
    label: "Motion Graphics",
    icon: Clapperboard,
    placeholder: "A bouncing logo reveal with a soft glow burst...",
    loadingIcon: "media",
  },
  {
    id: "vector",
    label: "SVG / Vector",
    icon: PenTool,
    placeholder: "A minimalist mountain and sun logo, flat colors...",
    loadingIcon: "media",
  },
  {
    id: "document",
    label: "Document",
    icon: FileText,
    placeholder: "A one-page project proposal for a community garden app...",
    loadingIcon: "document",
  },
];

/** Sized placeholder shown the instant generation starts — matched to the final asset's
 * aspect ratio (video/motion/vector all default to a square canvas) so the preview area
 * doesn't jump size when the real result swaps in, with the icon matched to what's loading. */
function PreviewSkeleton({ kind }: { kind: "media" | "document" }) {
  return (
    <div className="skeleton-shimmer relative mx-auto flex aspect-square w-full max-w-xs items-center justify-center rounded-2xl">
      {kind === "document" ? (
        <LoadingRings className="h-14 w-14 text-gray-400" />
      ) : (
        <LoadingGrid className="h-14 w-14 text-gray-400" />
      )}
    </div>
  );
}

const VECTOR_PURPOSES: { value: VectorDocumentPurpose; label: string }[] = [
  { value: "GENERAL", label: "General" },
  { value: "ILLUSTRATION", label: "Illustration" },
  { value: "LOGO", label: "Logo" },
  { value: "ICON", label: "Icon" },
];

function slugify(text: string): string {
  const slug = text
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .split("-")
    .slice(0, 6)
    .join("-");
  return slug || "mybuddy-creation";
}

function downloadTextFile(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename.endsWith(".md") ? filename : `${filename}.md`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

async function withOneRetry<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    await new Promise((resolve) => setTimeout(resolve, 900));
    return fn();
  }
}

export default function QuickCreatePanel({
  onActivityChange,
  chromeless = false,
}: {
  onActivityChange?: (active: boolean) => void;
  /** Drops the outer card + title/subtitle — for embedding inside a modal that already
   * supplies its own chrome (see GlobalQuickCreate), instead of the homepage's bare section. */
  chromeless?: boolean;
}) {
  const [activeTab, setActiveTab] = useState<TabId>("image");
  const [prompts, setPrompts] = useState<Record<TabId, string>>({
    image: "",
    video: "",
    motion: "",
    vector: "",
    document: "",
  });
  const [vectorPurpose, setVectorPurpose] = useState<VectorDocumentPurpose>("GENERAL");
  const [results, setResults] = useState<Record<TabId, TabResult>>({
    image: IDLE,
    video: IDLE,
    motion: IDLE,
    vector: IDLE,
    document: IDLE,
  });
  const stopPollRef = useRef<Partial<Record<TabId, () => void>>>({});
  const timeoutRef = useRef<Partial<Record<TabId, number>>>({});
  const [lightboxOpen, setLightboxOpen] = useState(false);

  useEffect(() => {
    return () => {
      Object.values(stopPollRef.current).forEach((stop) => stop?.());
      Object.values(timeoutRef.current).forEach((id) => window.clearTimeout(id));
    };
  }, []);

  // "Entering a request" — typing a prompt or having any result in flight/finished — signals
  // the caller to give this panel more room (e.g. HomeDashboard collapsing its hero banner).
  // Clearing every prompt with nothing generated yet reverts back to inactive.
  useEffect(() => {
    const hasActivity =
      Object.values(prompts).some((p) => p.trim().length > 0) ||
      Object.values(results).some((r) => r.status !== "idle");
    onActivityChange?.(hasActivity);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prompts, results]);

  function setResult(tab: TabId, result: TabResult) {
    setResults((prev) => ({ ...prev, [tab]: result }));
  }

  function clearTabTimers(tab: TabId) {
    stopPollRef.current[tab]?.();
    stopPollRef.current[tab] = undefined;
    const t = timeoutRef.current[tab];
    if (t) window.clearTimeout(t);
    timeoutRef.current[tab] = undefined;
  }

  async function generateImage() {
    const prompt = prompts.image.trim();
    if (!prompt) return;
    clearTabTimers("image");
    setResult("image", { status: "generating", stageLabel: "Starting generation..." });
    try {
      const job = await withOneRetry(() => createGenerationJob({ prompt }));
      setResult("image", { status: "generating", stageLabel: "Generating...", jobId: job.id });

      const stop = pollGenerationJob(job.id, async (updated) => {
        if (updated.status === "COMPLETED" && updated.image_id) {
          clearTabTimers("image");
          try {
            const url = await getImageBlobUrl(updated.image_id);
            setResult("image", { status: "done", previewUrl: url, previewType: "image", downloadId: updated.image_id });
          } catch {
            setResult("image", { status: "error", error: "The image finished but couldn't be loaded for preview." });
          }
        } else if (updated.status === "FAILED" || updated.status === "CANCELLED") {
          clearTabTimers("image");
          if (updated.status === "FAILED") deleteGenerationJob(updated.id).catch(() => {});
          setResult("image", {
            status: "error",
            error: updated.status === "CANCELLED" ? "Generation cancelled." : updated.error_message || "Image generation failed.",
          });
        }
      });
      stopPollRef.current.image = stop;
      timeoutRef.current.image = window.setTimeout(() => {
        clearTabTimers("image");
        setResult("image", { status: "error", error: "This is taking longer than expected. Please try again." });
      }, 5 * 60 * 1000);
    } catch (err) {
      setResult("image", { status: "error", error: err instanceof Error ? err.message : "Could not start image generation." });
    }
  }

  function cancelImage() {
    const jobId = results.image.jobId;
    clearTabTimers("image");
    setResult("image", IDLE);
    if (jobId) cancelGenerationJob(jobId).catch(() => {});
  }

  async function generateVideo() {
    const prompt = prompts.video.trim();
    if (!prompt) return;
    clearTabTimers("video");
    setResult("video", { status: "generating", stageLabel: "Starting generation..." });
    try {
      const job = await withOneRetry(() => createVideoGenerationJob({ prompt }));
      setResult("video", {
        status: "generating",
        stageLabel: "Rendering frames... this can take a long time without a GPU.",
        jobId: job.id,
      });

      const stop = pollVideoGenerationJob(job.id, async (updated) => {
        if (updated.status === "COMPLETED" && updated.video_id) {
          clearTabTimers("video");
          try {
            const { url } = await getVideoBlobUrl(updated.video_id);
            setResult("video", { status: "done", previewUrl: url, previewType: "video", downloadId: updated.video_id });
          } catch {
            setResult("video", { status: "error", error: "The video finished but couldn't be loaded for preview." });
          }
        } else if (updated.status === "FAILED" || updated.status === "CANCELLED") {
          clearTabTimers("video");
          setResult("video", {
            status: "error",
            error: updated.status === "CANCELLED" ? "Generation cancelled." : updated.error_message || "Video generation failed.",
          });
        }
      });
      stopPollRef.current.video = stop;
      // Text-to-video diffusion on CPU-only hardware is dramatically slower than image
      // generation (many frames, each its own denoising pass) — a short 5-minute cap would
      // almost always fire before a real (if slow) generation finishes. This still bounds
      // the wait, just generously enough to let CPU-only hardware actually complete.
      timeoutRef.current.video = window.setTimeout(() => {
        clearTabTimers("video");
        setResult("video", { status: "error", error: "This is taking longer than expected. Please try again." });
      }, 30 * 60 * 1000);
    } catch (err) {
      setResult("video", { status: "error", error: err instanceof Error ? err.message : "Could not start video generation." });
    }
  }

  function cancelVideo() {
    const jobId = results.video.jobId;
    clearTabTimers("video");
    setResult("video", IDLE);
    if (jobId) cancelVideoGenerationJob(jobId).catch(() => {});
  }

  async function generateMotion() {
    const prompt = prompts.motion.trim();
    if (!prompt) return;
    setResult("motion", { status: "generating", stageLabel: "Sketching the artwork..." });
    try {
      const vectorDoc = await withOneRetry(() => createVectorDocument(prompt, "ILLUSTRATION"));
      setResult("motion", { status: "generating", stageLabel: "Choreographing the motion..." });
      const animationDoc = await withOneRetry(() => createAnimationDocument(vectorDoc.id, prompt));
      const url = await getAnimationBlobUrl(animationDoc.id);
      setResult("motion", { status: "done", previewUrl: url, previewType: "svg", downloadId: animationDoc.id });
    } catch (err) {
      setResult("motion", { status: "error", error: err instanceof Error ? err.message : "Could not generate the motion graphic." });
    }
  }

  async function generateVector() {
    const prompt = prompts.vector.trim();
    if (!prompt) return;
    setResult("vector", { status: "generating", stageLabel: "Drawing..." });
    try {
      const doc = await withOneRetry(() => createVectorDocument(prompt, vectorPurpose));
      const resp = await apiFetch(`/api/v1/vector/documents/${doc.id}/export`);
      if (!resp.ok) throw new Error("Could not load the generated SVG for preview.");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      setResult("vector", { status: "done", previewUrl: url, previewType: "svg", downloadId: doc.id });
    } catch (err) {
      setResult("vector", { status: "error", error: err instanceof Error ? err.message : "Could not generate the SVG." });
    }
  }

  async function generateDocument() {
    const prompt = prompts.document.trim();
    if (!prompt) return;
    setResult("document", { status: "generating", stageLabel: "Writing...", textContent: "" });
    try {
      const assembled = await withOneRetry(async () => {
        const conversation = await apiJson<Conversation>("/api/v1/conversations", { method: "POST", body: JSON.stringify({}) });
        let text = "";
        await streamChatMessage(
          conversation.id,
          `Write a clear, well-organized document on the following topic. Use markdown headings and, where useful, bullet points or numbered lists. Start directly with the content — no preamble like "Here is the document".\n\nTopic: ${prompt}`,
          (delta) => {
            text += delta;
            setResult("document", { status: "generating", stageLabel: "Writing...", textContent: text });
          },
        );
        return text;
      });
      setResult("document", { status: "done", textContent: assembled, previewType: "text" });
    } catch (err) {
      setResult("document", { status: "error", error: err instanceof Error ? err.message : "Could not generate the document." });
    }
  }

  function handleGenerate() {
    if (activeTab === "image") generateImage();
    else if (activeTab === "video") generateVideo();
    else if (activeTab === "motion") generateMotion();
    else if (activeTab === "vector") generateVector();
    else generateDocument();
  }

  function handleDownload() {
    const result = results[activeTab];
    const filename = slugify(prompts[activeTab]);
    if (activeTab === "image" && result.previewUrl) {
      const link = document.createElement("a");
      link.href = result.previewUrl;
      link.download = `${filename}.png`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else if (activeTab === "video" && result.downloadId) downloadVideo(result.downloadId, filename);
    else if (activeTab === "motion" && result.downloadId) downloadAnimationDocument(result.downloadId, filename);
    else if (activeTab === "vector" && result.downloadId) downloadVectorDocument(result.downloadId, filename);
    else if (activeTab === "document" && result.textContent) downloadTextFile(filename, result.textContent);
  }

  const tab = TABS.find((t) => t.id === activeTab)!;
  const result = results[activeTab];
  const prompt = prompts[activeTab];
  const isGenerating = result.status === "generating";

  return (
    <section className={chromeless ? "" : "rounded-3xl border border-gray-200 bg-white p-4 sm:p-6"}>
      {!chromeless && (
        <div className="mb-4 flex items-center gap-2">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-500">
            <AnimatedIcon icon={Sparkles} className="h-4 w-4 text-white" strokeWidth={2.5} />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Quick Create Studio</h2>
            <p className="text-xs text-gray-500">Generate & download images, video, motion graphics, SVGs and documents — right here.</p>
          </div>
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`flex items-center gap-1.5 rounded-full px-3.5 py-2 text-sm font-medium transition ${
              activeTab === t.id ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            <t.icon className="h-3.5 w-3.5" strokeWidth={2.25} />
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === "vector" && (
        <div className="mb-3 flex flex-wrap gap-1.5">
          {VECTOR_PURPOSES.map((p) => (
            <button
              key={p.value}
              onClick={() => setVectorPurpose(p.value)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                vectorPurpose === p.value ? "bg-indigo-100 text-indigo-700" : "bg-gray-50 text-gray-500 hover:bg-gray-100"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      )}

      <div className="flex flex-col gap-2 sm:flex-row">
        <textarea
          value={prompt}
          onChange={(e) => setPrompts((prev) => ({ ...prev, [activeTab]: e.target.value }))}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !isGenerating) {
              e.preventDefault();
              handleGenerate();
            }
          }}
          placeholder={tab.placeholder}
          rows={2}
          className="flex-1 resize-none rounded-2xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-900 outline-none focus:border-indigo-400 focus:bg-white"
        />
        <button
          onClick={handleGenerate}
          disabled={!prompt.trim() || isGenerating}
          className="flex shrink-0 items-center justify-center gap-1.5 rounded-full bg-indigo-600 px-5 py-3 text-sm font-medium text-white transition hover:bg-indigo-500 disabled:opacity-40 sm:self-stretch"
        >
          {isGenerating ? <LoadingDots className="h-4 w-4" /> : <tab.icon className="h-4 w-4" strokeWidth={2.25} />}
          Generate
        </button>
      </div>

      {result.status === "generating" && (
        <div className="mt-4">
          <div className="mb-3 flex items-center gap-2 rounded-2xl bg-indigo-50 px-4 py-3 text-sm text-indigo-700">
            <LoadingDots className="h-5 w-5 shrink-0 text-indigo-500" />
            <span className="flex-1">{result.stageLabel ?? "Working..."}</span>
            {activeTab === "image" && (
              <button onClick={cancelImage} className="rounded-full px-2 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-100">
                Cancel
              </button>
            )}
            {activeTab === "video" && (
              <button onClick={cancelVideo} className="rounded-full px-2 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-100">
                Cancel
              </button>
            )}
          </div>

          {activeTab === "document" && result.textContent ? (
            <div className="thin-scroll max-h-48 overflow-y-auto rounded-2xl border border-gray-100 bg-gray-50 p-4 text-sm text-gray-700">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.textContent}</ReactMarkdown>
            </div>
          ) : (
            <div className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
              <PreviewSkeleton kind={tab.loadingIcon} />
            </div>
          )}
        </div>
      )}

      {result.status === "error" && (
        <div className="mt-4 flex items-center gap-2 rounded-2xl bg-red-50 px-4 py-3 text-sm text-red-600">
          <X className="h-4 w-4 shrink-0" strokeWidth={2.5} />
          <span className="flex-1">{result.error}</span>
          <button onClick={handleGenerate} className="rounded-full px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100">
            Try again
          </button>
        </div>
      )}

      {result.status === "done" && (
        <div className="mt-4 rounded-2xl border border-gray-100 bg-gray-50 p-3">
          {result.previewType === "video" && result.previewUrl && (
            // eslint-disable-next-line jsx-a11y/media-has-caption -- generated preview, no captions available
            <video
              src={result.previewUrl}
              controls
              autoPlay
              loop
              muted
              className="mx-auto max-h-72 w-auto cursor-zoom-in rounded-xl"
              onClick={() => setLightboxOpen(true)}
            />
          )}
          {result.previewType === "image" && result.previewUrl && (
            // eslint-disable-next-line @next/next/no-img-element -- a blob: URL can't go through next/image's loader
            <img
              src={result.previewUrl}
              alt="Generated image"
              className="mx-auto max-h-72 w-auto cursor-zoom-in rounded-xl"
              onClick={() => setLightboxOpen(true)}
            />
          )}
          {result.previewType === "svg" && result.previewUrl && (
            // eslint-disable-next-line @next/next/no-img-element -- a blob: URL can't go through next/image's loader
            <img
              src={result.previewUrl}
              alt="Generated artwork"
              className="mx-auto max-h-72 w-auto cursor-zoom-in rounded-xl bg-white"
              onClick={() => setLightboxOpen(true)}
            />
          )}
          {result.previewType === "text" && result.textContent && (
            <div className="thin-scroll max-h-64 overflow-y-auto rounded-xl bg-white p-4 text-sm text-gray-700">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.textContent}</ReactMarkdown>
            </div>
          )}
          <div className="mt-3 flex justify-center">
            <button
              onClick={handleDownload}
              className="group flex items-center gap-1.5 rounded-full bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-500"
            >
              <AnimatedIcon icon={Download} className="h-4 w-4" strokeWidth={2.25} />
              Download
            </button>
          </div>
        </div>
      )}

      {lightboxOpen && result.status === "done" && result.previewUrl && result.previewType !== "text" && (
        <MediaLightbox
          open
          onClose={() => setLightboxOpen(false)}
          mediaType={result.previewType as "image" | "video" | "svg"}
          src={result.previewUrl}
          prompt={prompt}
          onDownload={handleDownload}
          onRegenerate={() => {
            setLightboxOpen(false);
            handleGenerate();
          }}
        />
      )}
    </section>
  );
}
