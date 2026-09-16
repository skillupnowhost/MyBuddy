"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Sparkles, Video as VideoIcon } from "lucide-react";
import AuthedVideo from "@/components/AuthedVideo";
import { LoadingGrid } from "@/components/LoadingIcons";
import MediaLightbox from "@/components/MediaLightbox";
import PageHeader from "@/components/PageHeader";
import PageBlobBackground from "@/components/PageBlobBackground";
import { isLoggedIn } from "@/lib/auth";
import {
  cancelVideoGenerationJob,
  createVideoGenerationJob,
  deleteVideoGenerationJob,
  listVideoGenerationJobs,
  pollVideoGenerationJob,
  type VideoGenerationParams,
} from "@/lib/videoGeneration";
import type { VideoGenerationJobItem } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  PENDING: "text-gray-500",
  RUNNING: "text-amber-500",
  COMPLETED: "text-emerald-600",
  FAILED: "text-red-500",
  CANCELLED: "text-gray-400",
};

const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

export default function VideoPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<VideoGenerationJobItem[]>([]);
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [width, setWidth] = useState(512);
  const [height, setHeight] = useState(512);
  const [numFrames, setNumFrames] = useState(16);
  const [steps, setSteps] = useState(4);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // A failed generation shows here briefly (with the error and a one-click retry) instead of
  // sitting in the gallery forever — the job row itself is deleted server-side the moment it's
  // known to have failed, see watchJob below. Same pattern as /image/page.tsx.
  const [failedNotice, setFailedNotice] = useState<{ message: string; job: VideoGenerationJobItem } | null>(null);
  const [lightbox, setLightbox] = useState<{ src: string; job: VideoGenerationJobItem } | null>(null);
  const unsubscribersRef = useRef<Map<string, () => void>>(new Map());
  const failedNoticeTimeoutRef = useRef<number | undefined>(undefined);

  function reportFailure(job: VideoGenerationJobItem) {
    deleteVideoGenerationJob(job.id).catch(() => {});
    setJobs((prev) => prev.filter((j) => j.id !== job.id));
    window.clearTimeout(failedNoticeTimeoutRef.current);
    setFailedNotice({ message: job.error_message || "Video generation failed.", job });
    failedNoticeTimeoutRef.current = window.setTimeout(() => setFailedNotice(null), 8000);
  }

  function watchJob(id: string) {
    if (unsubscribersRef.current.has(id)) return;
    const stop = pollVideoGenerationJob(id, (updated) => {
      if (updated.status === "FAILED") {
        unsubscribersRef.current.get(id)?.();
        unsubscribersRef.current.delete(id);
        reportFailure(updated);
        return;
      }
      setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
      if (TERMINAL_STATUSES.has(updated.status)) {
        unsubscribersRef.current.get(id)?.();
        unsubscribersRef.current.delete(id);
      }
    });
    unsubscribersRef.current.set(id, stop);
  }

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    listVideoGenerationJobs()
      .then((loaded) => {
        // Sweep any FAILED rows left over from before auto-cleanup existed, or from a session
        // that ended mid-generation, rather than showing them in the gallery.
        const stale = loaded.filter((j) => j.status === "FAILED");
        stale.forEach((j) => deleteVideoGenerationJob(j.id).catch(() => {}));
        const usable = loaded.filter((j) => j.status !== "FAILED");
        setJobs(usable);
        usable.filter((j) => !TERMINAL_STATUSES.has(j.status)).forEach((j) => watchJob(j.id));
      })
      .catch(() => setError("Could not load video generation jobs."));

    const unsubscribers = unsubscribersRef.current;
    return () => {
      unsubscribers.forEach((stop) => stop());
      unsubscribers.clear();
      window.clearTimeout(failedNoticeTimeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function submitJob(params: VideoGenerationParams) {
    const job = await createVideoGenerationJob(params);
    setJobs((prev) => [job, ...prev]);
    watchJob(job.id);
    return job;
  }

  async function handleGenerate() {
    const trimmed = prompt.trim();
    if (!trimmed || submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await submitJob({
        prompt: trimmed,
        negative_prompt: negativePrompt.trim() || undefined,
        width,
        height,
        num_frames: numFrames,
        steps,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start video generation.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRetry(job: VideoGenerationJobItem) {
    try {
      await submitJob({
        prompt: job.prompt,
        negative_prompt: job.negative_prompt ?? undefined,
        width: job.width,
        height: job.height,
        num_frames: job.num_frames,
        steps: job.steps,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start video generation.");
    }
  }

  async function handleCancel(id: string) {
    const updated = await cancelVideoGenerationJob(id);
    setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
    unsubscribersRef.current.get(id)?.();
    unsubscribersRef.current.delete(id);
  }

  return (
    <div className="relative min-h-screen bg-white px-6 py-8 text-gray-900">
      <PageBlobBackground />
      <div className="mx-auto max-w-3xl">
        <PageHeader
          icon={VideoIcon}
          title="MyBuddy Video"
          description="Generation runs as a separate process (see video/README.md). Without a GPU and the video
          generation environment installed, jobs correctly fail fast rather than pretending to generate anything."
        />

        {error && (
          <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
        )}

        {failedNotice && (
          <div className="mb-4 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">
            <AlertTriangle className="h-4 w-4 shrink-0" strokeWidth={2} />
            <span className="flex-1">{failedNotice.message}</span>
            <button
              onClick={() => {
                setFailedNotice(null);
                handleRetry(failedNotice.job);
              }}
              className="shrink-0 rounded-full px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100"
            >
              Retry
            </button>
          </div>
        )}

        <section className="mb-8 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md">
          <h2 className="mb-3 flex items-center gap-1.5 text-sm font-medium text-gray-700">
            <Sparkles className="h-4 w-4 text-indigo-500" strokeWidth={2} />
            Generate a video
          </h2>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="A small red robot waving hello, watercolor style"
            rows={3}
            className="mb-2 w-full resize-none rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-400 focus:bg-white"
          />
          <input
            value={negativePrompt}
            onChange={(e) => setNegativePrompt(e.target.value)}
            placeholder="Negative prompt (optional)"
            className="mb-2 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-400 focus:bg-white"
          />
          <div className="mb-3 flex flex-wrap gap-2">
            <label className="flex items-center gap-2 text-xs text-gray-500">
              Width
              <input
                type="number"
                value={width}
                onChange={(e) => setWidth(Number(e.target.value))}
                className="w-20 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-sm text-gray-900"
              />
            </label>
            <label className="flex items-center gap-2 text-xs text-gray-500">
              Height
              <input
                type="number"
                value={height}
                onChange={(e) => setHeight(Number(e.target.value))}
                className="w-20 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-sm text-gray-900"
              />
            </label>
            <label className="flex items-center gap-2 text-xs text-gray-500">
              Frames
              <input
                type="number"
                value={numFrames}
                onChange={(e) => setNumFrames(Number(e.target.value))}
                className="w-16 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-sm text-gray-900"
              />
            </label>
            <label className="flex items-center gap-2 text-xs text-gray-500">
              Steps
              <input
                type="number"
                value={steps}
                onChange={(e) => setSteps(Number(e.target.value))}
                className="w-16 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-sm text-gray-900"
              />
            </label>
          </div>
          <button
            onClick={handleGenerate}
            disabled={!prompt.trim() || submitting}
            className="rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:from-indigo-500 hover:to-violet-500 hover:shadow-md disabled:opacity-40 disabled:shadow-none"
          >
            {submitting ? "Starting..." : "Generate"}
          </button>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md">
          <h2 className="mb-3 text-sm font-medium text-gray-700">Your generations</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="group rounded-xl border border-gray-200 p-2 transition hover:border-indigo-300 hover:shadow-sm"
              >
                {job.video_id ? (
                  <AuthedVideo
                    videoId={job.video_id}
                    className="mb-2 h-32 w-full rounded-lg object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                    downloadFilename={`${job.prompt.slice(0, 40).replace(/[^a-z0-9]+/gi, "-") || "mybuddy-video"}.mp4`}
                    onOpen={(src) => setLightbox({ src, job })}
                  />
                ) : (
                  // FAILED jobs never reach this list — they're auto-removed the moment the
                  // poll sees them (see reportFailure) — so anything without a video_id here
                  // is still genuinely in flight.
                  <div className="mb-2 flex h-32 w-full items-center justify-center rounded-lg bg-gray-100 text-xs text-gray-400">
                    <LoadingGrid className="h-10 w-10" />
                  </div>
                )}
                <p className="truncate text-xs text-gray-700" title={job.prompt}>
                  {job.prompt}
                </p>
                <div className="mt-1 flex items-center justify-between">
                  <span className={`text-xs ${STATUS_COLORS[job.status]}`}>{job.status}</span>
                  {(job.status === "PENDING" || job.status === "RUNNING") && (
                    <button onClick={() => handleCancel(job.id)} className="text-xs text-gray-400 hover:text-red-500">
                      cancel
                    </button>
                  )}
                </div>
              </div>
            ))}
            {jobs.length === 0 && (
              <p className="col-span-full py-6 text-center text-sm text-gray-400">No generations yet.</p>
            )}
          </div>
        </section>
      </div>

      {lightbox && (
        <MediaLightbox
          open
          onClose={() => setLightbox(null)}
          mediaType="video"
          src={lightbox.src}
          prompt={lightbox.job.prompt}
          onDownload={() => {
            const link = document.createElement("a");
            link.href = lightbox.src;
            link.download = `${lightbox.job.prompt.slice(0, 40).replace(/[^a-z0-9]+/gi, "-") || "mybuddy-video"}.mp4`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
          }}
          onRegenerate={() => {
            setLightbox(null);
            handleRetry(lightbox.job);
          }}
        />
      )}
    </div>
  );
}
