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
  discoverModels,
  listDatasets,
  listRegisteredModels,
  listTrainingJobs,
  promoteModel,
  runBenchmark,
  uploadDataset,
} from "@/lib/training";
import type { DatasetItem, ModelBenchmarkResultItem, ModelStatus, RegisteredModelItem, TrainingJobItem } from "@/lib/types";

const STATUS_COLORS: Record<string, string> = {
  UPLOADED: "text-gray-500",
  VALIDATED: "text-emerald-600",
  INVALID: "text-red-500",
  PENDING: "text-gray-500",
  RUNNING: "text-amber-500",
  COMPLETED: "text-emerald-600",
  FAILED: "text-red-500",
  CANCELLED: "text-gray-400",
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
  const [benchmarking, setBenchmarking] = useState<string | null>(null);
  const [benchmarkResults, setBenchmarkResults] = useState<Record<string, ModelBenchmarkResultItem[]>>({});
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

  async function handleDiscover() {
    setError(null);
    try {
      const found = await discoverModels();
      if (found.length === 0) return;
      setModels((prev) => [...found, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not discover local models.");
    }
  }

  async function handleBenchmark(id: string) {
    setError(null);
    setBenchmarking(id);
    try {
      const run = await runBenchmark(id);
      setBenchmarkResults((prev) => ({ ...prev, [id]: run.results }));
      setModels((prev) => prev.map((m) => (m.id === id ? { ...m, eval_score: run.eval_score } : m)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not run benchmark.");
    } finally {
      setBenchmarking(null);
    }
  }

  const validatedDatasets = datasets.filter((d) => d.status === "VALIDATED");

  return (
    <div className="min-h-screen bg-white px-6 py-8 text-gray-900">
      <div className="mx-auto max-w-4xl">
        <div className="mb-2 flex items-center justify-between">
          <h1 className="text-2xl font-semibold">Fine-tuning</h1>
          <Link href="/chat" className="text-sm text-indigo-600 hover:underline">
            &larr; Back to chat
          </Link>
        </div>
        <p className="mb-6 text-sm text-gray-400">
          Training runs as a separate process (see <code>training/README.md</code>). On a machine without a GPU and
          the training environment installed, jobs will correctly fail fast with a clear message rather than
          pretending to train — that's expected here.
        </p>

        {error && <p className="mb-4 text-sm text-red-500">{error}</p>}

        <section className="mb-8 rounded-xl border border-gray-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-medium text-gray-700">Datasets</h2>
          <input ref={fileInputRef} type="file" accept=".jsonl,.json" onChange={handleUpload} className="hidden" />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="mb-3 w-full rounded-lg border border-dashed border-gray-300 py-2 text-sm text-gray-500 hover:border-indigo-400 hover:text-gray-900"
          >
            + Upload a .jsonl instruction dataset
          </button>
          <div className="space-y-1">
            {datasets.map((d) => (
              <div key={d.id} className="flex items-center justify-between rounded-lg px-2 py-2 text-sm hover:bg-gray-100">
                <div>
                  <p className="text-gray-800">{d.filename}</p>
                  <p className="text-xs text-gray-400">
                    {d.num_examples ?? 0} examples ·{" "}
                    <span className={STATUS_COLORS[d.status]}>{d.status}</span>
                    {d.error_message ? `: ${d.error_message}` : ""}
                  </p>
                </div>
                <button
                  onClick={() => deleteDataset(d.id).then(() => setDatasets((prev) => prev.filter((x) => x.id !== d.id)))}
                  className="text-gray-400 hover:text-red-500"
                >
                  &times;
                </button>
              </div>
            ))}
            {datasets.length === 0 && <p className="py-4 text-center text-sm text-gray-400">No datasets yet.</p>}
          </div>
        </section>

        <section className="mb-8 rounded-xl border border-gray-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-medium text-gray-700">Start a training job</h2>
          <div className="flex flex-wrap gap-2">
            <select
              value={selectedDataset}
              onChange={(e) => setSelectedDataset(e.target.value)}
              className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900"
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
              className="flex-1 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900"
            />
            <button
              onClick={handleStartTraining}
              disabled={!selectedDataset || !baseModel.trim()}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
            >
              Start
            </button>
          </div>

          <div className="mt-4 space-y-1">
            {jobs.map((job) => (
              <div key={job.id} className="rounded-lg px-2 py-2 text-sm hover:bg-gray-100">
                <div className="flex items-center justify-between">
                  <p className="text-gray-800">{job.base_model}</p>
                  <div className="flex items-center gap-2">
                    <span className={STATUS_COLORS[job.status]}>{job.status}</span>
                    {(job.status === "PENDING" || job.status === "RUNNING") && (
                      <button onClick={() => handleCancel(job.id)} className="text-xs text-gray-400 hover:text-red-500">
                        cancel
                      </button>
                    )}
                  </div>
                </div>
                {job.error_message && <p className="text-xs text-red-500/80">{job.error_message}</p>}
                {job.eval_metrics && (
                  <p className="text-xs text-gray-400">
                    {Object.entries(job.eval_metrics)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(" · ")}
                  </p>
                )}
              </div>
            ))}
            {jobs.length === 0 && <p className="py-4 text-center text-sm text-gray-400">No training jobs yet.</p>}
          </div>
        </section>

        <section className="rounded-xl border border-gray-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-gray-700">Model registry</h2>
            {isAdmin && (
              <button
                onClick={handleDiscover}
                className="rounded-lg border border-gray-200 px-3 py-1 text-xs text-gray-700 hover:border-indigo-400 hover:text-gray-900"
              >
                Discover local models
              </button>
            )}
          </div>
          <p className="mb-3 text-xs text-gray-400">
            Only local Ollama models are supported right now (no cloud provider keys configured, by design). The
            router picks the highest-scoring PRODUCTION model per capability for chat automatically.
          </p>
          <div className="space-y-1">
            {models.map((model) => (
              <div key={model.id} className="rounded-lg px-2 py-2 text-sm hover:bg-gray-100">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-gray-800">
                      {model.name} <span className="text-gray-400">({model.base_model})</span>
                    </p>
                    <p className="text-xs text-gray-400">
                      <span className="rounded bg-gray-100 px-1.5 py-0.5">{model.capability}</span>{" "}
                      <span className="rounded bg-gray-100 px-1.5 py-0.5">{model.provider}</span>{" "}
                      {model.status}
                      {model.eval_score !== null ? ` · eval: ${model.eval_score.toFixed(2)}` : " · not benchmarked"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {isAdmin && (
                      <button
                        onClick={() => handleBenchmark(model.id)}
                        disabled={benchmarking === model.id}
                        className="rounded-lg border border-gray-200 px-2 py-1 text-xs text-gray-700 hover:border-indigo-400 hover:text-gray-900 disabled:opacity-40"
                      >
                        {benchmarking === model.id ? "Benchmarking…" : "Benchmark"}
                      </button>
                    )}
                    {isAdmin && (
                      <select
                        value={model.status}
                        onChange={(e) => handlePromote(model.id, e.target.value as ModelStatus)}
                        className="rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-900"
                      >
                        {PROMOTION_OPTIONS.map((s) => (
                          <option key={s} value={s}>
                            {s}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </div>
                {benchmarkResults[model.id] && (
                  <table className="mt-2 w-full text-xs text-gray-600">
                    <tbody>
                      {benchmarkResults[model.id].length === 0 ? (
                        <tr>
                          <td className="py-1 text-gray-400">
                            No benchmark suite defined yet for {model.capability} models.
                          </td>
                        </tr>
                      ) : (
                        benchmarkResults[model.id].map((r) => (
                          <tr key={r.id} className="border-t border-gray-100">
                            <td className="py-1 pr-3">{r.prompt_id}</td>
                            <td className="py-1 pr-3">{r.score.toFixed(2)}</td>
                            <td className="py-1 text-gray-400">{r.latency_ms}ms</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                )}
              </div>
            ))}
            {models.length === 0 && <p className="py-4 text-center text-sm text-gray-400">No registered models yet.</p>}
          </div>
        </section>
      </div>
    </div>
  );
}
