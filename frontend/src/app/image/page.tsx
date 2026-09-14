"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AuthedImage from "@/components/AuthedImage";
import { isLoggedIn } from "@/lib/auth";
import { cancelGenerationJob, createGenerationJob, listGenerationJobs, pollGenerationJob } from "@/lib/imageGeneration";
import type { ImageGenerationJobItem } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  PENDING: "text-white/50",
  RUNNING: "text-amber-400",
  COMPLETED: "text-emerald-400",
  FAILED: "text-red-400",
  CANCELLED: "text-white/40",
};

const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

export default function ImagePage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<ImageGenerationJobItem[]>([]);
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [width, setWidth] = useState(512);
  const [height, setHeight] = useState(512);
  const [steps, setSteps] = useState(4);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const unsubscribersRef = useRef<Map<string, () => void>>(new Map());

  function watchJob(id: string) {
    if (unsubscribersRef.current.has(id)) return;
    const stop = pollGenerationJob(id, (updated) => {
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
    listGenerationJobs()
      .then((loaded) => {
        setJobs(loaded);
        loaded.filter((j) => !TERMINAL_STATUSES.has(j.status)).forEach((j) => watchJob(j.id));
      })
      .catch(() => setError("Could not load image generation jobs."));

    const unsubscribers = unsubscribersRef.current;
    return () => {
      unsubscribers.forEach((stop) => stop());
      unsubscribers.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function handleGenerate() {
    const trimmed = prompt.trim();
    if (!trimmed || submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      const job = await createGenerationJob({
        prompt: trimmed,
        negative_prompt: negativePrompt.trim() || undefined,
        width,
        height,
        steps,
      });
      setJobs((prev) => [job, ...prev]);
      watchJob(job.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start image generation.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancel(id: string) {
    const updated = await cancelGenerationJob(id);
    setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
    unsubscribersRef.current.get(id)?.();
    unsubscribersRef.current.delete(id);
  }

  return (
    <div className="min-h-screen bg-[#0f1115] px-6 py-8 text-white">
      <div className="mx-auto max-w-3xl">
        <div className="mb-2 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">MyBuddy Image</h1>
          <Link href="/chat" className="text-sm text-blue-400 hover:underline">
            &larr; Back to chat
          </Link>
        </div>
        <p className="mb-6 text-sm text-white/40">
          Generation runs as a separate process (see <code>imagegen/README.md</code>). On a machine without a GPU
          and the image generation environment installed, jobs will correctly fail fast with a clear message rather
          than pretending to generate anything — that&apos;s expected here.
        </p>

        {error && <p className="mb-4 text-sm text-red-400">{error}</p>}

        <section className="mb-8 rounded-xl border border-white/10 bg-[#161922] p-4">
          <h2 className="mb-3 text-sm font-medium text-white/70">Generate an image</h2>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="A small red robot reading a book, watercolor style"
            rows={3}
            className="mb-2 w-full resize-none rounded-lg border border-white/10 bg-[#0f1115] px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
          />
          <input
            value={negativePrompt}
            onChange={(e) => setNegativePrompt(e.target.value)}
            placeholder="Negative prompt (optional)"
            className="mb-2 w-full rounded-lg border border-white/10 bg-[#0f1115] px-3 py-2 text-sm text-white outline-none focus:border-blue-500"
          />
          <div className="mb-3 flex flex-wrap gap-2">
            <label className="flex items-center gap-2 text-xs text-white/50">
              Width
              <input
                type="number"
                value={width}
                onChange={(e) => setWidth(Number(e.target.value))}
                className="w-20 rounded-lg border border-white/10 bg-[#0f1115] px-2 py-1 text-sm text-white"
              />
            </label>
            <label className="flex items-center gap-2 text-xs text-white/50">
              Height
              <input
                type="number"
                value={height}
                onChange={(e) => setHeight(Number(e.target.value))}
                className="w-20 rounded-lg border border-white/10 bg-[#0f1115] px-2 py-1 text-sm text-white"
              />
            </label>
            <label className="flex items-center gap-2 text-xs text-white/50">
              Steps
              <input
                type="number"
                value={steps}
                onChange={(e) => setSteps(Number(e.target.value))}
                className="w-16 rounded-lg border border-white/10 bg-[#0f1115] px-2 py-1 text-sm text-white"
              />
            </label>
          </div>
          <button
            onClick={handleGenerate}
            disabled={!prompt.trim() || submitting}
            className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
          >
            {submitting ? "Starting..." : "Generate"}
          </button>
        </section>

        <section className="rounded-xl border border-white/10 bg-[#161922] p-4">
          <h2 className="mb-3 text-sm font-medium text-white/70">Your generations</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {jobs.map((job) => (
              <div key={job.id} className="rounded-lg border border-white/10 p-2">
                {job.image_id ? (
                  <AuthedImage imageId={job.image_id} className="mb-2 h-32 w-full rounded-lg object-cover" />
                ) : (
                  <div className="mb-2 flex h-32 w-full items-center justify-center rounded-lg bg-white/5 text-xs text-white/30">
                    {job.status === "FAILED" ? "failed" : "generating..."}
                  </div>
                )}
                <p className="truncate text-xs text-white/70" title={job.prompt}>
                  {job.prompt}
                </p>
                <div className="mt-1 flex items-center justify-between">
                  <span className={`text-xs ${STATUS_COLORS[job.status]}`}>{job.status}</span>
                  {(job.status === "PENDING" || job.status === "RUNNING") && (
                    <button onClick={() => handleCancel(job.id)} className="text-xs text-white/40 hover:text-red-400">
                      cancel
                    </button>
                  )}
                </div>
                {job.error_message && (
                  <p className="mt-1 truncate text-xs text-red-400/80" title={job.error_message}>
                    {job.error_message}
                  </p>
                )}
              </div>
            ))}
            {jobs.length === 0 && (
              <p className="col-span-full py-6 text-center text-sm text-white/40">No generations yet.</p>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
