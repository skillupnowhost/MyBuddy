"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, Wand2 } from "lucide-react";
import AuthedImage from "@/components/AuthedImage";
import { LoadingGrid } from "@/components/LoadingIcons";
import MaskCanvas, { type MaskCanvasHandle } from "@/components/MaskCanvas";
import MediaLightbox from "@/components/MediaLightbox";
import PageHeader from "@/components/PageHeader";
import PageBlobBackground from "@/components/PageBlobBackground";
import { isLoggedIn } from "@/lib/auth";
import { createEditJob, deleteEditJob, listEditJobs, pollEditJob } from "@/lib/imageEdit";
import { getImageBlobUrl, uploadImage } from "@/lib/images";
import type { ImageEditJobItem, ImageEditOperation, ImageItem } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  PENDING: "text-gray-500",
  RUNNING: "text-amber-500",
  COMPLETED: "text-emerald-600",
  FAILED: "text-red-500",
  CANCELLED: "text-gray-400",
};

const TERMINAL_STATUSES = new Set(["COMPLETED", "FAILED", "CANCELLED"]);

export default function ImageEditPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<ImageEditJobItem[]>([]);
  const [sourceImage, setSourceImage] = useState<ImageItem | null>(null);
  const [sourceBlobUrl, setSourceBlobUrl] = useState<string | null>(null);
  const [operation, setOperation] = useState<ImageEditOperation>("INPAINT");
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [steps, setSteps] = useState(20);
  const [brushSize, setBrushSize] = useState(24);
  const [padTop, setPadTop] = useState(0);
  const [padBottom, setPadBottom] = useState(0);
  const [padLeft, setPadLeft] = useState(0);
  const [padRight, setPadRight] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // A failed edit shows here briefly (with the error and a one-click retry) instead of sitting
  // in the gallery forever — the job row itself is deleted server-side the moment it's known to
  // have failed, see watchJob below. Same pattern as /image/page.tsx and /video/page.tsx.
  const [failedNotice, setFailedNotice] = useState<{ message: string; job: ImageEditJobItem } | null>(null);
  const [lightbox, setLightbox] = useState<{ src: string; job: ImageEditJobItem } | null>(null);
  const maskRef = useRef<MaskCanvasHandle>(null);
  const unsubscribersRef = useRef<Map<string, () => void>>(new Map());
  const sourceInputRef = useRef<HTMLInputElement>(null);
  const failedNoticeTimeoutRef = useRef<number | undefined>(undefined);

  function reportFailure(job: ImageEditJobItem) {
    deleteEditJob(job.id).catch(() => {});
    setJobs((prev) => prev.filter((j) => j.id !== job.id));
    window.clearTimeout(failedNoticeTimeoutRef.current);
    setFailedNotice({ message: job.error_message || "Image edit failed.", job });
    failedNoticeTimeoutRef.current = window.setTimeout(() => setFailedNotice(null), 8000);
  }

  function watchJob(id: string) {
    if (unsubscribersRef.current.has(id)) return;
    const stop = pollEditJob(id, (updated) => {
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
    listEditJobs()
      .then((loaded) => {
        const stale = loaded.filter((j) => j.status === "FAILED");
        stale.forEach((j) => deleteEditJob(j.id).catch(() => {}));
        const usable = loaded.filter((j) => j.status !== "FAILED");
        setJobs(usable);
        usable.filter((j) => !TERMINAL_STATUSES.has(j.status)).forEach((j) => watchJob(j.id));
      })
      .catch(() => setError("Could not load image edit jobs."));

    const unsubscribers = unsubscribersRef.current;
    return () => {
      unsubscribers.forEach((stop) => stop());
      unsubscribers.clear();
      window.clearTimeout(failedNoticeTimeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  // Deep link from another surface's "Edit image" action (e.g. /image's lightbox) — preload
  // the source instead of requiring the user to download and re-upload the same file. Read
  // straight from window.location rather than next/navigation's useSearchParams, which would
  // force this client page into a Suspense boundary it (and no other page here) currently has.
  useEffect(() => {
    const sourceId = new URLSearchParams(window.location.search).get("source");
    if (!sourceId || sourceImage) return;
    getImageBlobUrl(sourceId)
      .then((url) => {
        setSourceImage({ id: sourceId, content_type: "image/png", size_bytes: 0, created_at: new Date().toISOString() });
        setSourceBlobUrl(url);
      })
      .catch(() => setError("Could not load the source image."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleUploadSource(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    try {
      const image = await uploadImage(file);
      setSourceImage(image);
      const url = await getImageBlobUrl(image.id);
      setSourceBlobUrl(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Image upload failed.");
    } finally {
      if (sourceInputRef.current) sourceInputRef.current.value = "";
    }
  }

  async function handleSubmit() {
    if (!sourceImage || submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      let maskImageId: string | undefined;
      if (operation === "INPAINT") {
        if (!maskRef.current) throw new Error("Mask canvas not ready.");
        const blob = await maskRef.current.exportMaskBlob();
        const maskFile = new File([blob], "mask.png", { type: "image/png" });
        const maskImage = await uploadImage(maskFile);
        maskImageId = maskImage.id;
      }

      const job = await createEditJob({
        operation,
        source_image_id: sourceImage.id,
        mask_image_id: maskImageId,
        prompt: operation !== "REMOVE_BACKGROUND" ? prompt.trim() || undefined : undefined,
        negative_prompt: operation !== "REMOVE_BACKGROUND" ? negativePrompt.trim() || undefined : undefined,
        steps: operation !== "REMOVE_BACKGROUND" ? steps : undefined,
        outpaint_top: operation === "OUTPAINT" ? padTop : undefined,
        outpaint_bottom: operation === "OUTPAINT" ? padBottom : undefined,
        outpaint_left: operation === "OUTPAINT" ? padLeft : undefined,
        outpaint_right: operation === "OUTPAINT" ? padRight : undefined,
      });
      setJobs((prev) => [job, ...prev]);
      watchJob(job.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start image edit job.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRetry(job: ImageEditJobItem) {
    if (!job.source_image_id) return;
    try {
      const retried = await createEditJob({
        operation: job.operation,
        source_image_id: job.source_image_id,
        mask_image_id: job.mask_image_id ?? undefined,
        prompt: job.prompt ?? undefined,
        negative_prompt: job.negative_prompt ?? undefined,
        steps: job.steps ?? undefined,
        outpaint_top: job.params.outpaint_top,
        outpaint_bottom: job.params.outpaint_bottom,
        outpaint_left: job.params.outpaint_left,
        outpaint_right: job.params.outpaint_right,
      });
      setJobs((prev) => [retried, ...prev]);
      watchJob(retried.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start image edit job.");
    }
  }

  const canSubmit =
    !!sourceImage &&
    !submitting &&
    (operation === "REMOVE_BACKGROUND" ||
      (operation === "INPAINT" && prompt.trim().length > 0) ||
      (operation === "OUTPAINT" && prompt.trim().length > 0 && (padTop || padBottom || padLeft || padRight) > 0));

  return (
    <div className="relative min-h-screen bg-white px-6 py-8 text-gray-900">
      <PageBlobBackground />
      <div className="mx-auto max-w-3xl">
        <PageHeader
          icon={Wand2}
          title="MyBuddy Image Edit"
          description="Runs as a separate process (see imagegen/README.md). Background removal is fast even on CPU;
          inpaint/outpaint go through a full diffusion pipeline and are much slower without a GPU."
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
          <h2 className="mb-3 text-sm font-medium text-gray-700">1. Upload a source image</h2>
          <input ref={sourceInputRef} type="file" accept="image/*" onChange={handleUploadSource} className="hidden" />
          <button
            onClick={() => sourceInputRef.current?.click()}
            className="mb-3 w-full rounded-lg border border-dashed border-gray-300 py-2 text-sm text-gray-500 hover:border-indigo-400 hover:text-gray-900"
          >
            {sourceImage ? "Replace image" : "+ Upload an image"}
          </button>

          {sourceImage && (
            <>
              <div className="mb-3 flex gap-2">
                {(["INPAINT", "OUTPAINT", "REMOVE_BACKGROUND"] as ImageEditOperation[]).map((op) => (
                  <button
                    key={op}
                    onClick={() => setOperation(op)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                      operation === op ? "bg-gradient-to-r from-indigo-600 to-violet-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                    }`}
                  >
                    {op === "INPAINT" ? "Inpaint" : op === "OUTPAINT" ? "Outpaint" : "Remove background"}
                  </button>
                ))}
              </div>

              {operation === "INPAINT" && sourceBlobUrl && (
                <div className="mb-3">
                  <p className="mb-2 text-xs text-gray-500">
                    Paint over the area you want MyBuddy to regenerate.
                  </p>
                  <MaskCanvas ref={maskRef} imageBlobUrl={sourceBlobUrl} brushSize={brushSize} />
                  <div className="mt-2 flex items-center gap-3">
                    <label className="flex items-center gap-2 text-xs text-gray-500">
                      Brush size
                      <input
                        type="range"
                        min={5}
                        max={80}
                        value={brushSize}
                        onChange={(e) => setBrushSize(Number(e.target.value))}
                      />
                    </label>
                    <button
                      onClick={() => maskRef.current?.clear()}
                      className="text-xs text-gray-400 hover:text-gray-900"
                    >
                      Clear mask
                    </button>
                  </div>
                </div>
              )}

              {operation !== "REMOVE_BACKGROUND" && (
                <>
                  <textarea
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    placeholder="Prompt"
                    rows={2}
                    className="mb-2 w-full resize-none rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-400 focus:bg-white"
                  />
                  <input
                    value={negativePrompt}
                    onChange={(e) => setNegativePrompt(e.target.value)}
                    placeholder="Negative prompt (optional)"
                    className="mb-2 w-full rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900 outline-none focus:border-indigo-400 focus:bg-white"
                  />
                  <label className="mb-3 flex w-fit items-center gap-2 text-xs text-gray-500">
                    Steps
                    <input
                      type="number"
                      value={steps}
                      onChange={(e) => setSteps(Number(e.target.value))}
                      className="w-16 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-sm text-gray-900"
                    />
                  </label>
                </>
              )}

              {operation === "OUTPAINT" && (
                <div className="mb-3 flex flex-wrap gap-2">
                  {(
                    [
                      ["Top", padTop, setPadTop],
                      ["Bottom", padBottom, setPadBottom],
                      ["Left", padLeft, setPadLeft],
                      ["Right", padRight, setPadRight],
                    ] as [string, number, (n: number) => void][]
                  ).map(([label, value, setValue]) => (
                    <label key={label} className="flex items-center gap-2 text-xs text-gray-500">
                      {label}
                      <input
                        type="number"
                        value={value}
                        onChange={(e) => setValue(Number(e.target.value))}
                        className="w-16 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-sm text-gray-900"
                      />
                    </label>
                  ))}
                </div>
              )}

              <button
                onClick={handleSubmit}
                disabled={!canSubmit}
                className="rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2 text-sm font-medium text-white hover:from-indigo-500 hover:to-violet-500 disabled:opacity-40"
              >
                {submitting ? "Starting..." : "Run"}
              </button>
            </>
          )}
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md">
          <h2 className="mb-3 text-sm font-medium text-gray-700">Your edits</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="group rounded-xl border border-gray-200 p-2 transition hover:border-indigo-300 hover:shadow-sm"
              >
                {job.result_image_id ? (
                  <AuthedImage
                    imageId={job.result_image_id}
                    className="mb-2 h-32 w-full rounded-lg object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                    downloadable
                    downloadFilename="mybuddy-edited-image.png"
                    onOpen={(src) => setLightbox({ src, job })}
                  />
                ) : (
                  // FAILED jobs never reach this list — they're auto-removed the moment the
                  // poll sees them (see reportFailure) — so anything without a result_image_id
                  // here is still genuinely in flight.
                  <div className="mb-2 flex h-32 w-full items-center justify-center rounded-lg bg-gray-100 text-xs text-gray-400">
                    <LoadingGrid className="h-10 w-10" />
                  </div>
                )}
                <p className="truncate text-xs text-gray-700">{job.operation}</p>
                <div className="mt-1 flex items-center justify-between">
                  <span className={`text-xs ${STATUS_COLORS[job.status]}`}>{job.status}</span>
                </div>
              </div>
            ))}
            {jobs.length === 0 && <p className="col-span-full py-6 text-center text-sm text-gray-400">No edits yet.</p>}
          </div>
        </section>
      </div>

      {lightbox && (
        <MediaLightbox
          open
          onClose={() => setLightbox(null)}
          mediaType="image"
          src={lightbox.src}
          prompt={lightbox.job.prompt}
          onDownload={() => {
            const link = document.createElement("a");
            link.href = lightbox.src;
            link.download = "mybuddy-edited-image.png";
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
