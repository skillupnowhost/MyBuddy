"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import AuthedImage from "@/components/AuthedImage";
import MaskCanvas, { type MaskCanvasHandle } from "@/components/MaskCanvas";
import { isLoggedIn } from "@/lib/auth";
import { createEditJob, listEditJobs, pollEditJob } from "@/lib/imageEdit";
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
  const maskRef = useRef<MaskCanvasHandle>(null);
  const unsubscribersRef = useRef<Map<string, () => void>>(new Map());
  const sourceInputRef = useRef<HTMLInputElement>(null);

  function watchJob(id: string) {
    if (unsubscribersRef.current.has(id)) return;
    const stop = pollEditJob(id, (updated) => {
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
        setJobs(loaded);
        loaded.filter((j) => !TERMINAL_STATUSES.has(j.status)).forEach((j) => watchJob(j.id));
      })
      .catch(() => setError("Could not load image edit jobs."));

    const unsubscribers = unsubscribersRef.current;
    return () => {
      unsubscribers.forEach((stop) => stop());
      unsubscribers.clear();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

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

  const canSubmit =
    !!sourceImage &&
    !submitting &&
    (operation === "REMOVE_BACKGROUND" ||
      (operation === "INPAINT" && prompt.trim().length > 0) ||
      (operation === "OUTPAINT" && prompt.trim().length > 0 && (padTop || padBottom || padLeft || padRight) > 0));

  return (
    <div className="min-h-screen bg-[#f4f5f9] px-6 py-8 text-gray-900">
      <div className="mx-auto max-w-3xl">
        <div className="mb-2 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">MyBuddy Image Edit</h1>
          <Link href="/chat" className="text-sm text-indigo-600 hover:underline">
            &larr; Back to chat
          </Link>
        </div>
        <p className="mb-6 text-sm text-gray-400">
          Runs as a separate process (see <code>imagegen/README.md</code>). Background removal is fast even on
          CPU; inpaint/outpaint go through a full diffusion pipeline and are much slower without a GPU.
        </p>

        {error && <p className="mb-4 text-sm text-red-500">{error}</p>}

        <section className="mb-8 rounded-xl border border-gray-200 bg-white p-4">
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
                      operation === op ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
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
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
              >
                {submitting ? "Starting..." : "Run"}
              </button>
            </>
          )}
        </section>

        <section className="rounded-xl border border-gray-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-medium text-gray-700">Your edits</h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {jobs.map((job) => (
              <div key={job.id} className="rounded-lg border border-gray-200 p-2">
                {job.result_image_id ? (
                  <AuthedImage imageId={job.result_image_id} className="mb-2 h-32 w-full rounded-lg object-cover" />
                ) : (
                  <div className="mb-2 flex h-32 w-full items-center justify-center rounded-lg bg-gray-100 text-xs text-gray-400">
                    {job.status === "FAILED" ? "failed" : "working..."}
                  </div>
                )}
                <p className="truncate text-xs text-gray-700">{job.operation}</p>
                <div className="mt-1 flex items-center justify-between">
                  <span className={`text-xs ${STATUS_COLORS[job.status]}`}>{job.status}</span>
                </div>
                {job.error_message && (
                  <p className="mt-1 truncate text-xs text-red-500/80" title={job.error_message}>
                    {job.error_message}
                  </p>
                )}
              </div>
            ))}
            {jobs.length === 0 && <p className="col-span-full py-6 text-center text-sm text-gray-400">No edits yet.</p>}
          </div>
        </section>
      </div>
    </div>
  );
}
