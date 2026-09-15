"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { listAnimationDocuments } from "@/lib/animation";
import { apiFetch } from "@/lib/api";
import { isLoggedIn } from "@/lib/auth";
import {
  attachAsset,
  createBrandKit,
  createCreativeProject,
  deleteBrandKit,
  deleteCreativeProject,
  detachAsset,
  generateAsset,
  getCreativeProject,
  listBrandKits,
  listCreativeProjects,
} from "@/lib/creative";
import { listMotionProjects } from "@/lib/motion";
import { listVectorDocuments } from "@/lib/vector";
import type {
  AnimationDocumentItem,
  BrandKitItem,
  CreativeAssetItem,
  CreativeAssetType,
  CreativeProjectItem,
  MotionProjectItem,
  VectorDocumentItem,
  VectorDocumentPurpose,
} from "@/lib/types";

const EXPORT_URL_BY_TYPE: Record<CreativeAssetType, (id: string) => string> = {
  VECTOR: (id) => `/api/v1/vector/documents/${id}/export`,
  ANIMATION: (id) => `/api/v1/animation/documents/${id}/export`,
  MOTION: (id) => `/api/v1/motion/projects/${id}/export`,
};

function AssetPreview({ exportUrl }: { exportUrl: string }) {
  const [src, setSrc] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    apiFetch(exportUrl)
      .then((resp) => (resp.ok ? resp.blob() : Promise.reject(new Error("failed"))))
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [exportUrl]);

  if (!src) return <div className="h-24 w-24 animate-pulse rounded-lg bg-gray-100" />;
  // eslint-disable-next-line @next/next/no-img-element -- a blob: URL can't go through next/image's loader
  return <img src={src} alt="asset preview" className="h-24 w-24 rounded-lg border border-gray-200 bg-white object-contain" />;
}

const PURPOSE_OPTIONS: { value: VectorDocumentPurpose; label: string }[] = [
  { value: "GENERAL", label: "General" },
  { value: "ILLUSTRATION", label: "Illustration" },
  { value: "LOGO", label: "Logo" },
  { value: "ICON", label: "Icon" },
];

export default function CreativePage() {
  const router = useRouter();
  const [brandKits, setBrandKits] = useState<BrandKitItem[]>([]);
  const [projects, setProjects] = useState<CreativeProjectItem[]>([]);
  const [activeProject, setActiveProject] = useState<CreativeProjectItem | null>(null);

  const [kitName, setKitName] = useState("");
  const [primaryColor, setPrimaryColor] = useState("#3366cc");
  const [secondaryColor, setSecondaryColor] = useState("#ffffff");
  const [accentColor, setAccentColor] = useState("#ff9900");
  const [fontFamily, setFontFamily] = useState("");

  const [projectTitle, setProjectTitle] = useState("");
  const [selectedBrandKitId, setSelectedBrandKitId] = useState("");

  const [genPrompt, setGenPrompt] = useState("");
  const [genPurpose, setGenPurpose] = useState<VectorDocumentPurpose>("LOGO");
  const [genLabel, setGenLabel] = useState("");
  const [generating, setGenerating] = useState(false);

  const [vectorDocs, setVectorDocs] = useState<VectorDocumentItem[]>([]);
  const [animations, setAnimations] = useState<AnimationDocumentItem[]>([]);
  const [motionProjects, setMotionProjects] = useState<MotionProjectItem[]>([]);
  const [attachType, setAttachType] = useState<CreativeAssetType>("VECTOR");
  const [attachId, setAttachId] = useState("");

  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    listBrandKits().then(setBrandKits).catch(() => setError("Could not load brand kits."));
    listCreativeProjects().then(setProjects).catch(() => setError("Could not load creative projects."));
    listVectorDocuments().then(setVectorDocs).catch(() => {});
    listAnimationDocuments().then(setAnimations).catch(() => {});
    listMotionProjects().then(setMotionProjects).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  async function handleCreateBrandKit() {
    if (!kitName.trim()) return;
    setError(null);
    try {
      const kit = await createBrandKit({
        name: kitName.trim(),
        primary_color: primaryColor || undefined,
        secondary_color: secondaryColor || undefined,
        accent_color: accentColor || undefined,
        font_family: fontFamily.trim() || undefined,
      });
      setBrandKits((prev) => [kit, ...prev]);
      setKitName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create brand kit.");
    }
  }

  async function handleDeleteBrandKit(id: string) {
    await deleteBrandKit(id);
    setBrandKits((prev) => prev.filter((k) => k.id !== id));
  }

  async function handleCreateProject() {
    if (!projectTitle.trim()) return;
    setError(null);
    try {
      const project = await createCreativeProject(projectTitle.trim(), selectedBrandKitId || undefined);
      setProjects((prev) => [project, ...prev]);
      setActiveProject(project);
      setProjectTitle("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create project.");
    }
  }

  async function handleDeleteProject(id: string) {
    await deleteCreativeProject(id);
    setProjects((prev) => prev.filter((p) => p.id !== id));
    if (activeProject?.id === id) setActiveProject(null);
  }

  async function handleGenerateAsset() {
    if (!activeProject || !genPrompt.trim() || generating) return;
    setError(null);
    setGenerating(true);
    try {
      await generateAsset(activeProject.id, {
        prompt: genPrompt.trim(),
        purpose: genPurpose,
        label: genLabel.trim() || undefined,
      });
      const refreshed = await getCreativeProject(activeProject.id);
      setActiveProject(refreshed);
      setProjects((prev) => prev.map((p) => (p.id === refreshed.id ? refreshed : p)));
      setGenPrompt("");
      setGenLabel("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate asset.");
    } finally {
      setGenerating(false);
    }
  }

  async function handleAttach() {
    if (!activeProject || !attachId) return;
    setError(null);
    try {
      const asset = await attachAsset(activeProject.id, attachType, attachId);
      setActiveProject((prev) => (prev ? { ...prev, assets: [...prev.assets, asset] } : prev));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not attach asset.");
    }
  }

  async function handleDetach(asset: CreativeAssetItem) {
    if (!activeProject) return;
    await detachAsset(activeProject.id, asset.id);
    setActiveProject((prev) => (prev ? { ...prev, assets: prev.assets.filter((a) => a.id !== asset.id) } : prev));
  }

  const attachOptions =
    attachType === "VECTOR" ? vectorDocs : attachType === "ANIMATION" ? animations : motionProjects;

  return (
    <div className="flex h-screen flex-col bg-[#f4f5f9] text-gray-900">
      <div className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3">
        <h1 className="text-lg font-semibold">MyBuddy Creative Director</h1>
        <Link href="/chat" className="text-sm text-indigo-600 hover:underline">
          &larr; Back to chat
        </Link>
      </div>

      {error && <p className="border-b border-gray-200 bg-red-50 px-4 py-2 text-sm text-red-500">{error}</p>}

      <div className="flex flex-1 overflow-hidden">
        <aside className="flex w-80 shrink-0 flex-col gap-4 overflow-y-auto border-r border-gray-200 bg-white p-3">
          <section>
            <h2 className="mb-2 text-xs font-medium text-gray-500">Brand kits</h2>
            <input
              value={kitName}
              onChange={(e) => setKitName(e.target.value)}
              placeholder="Brand kit name"
              className="mb-1 w-full rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-900"
            />
            <div className="mb-1 flex gap-1">
              <input type="color" value={primaryColor} onChange={(e) => setPrimaryColor(e.target.value)} className="h-7 w-full" />
              <input type="color" value={secondaryColor} onChange={(e) => setSecondaryColor(e.target.value)} className="h-7 w-full" />
              <input type="color" value={accentColor} onChange={(e) => setAccentColor(e.target.value)} className="h-7 w-full" />
            </div>
            <input
              value={fontFamily}
              onChange={(e) => setFontFamily(e.target.value)}
              placeholder="Font family (reference only)"
              className="mb-1 w-full rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-900"
            />
            <button
              onClick={handleCreateBrandKit}
              disabled={!kitName.trim()}
              className="mb-2 w-full rounded-lg bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
            >
              + Add brand kit
            </button>
            {brandKits.map((k) => (
              <div key={k.id} className="mb-1 flex items-center justify-between rounded-lg px-2 py-1 text-xs text-gray-700 hover:bg-gray-100">
                <span className="truncate">{k.name}</span>
                <button onClick={() => handleDeleteBrandKit(k.id)} className="text-gray-400 hover:text-red-500">
                  &times;
                </button>
              </div>
            ))}
          </section>

          <section>
            <h2 className="mb-2 text-xs font-medium text-gray-500">Projects</h2>
            <input
              value={projectTitle}
              onChange={(e) => setProjectTitle(e.target.value)}
              placeholder="Project title"
              className="mb-1 w-full rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-900"
            />
            <select
              value={selectedBrandKitId}
              onChange={(e) => setSelectedBrandKitId(e.target.value)}
              className="mb-1 w-full rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-900"
            >
              <option value="">No brand kit</option>
              {brandKits.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name}
                </option>
              ))}
            </select>
            <button
              onClick={handleCreateProject}
              disabled={!projectTitle.trim()}
              className="mb-2 w-full rounded-lg bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
            >
              + New project
            </button>
            {projects.map((p) => (
              <div
                key={p.id}
                className={`mb-1 flex items-center justify-between rounded-lg px-2 py-1 text-xs ${
                  p.id === activeProject?.id ? "bg-gray-100 text-gray-900" : "text-gray-700 hover:bg-gray-100"
                }`}
              >
                <button onClick={() => setActiveProject(p)} className="flex-1 truncate text-left">
                  {p.title}
                </button>
                <button onClick={() => handleDeleteProject(p.id)} className="text-gray-400 hover:text-red-500">
                  &times;
                </button>
              </div>
            ))}
          </section>
        </aside>

        <main className="flex-1 overflow-y-auto p-6">
          {activeProject ? (
            <>
              <section className="mb-6 rounded-xl border border-gray-200 bg-white p-4">
                <h2 className="mb-2 text-sm font-medium text-gray-700">Generate an asset (brand-aware)</h2>
                <textarea
                  value={genPrompt}
                  onChange={(e) => setGenPrompt(e.target.value)}
                  placeholder="Describe the asset to generate"
                  rows={2}
                  className="mb-2 w-full resize-none rounded-lg border border-gray-200 bg-gray-50 px-2 py-1.5 text-xs text-gray-900 outline-none focus:border-indigo-400 focus:bg-white"
                />
                <div className="mb-2 flex gap-2">
                  <select
                    value={genPurpose}
                    onChange={(e) => setGenPurpose(e.target.value as VectorDocumentPurpose)}
                    className="rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-900"
                  >
                    {PURPOSE_OPTIONS.map((opt) => (
                      <option key={opt.value} value={opt.value}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                  <input
                    value={genLabel}
                    onChange={(e) => setGenLabel(e.target.value)}
                    placeholder="Label (optional)"
                    className="flex-1 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-900"
                  />
                </div>
                <button
                  onClick={handleGenerateAsset}
                  disabled={!genPrompt.trim() || generating}
                  className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
                >
                  {generating ? "Generating..." : "+ Generate asset"}
                </button>
              </section>

              <section className="mb-6 rounded-xl border border-gray-200 bg-white p-4">
                <h2 className="mb-2 text-sm font-medium text-gray-700">Attach an existing asset</h2>
                <div className="flex gap-2">
                  <select
                    value={attachType}
                    onChange={(e) => {
                      setAttachType(e.target.value as CreativeAssetType);
                      setAttachId("");
                    }}
                    className="rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-900"
                  >
                    <option value="VECTOR">Vector</option>
                    <option value="ANIMATION">Animation</option>
                    <option value="MOTION">Motion</option>
                  </select>
                  <select
                    value={attachId}
                    onChange={(e) => setAttachId(e.target.value)}
                    className="flex-1 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-900"
                  >
                    <option value="">Select...</option>
                    {attachOptions.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.title}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={handleAttach}
                    disabled={!attachId}
                    className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-40"
                  >
                    Attach
                  </button>
                </div>
              </section>

              <section>
                <h2 className="mb-2 text-sm font-medium text-gray-700">Assets ({activeProject.assets.length})</h2>
                <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
                  {activeProject.assets.map((asset) => (
                    <div key={asset.id} className="rounded-lg border border-gray-200 p-2 text-center">
                      <AssetPreview exportUrl={EXPORT_URL_BY_TYPE[asset.asset_type](asset.asset_id)} />
                      <p className="mt-1 truncate text-xs text-gray-700">{asset.label || asset.asset_type}</p>
                      <button onClick={() => handleDetach(asset)} className="text-xs text-gray-400 hover:text-red-500">
                        detach
                      </button>
                    </div>
                  ))}
                  {activeProject.assets.length === 0 && (
                    <p className="col-span-full py-6 text-center text-xs text-gray-400">No assets yet.</p>
                  )}
                </div>
              </section>
            </>
          ) : (
            <p className="mt-20 text-center text-sm text-gray-400">Create or select a creative project.</p>
          )}
        </main>
      </div>
    </div>
  );
}
