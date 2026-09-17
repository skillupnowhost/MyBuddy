"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { SlidersHorizontal } from "lucide-react";
import PageHeader from "@/components/PageHeader";
import PageBlobBackground from "@/components/PageBlobBackground";
import { getCurrentUser } from "@/lib/admin";
import { isLoggedIn } from "@/lib/auth";
import {
  cancelTrainingJob,
  createTrainingJob,
  deleteDataset,
  discoverModels,
  listDatasets,
  listArenaHistory,
  listRegisteredModels,
  listTrainingJobs,
  promoteModel,
  runArenaComparison,
  runBenchmark,
  uploadDataset,
} from "@/lib/training";
import type {
  ArenaComparisonResultItem,
  DatasetItem,
  ModelBenchmarkResultItem,
  ModelStatus,
  RegisteredModelItem,
  TrainingJobItem,
} from "@/lib/types";

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
  const [arenaCapability, setArenaCapability] = useState<"TEXT" | "CODE">("TEXT");
  const [arenaPrompt, setArenaPrompt] = useState("");
  const [arenaReference, setArenaReference] = useState("");
  const [arenaResults, setArenaResults] = useState<ArenaComparisonResultItem[]>([]);
  const [arenaHistory, setArenaHistory] = useState<ArenaComparisonResultItem[]>([]);
  const [runningArena, setRunningArena] = useState(false);
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
      .then((user) => {
        const admin = user.role === "ADMIN";
        setIsAdmin(admin);
        if (admin) loadArenaHistory(arenaCapability);
      })
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

  async function handleArenaCompare() {
    if (!arenaPrompt.trim()) return;
    setError(null);
    setRunningArena(true);
    try {
      const results = await runArenaComparison(arenaCapability, arenaPrompt.trim(), arenaReference.trim());
      setArenaResults(results);
      setArenaHistory((prev) => [...results, ...prev].slice(0, 50));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not run model arena.");
    } finally {
      setRunningArena(false);
    }
  }

  async function loadArenaHistory(capability: "TEXT" | "CODE") {
    try {
      setArenaHistory(await listArenaHistory(capability));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load arena history.");
    }
  }

  const validatedDatasets = datasets.filter((d) => d.status === "VALIDATED");

  return (
    <div className="relative min-h-screen bg-white px-6 py-8 text-gray-900">
      <PageBlobBackground />
      <div className="mx-auto max-w-4xl">
        <PageHeader
          icon={SlidersHorizontal}
          title="Fine-tuning"
          description="Training runs as a separate process (see training/README.md). Without a GPU and the training
          environment installed, jobs correctly fail fast rather than pretending to train."
        />

        {error && (
          <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
        )}

        <section className="mb-8 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md">
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

        <section className="mb-8 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md">
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
              className="rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2 text-sm font-medium text-white hover:from-indigo-500 hover:to-violet-500 disabled:opacity-40"
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

        <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md">
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

        {isAdmin && (
          <section className="mt-8 rounded-2xl border border-gray-200 bg-white p-5 shadow-sm transition hover:shadow-md">
            <h2 className="mb-1 text-sm font-medium text-gray-700">Model arena</h2>
            <p className="mb-3 text-xs text-gray-400">
              Compare every registered local model for one prompt. Add an expected answer for an automatic score.
            </p>
            <div className="flex flex-wrap gap-2">
              <select
                value={arenaCapability}
                onChange={(e) => {
                  const capability = e.target.value as "TEXT" | "CODE";
                  setArenaCapability(capability);
                  loadArenaHistory(capability);
                }}
                className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900"
              >
                <option value="TEXT">TEXT</option>
                <option value="CODE">CODE</option>
              </select>
              <input
                value={arenaPrompt}
                onChange={(e) => setArenaPrompt(e.target.value)}
                placeholder="Prompt to compare"
                className="min-w-64 flex-1 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900"
              />
              <input
                value={arenaReference}
                onChange={(e) => setArenaReference(e.target.value)}
                placeholder="Expected answer (optional)"
                className="min-w-52 flex-1 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-900"
              />
              <button
                onClick={handleArenaCompare}
                disabled={runningArena || !arenaPrompt.trim()}
                className="rounded-lg bg-gray-900 px-3 py-2 text-sm text-white hover:bg-gray-700 disabled:opacity-40"
              >
                {runningArena ? "Comparing..." : "Compare"}
              </button>
            </div>
            {arenaResults.length > 0 && (
              <div className="mt-4 space-y-2">
                {arenaResults.map((result) => {
                  const model = models.find((candidate) => candidate.id === result.model_id);
                  return (
                    <div key={result.id} className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2 text-sm">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium text-gray-800">{model?.name || result.model_id}</span>
                        <span className="text-xs text-gray-400">
                          {result.score === null ? "human review" : `score ${result.score.toFixed(2)}`} · {result.latency_ms}ms
                        </span>
                      </div>
                      <p className="mt-1 whitespace-pre-wrap text-gray-600">{result.response}</p>
                    </div>
                  );
                })}
              </div>
            )}
            {arenaHistory.length > 0 && (
              <div className="mt-5 border-t border-gray-100 pt-3">
                <p className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-400">Recent arena runs</p>
                <div className="space-y-1">
                  {arenaHistory.slice(0, 8).map((result) => {
                    const model = models.find((candidate) => candidate.id === result.model_id);
                    return (
                      <div key={result.id} className="flex items-center justify-between gap-3 text-xs text-gray-500">
                        <span className="truncate">{model?.name || result.model_id}</span>
                        <span className="shrink-0">
                          {result.score === null ? "review" : result.score.toFixed(2)} · {result.latency_ms}ms
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
