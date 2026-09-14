"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getCurrentUser } from "@/lib/admin";
import { isLoggedIn } from "@/lib/auth";
import {
  cancelTrainingJob,
  createTrainingJob,
  deleteDataset,
  listDatasets,
  listRegisteredModels,
  listTrainingJobs,
  promoteModel,
  uploadDataset,
} from "@/lib/training";
import type { DatasetItem, ModelStatus, RegisteredModelItem, TrainingJobItem } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  UPLOADED: "text-white/50",
  VALIDATED: "text-emerald-400",
  INVALID: "text-red-400",
  PENDING: "text-white/50",
  RUNNING: "text-amber-400",
  COMPLETED: "text-emerald-400",
  FAILED: "text-red-400",
  CANCELLED: "text-white/40",
};

const PROMOTION_OPTIONS: ModelStatus[] = ["EXPERIMENTAL", "CANARY", "STAGING", "PRODUCTION", "ARCHIVED", "REJECTED"];

export default function FinetunePage() {
  const router = useRouter();
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [jobs, setJobs] = useState<TrainingJobItem[]>([]);
  const [models, setModels] = useState<RegisteredModelItem[]>([]);
  const [isAdmin, setIsAdmin] = useState(false);
  const [baseModel, setBaseModel] = useState("meta-llama/Llama-3.2-1B");
  const [selectedDataset, setSelectedDataset] = useState("");
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    try {
      const [ds, jb, md] = await Promise.all([listDatasets(), listTrainingJobs(), listRegisteredModels()]);
      setDatasets(ds);
      setJobs(jb);
      setModels(md);
    } catch {
      setError("Could not load fine-tuning data.");
    }
  }

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    getCurrentUser()
      .then((user) => setIsAdmin(user.role === "ADMIN"))
      .catch(() => {});
    refresh();
    const interval = setInterval(refresh, 4000);
    return () => clearInterval(interval);
  }, [router]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const dataset = await uploadDataset(file);
      setDatasets((prev) => [dataset, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleStartTraining() {
    if (!selectedDataset || !baseModel.trim()) return;
    setError(null);
    try {
      const job = await createTrainingJob(selectedDataset, baseModel.trim());
      setJobs((prev) => [job, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start training job.");
    }
  }

  async function handleCancel(id: string) {
    const updated = await cancelTrainingJob(id);
    setJobs((prev) => prev.map((j) => (j.id === updated.id ? updated : j)));
  }

  async function handlePromote(id: string, status: ModelStatus) {
    const updated = await promoteModel(id, status);
    setModels((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
  }

  const validatedDatasets = datasets.filter((d) => d.status === "VALIDATED");

  return (
    <div className="min-h-screen bg-[#0f1115] px-6 py-8 text-white">
      <div className="mx-auto max-w-4xl">
        <div className="mb-2 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Fine-tuning</h1>
          <Link href="/chat" className="text-sm text-blue-400 hover:underline">
            &larr; Back to chat
          </Link>
        </div>
        <p className="mb-6 text-sm text-white/40">
          Training runs as a separate process (see <code>training/README.md</code>). On a machine without a GPU and
          the training environment installed, jobs will correctly fail fast with a clear message rather than
          pretending to train — that's expected here.
        </p>

        {error && <p className="mb-4 text-sm text-red-400">{error}</p>}

        <section className="mb-8 rounded-xl border border-white/10 bg-[#161922] p-4">
          <h2 className="mb-3 text-sm font-medium text-white/70">Datasets</h2>
          <input ref={fileInputRef} type="file" accept=".jsonl,.json" onChange={handleUpload} className="hidden" />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="mb-3 w-full rounded-lg border border-dashed border-white/20 py-2 text-sm text-white/70 hover:border-blue-500 hover:text-white"
          >
            + Upload a .jsonl instruction dataset
          </button>
          <div className="space-y-1">
            {datasets.map((d) => (
              <div key={d.id} className="flex items-center justify-between rounded-lg px-2 py-2 text-sm hover:bg-white/5">
                <div>
                  <p className="text-white/90">{d.filename}</p>
                  <p className="text-xs text-white/40">
                    {d.num_examples ?? 0} examples ·{" "}
                    <span className={STATUS_COLORS[d.status]}>{d.status}</span>
                    {d.error_message ? `: ${d.error_message}` : ""}
                  </p>
                </div>
                <button
                  onClick={() => deleteDataset(d.id).then(() => setDatasets((prev) => prev.filter((x) => x.id !== d.id)))}
                  className="text-white/40 hover:text-red-400"
                >
                  &times;
                </button>
              </div>
            ))}
            {datasets.length === 0 && <p className="py-4 text-center text-sm text-white/40">No datasets yet.</p>}
          </div>
        </section>

        <section className="mb-8 rounded-xl border border-white/10 bg-[#161922] p-4">
          <h2 className="mb-3 text-sm font-medium text-white/70">Start a training job</h2>
          <div className="flex flex-wrap gap-2">
            <select
              value={selectedDataset}
              onChange={(e) => setSelectedDataset(e.target.value)}
              className="rounded-lg border border-white/10 bg-[#0f1115] px-3 py-2 text-sm text-white"
            >
              <option value="">Select a validated dataset...</option>
              {validatedDatasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.filename}
                </option>
              ))}
            </select>
            <input
              value={baseModel}
              onChange={(e) => setBaseModel(e.target.value)}
              placeholder="Base model (Hugging Face id)"
              className="flex-1 rounded-lg border border-white/10 bg-[#0f1115] px-3 py-2 text-sm text-white"
            />
            <button
              onClick={handleStartTraining}
              disabled={!selectedDataset || !baseModel.trim()}
              className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40"
            >
              Start
            </button>
          </div>

          <div className="mt-4 space-y-1">
            {jobs.map((job) => (
              <div key={job.id} className="rounded-lg px-2 py-2 text-sm hover:bg-white/5">
                <div className="flex items-center justify-between">
                  <p className="text-white/90">{job.base_model}</p>
                  <div className="flex items-center gap-2">
                    <span className={STATUS_COLORS[job.status]}>{job.status}</span>
                    {(job.status === "PENDING" || job.status === "RUNNING") && (
                      <button onClick={() => handleCancel(job.id)} className="text-xs text-white/40 hover:text-red-400">
                        cancel
                      </button>
                    )}
                  </div>
                </div>
                {job.error_message && <p className="text-xs text-red-400/80">{job.error_message}</p>}
                {job.eval_metrics && (
                  <p className="text-xs text-white/40">
                    {Object.entries(job.eval_metrics)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(" · ")}
                  </p>
                )}
              </div>
            ))}
            {jobs.length === 0 && <p className="py-4 text-center text-sm text-white/40">No training jobs yet.</p>}
          </div>
        </section>

        <section className="rounded-xl border border-white/10 bg-[#161922] p-4">
          <h2 className="mb-3 text-sm font-medium text-white/70">Model registry</h2>
          <div className="space-y-1">
            {models.map((model) => (
              <div key={model.id} className="flex items-center justify-between rounded-lg px-2 py-2 text-sm hover:bg-white/5">
                <div>
                  <p className="text-white/90">
                    {model.name} <span className="text-white/40">({model.base_model})</span>
                  </p>
                  <p className="text-xs text-white/40">
                    {model.status}
                    {model.eval_score !== null ? ` · eval: ${model.eval_score}` : ""}
                  </p>
                </div>
                {isAdmin && (
                  <select
                    value={model.status}
                    onChange={(e) => handlePromote(model.id, e.target.value as ModelStatus)}
                    className="rounded-lg border border-white/10 bg-[#0f1115] px-2 py-1 text-xs text-white"
                  >
                    {PROMOTION_OPTIONS.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            ))}
            {models.length === 0 && <p className="py-4 text-center text-sm text-white/40">No registered models yet.</p>}
          </div>
        </section>
      </div>
    </div>
  );
}
