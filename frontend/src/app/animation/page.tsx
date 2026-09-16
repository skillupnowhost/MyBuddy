"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Film } from "lucide-react";
import WorkspaceHeader from "@/components/WorkspaceHeader";
import {
  createAnimationDocument,
  deleteAnimationDocument,
  deleteKeyframe,
  downloadAnimationDocument,
  getAnimationBlobUrl,
  listAnimationDocuments,
  updateKeyframe,
} from "@/lib/animation";
import { isLoggedIn } from "@/lib/auth";
import { listVectorDocuments } from "@/lib/vector";
import type { AnimationDocumentItem, AnimationKeyframeItem, VectorDocumentItem } from "@/lib/types";

function AnimationPreview({ animationId }: { animationId: string }) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    getAnimationBlobUrl(animationId)
      .then((url) => {
        if (cancelled) {
          URL.revokeObjectURL(url);
          return;
        }
        objectUrl = url;
        setSrc(url);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [animationId]);

  if (!src) return <div className="h-64 w-64 animate-pulse rounded-lg bg-gray-100" />;
  // eslint-disable-next-line @next/next/no-img-element -- a blob: URL can't go through next/image's loader
  return <img src={src} alt="animation preview" className="max-w-full rounded-lg border border-gray-200 bg-white" />;
}

export default function AnimationPage() {
  const router = useRouter();
  const [vectorDocuments, setVectorDocuments] = useState<VectorDocumentItem[]>([]);
  const [animations, setAnimations] = useState<AnimationDocumentItem[]>([]);
  const [activeAnimation, setActiveAnimation] = useState<AnimationDocumentItem | null>(null);
  const [sourceDocId, setSourceDocId] = useState("");
  const [prompt, setPrompt] = useState("");
  const [durationMs, setDurationMs] = useState(2000);
  const [loop, setLoop] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const previewKey = useRef(0);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    listVectorDocuments()
      .then((docs) => {
        setVectorDocuments(docs);
        if (docs.length > 0) setSourceDocId(docs[0].id);
      })
      .catch(() => setError("Could not load vector documents."));
    listAnimationDocuments()
      .then(setAnimations)
      .catch(() => setError("Could not load animations."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function handleGenerate() {
    if (!sourceDocId || !prompt.trim() || generating) return;
    setError(null);
    setGenerating(true);
    try {
      const anim = await createAnimationDocument(sourceDocId, prompt.trim(), durationMs, undefined, loop);
      setAnimations((prev) => [anim, ...prev]);
      setActiveAnimation(anim);
      setPrompt("");
      previewKey.current += 1;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate an animation.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleDeleteAnimation(id: string) {
    await deleteAnimationDocument(id);
    setAnimations((prev) => prev.filter((a) => a.id !== id));
    if (activeAnimation?.id === id) setActiveAnimation(null);
  }

  async function handleUpdateKeyframe(kf: AnimationKeyframeItem, field: "time_ms" | "value" | "easing", raw: string) {
    if (!activeAnimation) return;
    const patch =
      field === "time_ms"
        ? { time_ms: Number(raw) }
        : field === "value"
          ? { value: raw }
          : { easing: raw as AnimationKeyframeItem["easing"] };
    const updated = await updateKeyframe(activeAnimation.id, kf.id, patch);
    setActiveAnimation((prev) =>
      prev ? { ...prev, keyframes: prev.keyframes.map((k) => (k.id === updated.id ? updated : k)) } : prev,
    );
  }

  async function handleDeleteKeyframe(kf: AnimationKeyframeItem) {
    if (!activeAnimation) return;
    await deleteKeyframe(activeAnimation.id, kf.id);
    setActiveAnimation((prev) =>
      prev ? { ...prev, keyframes: prev.keyframes.filter((k) => k.id !== kf.id) } : prev,
    );
  }

  return (
    <div className="flex h-screen flex-col bg-white text-gray-900">
      <WorkspaceHeader icon={Film} title="MyBuddy Animator" />

      {error && <p className="border-b border-gray-200 bg-red-50 px-4 py-2 text-sm text-red-500">{error}</p>}

      <div className="flex flex-1 overflow-hidden">
        <aside className="flex w-72 shrink-0 flex-col border-r border-gray-200 bg-white p-3">
          <label className="mb-2 block text-xs text-gray-500">
            Source Vector document
            <select
              value={sourceDocId}
              onChange={(e) => setSourceDocId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-gray-200 bg-gray-50 px-2 py-1.5 text-xs text-gray-900"
            >
              {vectorDocuments.length === 0 && <option value="">No vector documents yet</option>}
              {vectorDocuments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title}
                </option>
              ))}
            </select>
          </label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe the motion: move the circle across the screen"
            rows={3}
            className="mb-2 w-full resize-none rounded-lg border border-gray-200 bg-gray-50 px-2 py-1.5 text-xs text-gray-900 outline-none focus:border-indigo-400 focus:bg-white"
          />
          <div className="mb-2 flex items-center gap-2 text-xs text-gray-500">
            <label className="flex items-center gap-1">
              Duration (ms)
              <input
                type="number"
                value={durationMs}
                onChange={(e) => setDurationMs(Number(e.target.value))}
                className="w-20 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-900"
              />
            </label>
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={loop} onChange={(e) => setLoop(e.target.checked)} className="accent-indigo-600" />
              loop
            </label>
          </div>
          <button
            onClick={handleGenerate}
            disabled={!sourceDocId || !prompt.trim() || generating}
            className="mb-4 w-full rounded-lg bg-gradient-to-r from-indigo-600 to-violet-600 px-3 py-1.5 text-xs font-medium text-white hover:from-indigo-500 hover:to-violet-500 disabled:opacity-40"
          >
            {generating ? "Generating..." : "+ Generate animation"}
          </button>

          <div className="flex-1 overflow-y-auto">
            {animations.map((a) => (
              <div
                key={a.id}
                className={`group flex items-center justify-between rounded-lg px-2 py-2 text-sm ${
                  a.id === activeAnimation?.id ? "bg-gray-100 text-gray-900" : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                }`}
              >
                <button onClick={() => setActiveAnimation(a)} className="flex-1 truncate text-left text-xs">
                  {a.title}
                </button>
                <button
                  onClick={() => handleDeleteAnimation(a.id)}
                  className="ml-1 opacity-0 transition group-hover:opacity-100 hover:text-red-500"
                  aria-label="Delete animation"
                >
                  &times;
                </button>
              </div>
            ))}
            {animations.length === 0 && <p className="py-6 text-center text-xs text-gray-400">No animations yet.</p>}
          </div>
        </aside>

        <main className="flex flex-1 flex-col items-center gap-4 overflow-auto p-6">
          {activeAnimation ? (
            <>
              <AnimationPreview key={activeAnimation.id} animationId={activeAnimation.id} />
              <button
                onClick={() => downloadAnimationDocument(activeAnimation.id, activeAnimation.title)}
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-700 hover:bg-gray-100 hover:text-gray-900"
              >
                Export SVG
              </button>

              <div className="w-full max-w-xl overflow-x-auto rounded-lg border border-gray-200">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 text-gray-500">
                    <tr>
                      <th className="px-2 py-1">time_ms</th>
                      <th className="px-2 py-1">prop</th>
                      <th className="px-2 py-1">value</th>
                      <th className="px-2 py-1">easing</th>
                      <th className="px-2 py-1" />
                    </tr>
                  </thead>
                  <tbody>
                    {activeAnimation.keyframes.map((kf) => (
                      <tr key={kf.id} className="border-t border-gray-100">
                        <td className="px-2 py-1">
                          <input
                            type="number"
                            defaultValue={kf.time_ms}
                            onBlur={(e) => handleUpdateKeyframe(kf, "time_ms", e.target.value)}
                            className="w-16 bg-transparent text-gray-900"
                          />
                        </td>
                        <td className="px-2 py-1 text-gray-700">{kf.prop}</td>
                        <td className="px-2 py-1">
                          <input
                            defaultValue={String(kf.value)}
                            onBlur={(e) => handleUpdateKeyframe(kf, "value", e.target.value)}
                            className="w-20 bg-transparent text-gray-900"
                          />
                        </td>
                        <td className="px-2 py-1 text-gray-700">{kf.easing}</td>
                        <td className="px-2 py-1">
                          <button onClick={() => handleDeleteKeyframe(kf)} className="text-gray-400 hover:text-red-500">
                            &times;
                          </button>
                        </td>
                      </tr>
                    ))}
                    {activeAnimation.keyframes.length === 0 && (
                      <tr>
                        <td colSpan={5} className="px-2 py-4 text-center text-gray-400">
                          No keyframes.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="mt-20 text-sm text-gray-400">Generate or select an animation to preview it.</p>
          )}
        </main>
      </div>
    </div>
  );
}
